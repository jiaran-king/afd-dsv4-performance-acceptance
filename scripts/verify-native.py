"""Check that workers mapped the prepared libraries, recording their hashes."""

import hashlib
import json
import sys
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence, runtime, group = sys.argv[1:]
    runtime = Path(runtime)
    maps = json.loads(Path(evidence).read_text())
    cws = Path((runtime / "cws-vendor.path").read_text().strip()).resolve()
    afd = runtime / "afd-plugin/afd_plugin"
    found = {Path(key).resolve(): sha for key, sha in maps["library_sha256"].items()}
    cws_library = cws / "op_api/lib/libcust_opapi.so"
    expected = [cws_library]
    if group == "baseline" and any("/afd_plugin/" in str(path) for path in found):
        raise ValueError("The baseline mapped an AFD library")
    if group != "baseline":
        packages = [afd]
        if group == "afd12":
            packages.append(runtime / "afd-attention/afd_plugin")
        for package in packages:
            expected.append(package / "_cann_ops_custom/vendors/afd-plugin/op_api/lib/libcust_opapi.so")
            extensions = list(package.glob("_C_ascend.*.so"))
            if len(extensions) != 1:
                raise ValueError(f"Expected one AFD extension under {package}")
            expected += extensions
    for path in expected:
        if found.get(path.resolve()) != digest(path):
            raise ValueError(f"The expected library was not mapped: {path}")
    print(f"Verified mapped native libraries for {group} ({len(maps['processes'])} processes).")


if __name__ == "__main__":
    main()
