"""Check that workers mapped the prepared libraries, recording their hashes."""

import hashlib
import json
import sys
import sysconfig
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence, runtime, group = sys.argv[1:]
    runtime = Path(runtime)
    maps = json.loads(Path(evidence).read_text())
    cws = Path((runtime / "cws-vendor.path").read_text().strip()).resolve()
    afd = runtime / "afd-install/afd_plugin"
    found = {Path(key).resolve(): sha for key, sha in maps["library_sha256"].items()}
    cws_library = (cws / "op_api/lib/libcust_opapi.so").resolve()
    cws_sha256 = (runtime / "cws-vendor.sha256").read_text().strip()
    if found.get(cws_library) != cws_sha256:
        raise ValueError(f"The prepared CWS library was not mapped with its recorded SHA-256: {cws_library}")
    if group == "baseline" and any(path != cws_library and "/afd_plugin/" in str(path) for path in found):
        raise ValueError("The baseline mapped an AFD library")
    if group != "baseline":
        extension = f"_C_ascend{sysconfig.get_config_var('EXT_SUFFIX')}"
        packages = [afd]
        if group == "afd12":
            packages.append(runtime / "afd-attention/afd_plugin")
        for package in packages:
            for path in (package / "_cann_ops_custom/vendors/afd-plugin/op_api/lib/libcust_opapi.so",
                         package / extension):
                if found.get(path.resolve()) != digest(path):
                    raise ValueError(f"The expected library was not mapped: {path}")
    print(f"Verified mapped native libraries for {group} ({len(maps['processes'])} processes).")


if __name__ == "__main__":
    main()
