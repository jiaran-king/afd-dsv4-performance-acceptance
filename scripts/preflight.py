"""Check a target container or compare its record with a saved baseline."""

import hashlib
import importlib.metadata
import ipaddress
import json
import platform
import re
import socket
import subprocess
import sys
from pathlib import Path


LOCK = Path(__file__).resolve().parent.parent / "cases/910c-dsv4-w4a8-rps4/case.json"


def verify(value, expected, name):
    if value != expected:
        raise ValueError(f"{name}: expected {expected!r}, got {value!r}")


def cmd(*args):
    return subprocess.check_output(args, text=True).strip()


def driver_version():
    try:
        text = Path("/usr/local/Ascend/driver/version.info").read_text()
    except OSError:
        return None
    return text.strip().partition("\n")[0].strip() or None


def compare_baseline(saved_path, current_path):
    saved = json.loads(Path(saved_path).read_text())
    current = json.loads(Path(current_path).read_text())
    label = f"{current['role']} saved baseline"
    for field in ("role", "vllm", "vllm_ascend", "cann", "torch_npu", "devices", "shards"):
        verify(current[field], saved[field], f"{label} {field}")
    if "container" in saved:
        verify(current["container"], saved["container"], f"{label} container")
    saved_driver = (saved.get("driver") or "").strip()
    if saved_driver and current.get("driver"):
        verify(current["driver"], saved_driver, f"{label} driver")

    saved_model = saved.get("model_json_sha256")
    if saved_model is None:
        model_lock = json.loads(LOCK.read_text())["model"]
        verify(saved["model_sha256"], model_lock["file_sha256"], f"{label} model fingerprint")
        saved_model = model_lock["json_sha256"]
    verify(current["model_json_sha256"], saved_model, f"{label} model JSON fingerprint")


def main():
    if sys.argv[1] == "--compare-baseline":
        compare_baseline(*sys.argv[2:])
        return

    role, model, devices, vllm, ascend, cann, p_ip, d_ip, output, *ports = sys.argv[1:]
    addresses = {ipaddress.IPv4Address(value) for value in (p_ip, d_ip)}
    verify(len(addresses), 2, "distinct P/D addresses")
    local = p_ip if role == "P" else d_ip
    for port in ports:
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server.bind((local, int(port)))
            except OSError as error:
                raise ValueError(f"{role} cannot use {local}:{port}: {error}") from error
    lock = json.loads(LOCK.read_text())
    version = lock["runtime"]
    verify(platform.machine(), "aarch64", "container architecture")
    verify(cmd("git", "-C", vllm, "rev-parse", "HEAD"), version["vllm"], "vLLM source")
    verify(cmd("git", "-C", ascend, "rev-parse", "HEAD"), version["vllm_ascend"], "vLLM-Ascend source")
    for source in (vllm, ascend):
        changes = cmd("git", "-C", source, "status", "--short", "--untracked-files=no",
                      "--", ".", ":(exclude,glob)**/*.md", ":(exclude,glob)**/*.rst")
        verify(changes, "", f"tracked source edits in {source}")
    verify(importlib.metadata.version("torch-npu"), version["torch_npu"], "torch-npu")
    info = (Path(cann) / "compiler/version.info").read_text()
    verify(re.search(r"^Version=(.*)$", info, re.M)[1].strip(), version["cann"], "CANN")

    mapping = cmd("npu-smi", "info", "-m")
    visible = set(re.findall(r"^[ \t]*\d+[ \t]+\d+[ \t]+(\d+)[ \t]+\d+[ \t]+", mapping, re.M))
    selected = [device.strip() for device in devices.split(",")]
    verify(len(selected), 16, f"{role} device rank count")
    verify(len(set(selected)), 16, f"{role} unique devices")
    if not set(selected) <= visible:
        raise ValueError(f"{role} logical devices are outside Ascend device mapping")

    model = Path(model)
    fingerprints = {}
    model_json = {}
    for name, expected in lock["model"]["json_sha256"].items():
        raw = (model / name).read_bytes()
        fingerprints[name] = hashlib.sha256(raw).hexdigest()
        canonical = json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":")).encode("utf-8")
        model_json[name] = hashlib.sha256(canonical).hexdigest()
        verify(model_json[name], expected, f"model JSON content {name}")
    shards = [p for p in model.glob("*.safetensors") if p.is_file() and p.stat().st_size]
    verify(len(shards), lock["model"]["safetensors_shards"], "safetensors shard count")
    record = json.dumps({
        "role": role, "container": socket.gethostname(), "vllm": version["vllm"], "vllm_ascend": version["vllm_ascend"],
        "cann": version["cann"], "driver": driver_version(), "reference_driver": version["driver"],
        "torch_npu": version["torch_npu"], "devices": selected, "model_sha256": fingerprints,
        "model_json_sha256": model_json, "checkpoint_path": str(model.resolve()), "shards": len(shards),
    }, indent=2)
    Path(output).write_text(record + "\n")
    print(record)


if __name__ == "__main__":
    main()
