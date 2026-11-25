"""Record site software and identify compatible cached builds."""

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import sysconfig
from pathlib import Path


SOURCE_PATHS = (
    ".", ":(exclude,top)docs", ":(exclude,top)tests", ":(exclude,top).gitignore",
    ":(exclude,top).github", ":(exclude,glob)**/*.md", ":(exclude,glob)**/*.rst",
)


def fingerprint(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(source, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(source), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def source_state(directory):
    source = Path(directory).resolve()
    state = {"path": str(source), "revision": None, "worktree_sha256": None, "runtime_edits": None}
    if not (source / ".git").exists():
        return state
    revision = git_output(source, "rev-parse", "--verify", "HEAD")
    if not revision:
        return state
    state["revision"] = revision.decode().strip()
    status = git_output(source, "status", "--short", "--untracked-files=normal")
    if status is not None:
        state["changes"] = status.decode(errors="replace").splitlines()
    diff = git_output(source, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--", *SOURCE_PATHS)
    names = git_output(source, "ls-files", "--others", "--exclude-standard", "-z", "--", *SOURCE_PATHS)
    if diff is None or names is None:
        return state
    try:
        extra = {os.fsdecode(name): file_digest(source / os.fsdecode(name))
                 for name in names.split(b"\0") if name}
    except OSError:
        return state
    state["runtime_edits"] = bool(diff or extra)
    state["worktree_sha256"] = fingerprint([hashlib.sha256(diff).hexdigest(), extra])
    return state


def package_state(name):
    try:
        dist = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return {"version": None}
    try:
        record = dist.read_text("RECORD")
    except (OSError, UnicodeError):
        record = None
    return {
        "version": dist.version,
        "path": str(Path(dist.locate_file("")).resolve()),
        "record_sha256": hashlib.sha256(record.encode()).hexdigest() if record else None,
    }


def cann_state(directory):
    root = Path(directory).resolve()
    manifests = {}
    version = None
    for name in ("compiler/version.info", "runtime/version.info", "version.info", "set_env.sh"):
        try:
            content = (root / name).read_bytes()
        except OSError:
            continue
        manifests[name] = hashlib.sha256(content).hexdigest()
        if name.endswith("version.info") and version is None:
            match = re.search(r"^Version\s*=\s*(.+)$", content.decode(errors="replace"), re.M)
            if match:
                version = match[1].strip()
    return {"path": str(root), "version": version, "manifests": manifests}


def software_state(vllm, ascend, cann):
    return {
        "sources": {"vllm": source_state(vllm), "vllm_ascend": source_state(ascend)},
        "cann": cann_state(cann),
        "packages": {name: package_state(name) for name in ("vllm", "vllm-ascend", "torch", "torch-npu")},
        "python": {"version": sys.version, "extension_suffix": sysconfig.get_config_var("EXT_SUFFIX")},
        "architecture": platform.machine(),
    }


def software_key(state):
    sources = {
        name: (source["path"], source["revision"], source["worktree_sha256"])
        for name, source in state["sources"].items()
    }
    if (any(not revision or not worktree for _, revision, worktree in sources.values())
            or not state["cann"]["version"]
            or any(not state["packages"][name]["version"] for name in ("torch", "torch-npu"))):
        return None
    return fingerprint({**state, "sources": sources})


if __name__ == "__main__":
    vllm, ascend, cann, case_file, third_party = sys.argv[1:]
    key = software_key(software_state(vllm, ascend, cann))
    if key:
        case = json.loads(Path(case_file).read_text())["runtime"]
        print(fingerprint({
            "software": key,
            "afd": case["afd"],
            "patches": case["patches"],
            "build_scripts": {
                name: file_digest(Path(__file__).with_name(name))
                for name in ("prepare-runtime.sh", "prepare-cws-overlay.sh")
            },
            "cann_third_party": str(Path(third_party).resolve()) if third_party else None,
        }))
