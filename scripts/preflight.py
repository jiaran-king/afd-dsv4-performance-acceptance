"""Check the local test container and record the runtime environment."""

import hashlib
import json
import platform
import re
import socket
import subprocess
import sys
from pathlib import Path

from runtime_state import fingerprint, software_state


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


def check_weight_files(model):
    index = model / "model.safetensors.index.json"
    if index.is_file():
        weight_map = json.loads(index.read_text())["weight_map"]
        shards = [model / name for name in sorted(set(weight_map.values()))]
    else:
        shards = sorted(model.glob("*.safetensors"))
    if not shards:
        raise ValueError(f"No safetensors weight files in {model}")
    for path in shards:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"Missing or empty safetensors weight file: {path}")
    return len(shards)


def main():
    model, devices, vllm, ascend, cann, local, output, *ports = sys.argv[1:]
    for port in ports:
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server.bind(("0.0.0.0", int(port)))
            except OSError as error:
                raise ValueError(f"Cannot use port {port}: {error}") from error
    verify(platform.machine(), "aarch64", "container architecture")
    software = software_state(vllm, ascend, cann)

    mapping = cmd("npu-smi", "info", "-m")
    visible = set(re.findall(r"^[ \t]*\d+[ \t]+\d+[ \t]+(\d+)[ \t]+\d+[ \t]+", mapping, re.M))
    selected = [device.strip() for device in devices.split(",")]
    verify(len(selected), 16, "device rank count")
    verify(len(set(selected)), 16, "unique devices")
    if not set(selected) <= visible:
        raise ValueError("Logical devices are outside Ascend device mapping")

    model = Path(model)
    fingerprints = {}
    model_json = {}
    for name in ("config.json", "quant_model_description.json", "tokenizer.json"):
        raw = (model / name).read_bytes()
        fingerprints[name] = hashlib.sha256(raw).hexdigest()
        configuration = json.loads(raw)
        model_json[name] = fingerprint(configuration)
        if name == "config.json":
            model_config = {key: configuration[key] for key in (
                "model_type", "architectures", "num_hidden_layers", "hidden_size", "vocab_size",
            ) if key in configuration}
    shards = check_weight_files(model)
    record = json.dumps({
        "container": socket.gethostname(), "node_ip": local,
        "vllm": software["sources"]["vllm"]["revision"], "vllm_ascend": software["sources"]["vllm_ascend"]["revision"],
        "cann": software["cann"]["version"], "driver": driver_version(),
        "torch_npu": software["packages"]["torch-npu"]["version"], "software": software,
        "devices": selected,
        "model_config": model_config, "model_sha256": fingerprints,
        "model_json_sha256": model_json, "checkpoint_path": str(model.resolve()), "shards": shards,
    }, indent=2)
    try:
        Path(output).write_text(record + "\n")
    except OSError as error:
        raise SystemExit(f"Cannot write the preflight record in {Path(output).parent}: {error}")
    print(record)


if __name__ == "__main__":
    main()
