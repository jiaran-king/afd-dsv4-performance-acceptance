#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/environment.sh"
if [[ -n "${CASE_RUN_DIR:-}" ]]; then
    exec > >(tee "$CASE_RUN_DIR/prepare.log") 2>&1
fi

value() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["runtime"][sys.argv[2]])' "$case_dir/case.json" "$1"
}
activate_cann

mkdir -p "$runtime"
afd="$runtime/afd-plugin"
afd_commit=$(value afd)
afd_source=$(value afd_source)
afd_version=$(value afd_package_version)
cached_commit=
if [[ -e "$afd/.git" ]]; then
    cached_commit=$(git -C "$afd" rev-parse --verify HEAD 2>/dev/null) || cached_commit=
fi
if [[ "$cached_commit" != "$afd_commit" ]]; then
    staging=$(mktemp -d "$runtime/afd.XXXXXX")
    trap 'rm -rf -- "$staging"' EXIT
    mkdir "$staging/source"
    git -C "$staging/source" init -q
    git -C "$staging/source" fetch --depth 1 "$afd_source" "$afd_commit"
    git -C "$staging/source" checkout --detach FETCH_HEAD
    test "$(git -C "$staging/source" rev-parse HEAD)" = "$afd_commit"
    if [[ -e "$afd" || -L "$afd" ]]; then
        mv -- "$afd" "$staging/previous"
    fi
    mv -- "$staging/source" "$afd"
    rm -rf -- "$staging"
    trap - EXIT
fi

