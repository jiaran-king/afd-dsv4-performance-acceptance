"""Fetch and verify the versioned request payload and atomically unpack it."""

import argparse
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "cases/910c-dsv4-w4a8-rps4/case.json"
RELEASES = "https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/download"


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as data:
        for chunk in iter(lambda: data.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(path, url, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and sha(path) == expected:
        return
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    pending = Path(name)
    try:
        with os.fdopen(fd, "wb") as target, urlopen(url, timeout=60) as source:
            shutil.copyfileobj(source, target)
        if sha(pending) != expected:
            raise ValueError(f"Release asset checksum mismatch: {url}")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def unpack(path, output, split_files, optional_files=()):
    if output.is_dir():
        try:
            if all(sha(output / name) == digest for name, digest in split_files.items()):
                return
        except OSError:
            pass
    output.parent.mkdir(parents=True, exist_ok=True)
    allowed = split_files.keys() | set(optional_files)
    with tempfile.TemporaryDirectory(dir=output.parent) as scratch, tarfile.open(path, "r:gz") as archive:
        stage = Path(scratch) / "prepared"
        seen = set()
        for member in archive:
            if member.name not in allowed or member.name in seen or not member.isfile():
                raise ValueError(f"Unexpected archive entry: {member.name}")
            dest = stage / member.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, dest.open("wb") as target:
                shutil.copyfileobj(source, target)
            if member.name in split_files and sha(dest) != split_files[member.name]:
                raise ValueError(f"Request payload checksum mismatch: {member.name}")
            seen.add(member.name)
        if not split_files.keys() <= seen:
            raise ValueError("Incomplete request payload")
        if output.exists() or output.is_symlink():
            output.rename(Path(scratch) / "previous")
        stage.rename(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--runtime", type=Path, default=ROOT / ".runtime")
    args = parser.parse_args()
    manifest = json.loads(LOCK.read_text())
    load = manifest["load"]
    splits = {f"{key.replace('_', '-')}/requests.jsonl": load["splits"][key]["sha256"]
              for key in ("warmup", "formal_candidate")}
    optional_files = {"qualification/requests.jsonl", *load["asset_support_files"]}
    archive = args.archive or (args.runtime / "downloads" / load["asset"])
    if args.archive is None:
        url = f"{RELEASES}/{load['release']}/{load['asset']}"
        download(archive, url, load["asset_sha256"])
    output = args.runtime / "workload"
    unpack(archive, output, splits, optional_files)
    print(f"Verified frozen inputs at {output}")


if __name__ == "__main__":
    main()
