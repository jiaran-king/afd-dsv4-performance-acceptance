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
    afd = runtime / "afd-install/afd_plugin"
    found = {Path(key).resolve(): sha for key, sha in maps["library_sha256"].items()}
    if group == "baseline" and any("/afd_plugin/" in str(path) for path in found):
        raise ValueError("The baseline mapped an AFD library")
    if group != "baseline":
        extension = f"_C_ascend{sysconfig.get_config_var('EXT_SUFFIX')}"
        for path in (afd / "_cann_ops_custom/vendors/afd-plugin/op_api/lib/libcust_opapi.so",
                     afd / extension):
            if found.get(path.resolve()) != digest(path):
                raise ValueError(f"The expected library was not mapped: {path}")
    print(f"Verified mapped native libraries for {group} ({len(maps['processes'])} processes).")


if __name__ == "__main__":
    main()