overlay="$runtime/vllm-ascend-cws"
for patch in "$case_dir"/patches/*.patch; do
    python3 -B - "$case_dir/case.json" "$patch" <<'PY'
import hashlib, json, sys
from pathlib import Path
path = Path(sys.argv[2])
expected = json.loads(Path(sys.argv[1]).read_text())["runtime"]["patches"][path.name]
if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
    raise SystemExit(f"Patch checksum does not match case lock: {path.name}")
PY
done
stack_key=$(python3 -B "$root/scripts/runtime_state.py" \
    "$VLLM_SOURCE" "$ASCEND_SOURCE" "$CANN_ROOT" "$case_dir/case.json" "${CANN_3RD_LIB_PATH:-}")
bash "$root/scripts/prepare-cws-overlay.sh" "$ASCEND_SOURCE" "$runtime" "$case_dir/patches" "$stack_key"

export PYTHONPATH="$overlay:$VLLM_SOURCE:${PYTHONPATH:-}"
cws_origin=site
if [[ -z "${CWS_VENDOR_DIR:-}" ]]; then
    cws_origin=built
    CWS_VENDOR_DIR="$runtime/cws-native/vendors/cws32k_transformer"
    cws_key="$runtime/cws-native/.stack-key"
    if [[ -z "$stack_key" || ! -s "$cws_key" || "$(<"$cws_key")" != "$stack_key" ||
          ! -s "$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so" ]]; then
        rm -rf -- "$runtime/cws-native" "$overlay/csrc/build" "$overlay/csrc/build_out"
        (
            cd "$overlay/csrc"
            bash build.sh --pkg --ops=compressor,sparse_attn_sharedkv --soc=ascend910_93 --vendor_name=cws32k -j8 \
                --cann_3rd_lib_path="${CANN_3RD_LIB_PATH:-$overlay/csrc/third_party}"
            shopt -s nullglob
            installers=(build/cann-ops-transformer*.run)
            if [[ ${#installers[@]} -ne 1 ]]; then
                echo "Expected one CWS installer in $PWD/build" >&2
                exit 1
            fi
            mkdir -p "$runtime/cws-native"
            bash "${installers[0]}" --quiet --install-path="$runtime/cws-native"
        )
        test -s "$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so"
        printf '%s\n' "$stack_key" > "$cws_key"
    fi
fi
cws_library="$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so"
if [[ ! -s "$cws_library" ]]; then
    printf 'CWS library is missing or empty: %s\n' "$cws_library" >&2
    exit 1
fi
CWS_VENDOR_DIR=$(cd -- "$CWS_VENDOR_DIR" && pwd -P)
printf '%s\n' "$CWS_VENDOR_DIR" > "$runtime/cws-vendor.path"
sha256sum "$cws_library" | cut -d ' ' -f 1 > "$runtime/cws-vendor.sha256"
staging=$(mktemp -d "$runtime/skill.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT
skill_scripts=.agents/skills/deploy-dsv4-flash-async/scripts
git -C "$afd" archive "$afd_commit" "$skill_scripts" | tar -C "$staging" -xf -
python3 -B "$root/scripts/prepare-runtime.py" "$staging/$skill_scripts" "$staging/scripts"
rm -rf -- "$skill_dir"
mv -- "$staging/scripts" "$skill_dir"
rm -rf -- "$staging"
trap - EXIT

# CANN deletes temporary kernel files during compilation. Keep that work on
# the P container's local disk and publish only the installed wheel.
extension="afd_plugin/_C_ascend$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"
opapi=afd_plugin/_cann_ops_custom/vendors/afd-plugin/op_api/lib/libcust_opapi.so
if [[ -z "$stack_key" || ! -s "$afd_install/.stack-key" || "$(<"$afd_install/.stack-key")" != "$stack_key" ||
      ! -s "$afd_install/.source-commit" || "$(<"$afd_install/.source-commit")" != "$afd_commit" ||
      ! -s "$afd_install/$extension" || ! -s "$afd_install/$opapi" ]]; then
    build=$(mktemp -d /tmp/afd-build.XXXXXX)
    staging=$(mktemp -d "$runtime/afd-install.XXXXXX")
    trap 'rm -rf -- "$build" "$staging"' EXIT
    mkdir "$build/source"
    git -C "$afd" archive "$afd_commit" | tar -C "$build/source" -xf -
    (
        cd "$build/source"
        SETUPTOOLS_SCM_PRETEND_VERSION_FOR_VLLM_AFD_PLUGIN="$afd_version" \
            SOC_VERSION=910c AFD_BUILD_ASCEND_OPS=1 TMPDIR="$build" \
            python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir "$build" .
    )
    wheels=("$build"/vllm_afd_plugin-*.whl)
    [[ "${#wheels[@]}" -eq 1 && -f "${wheels[0]}" ]]
    python3 -m pip install --no-index --no-deps --target "$staging" "${wheels[0]}"
    test -s "$staging/$extension"
    test -s "$staging/$opapi"
    printf '%s\n' "$afd_commit" > "$staging/.source-commit"
    printf '%s\n' "$stack_key" > "$staging/.stack-key"
    rm -rf -- "$afd_install"
    mv -- "$staging" "$afd_install"
    rm -rf -- "$build"
    trap - EXIT
else
    printf 'Using the prepared AFD installation for %s\n' "$afd_commit"
fi

# The pinned wheel omits dynamically imported namespace packages. Keep the
# wheel's native libraries and registration, and use the pinned Python tree.
git -C "$afd" archive "$afd_commit" afd_plugin | tar -C "$afd_install" -xf -

validator=afd_plugin/compat/npu/feature_validation.py
if ! cmp -s "$afd_install/$validator" <(git -C "$afd" show "$afd_commit:$validator"); then
    printf 'The prepared AFD validator differs from commit %s.\n' "$afd_commit" >&2
    exit 1
fi

sha256sum "$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so" \
    "$afd_install/$validator" \
    "$afd_install/$opapi"

if [[ -n "${CASE_RUN_DIR:-}" ]]; then
    python3 -B - "$CASE_RUN_DIR/prepared-runtime.json" "$runtime" \
        "$afd_commit" "$afd_source" "$afd_version" "$stack_key" "$cws_origin" <<'PY'
import json
import sys
from pathlib import Path

output, runtime, afd, afd_source, afd_version, key, origin = sys.argv[1:]
runtime = Path(runtime)
record = {
    "afd": afd,
    "afd_source": afd_source,
    "afd_package_version": afd_version,
    "build_key": key or None,
    "cws": {
        "origin": origin,
        "vendor_path": (runtime / "cws-vendor.path").read_text().strip(),
        "opapi_sha256": (runtime / "cws-vendor.sha256").read_text().strip(),
    },
}
Path(output).write_text(json.dumps(record, indent=2) + "\n")
PY
fi
