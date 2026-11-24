#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/environment.sh"
if [[ -n "${CASE_RUN_DIR:-}" ]]; then
    exec > >(tee "$CASE_RUN_DIR/prepare.log") 2>&1
fi

value() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["runtime"][sys.argv[2]])' "$case_dir/case.json" "$1"
}
test "$(git -C "$VLLM_SOURCE" rev-parse HEAD)" = "$(value vllm)"
test "$(git -C "$ASCEND_SOURCE" rev-parse HEAD)" = "$(value vllm_ascend)"
test -r "$CANN_ROOT/set_env.sh"
set +u
source "$CANN_ROOT/set_env.sh"
set -u

mkdir -p "$runtime"
afd="$runtime/afd-plugin"
afd_commit=$(value afd)
if [[ ! -d "$afd/.git" ]]; then
    staging=$(mktemp -d "$runtime/afd.XXXXXX")
    trap 'rm -rf -- "$staging"' EXIT
    git -C "$staging" init -q
    git -C "$staging" fetch --depth 1 https://github.com/vllm-project/afd-plugin.git "$afd_commit"
    git -C "$staging" checkout --detach FETCH_HEAD
    mv -- "$staging" "$afd"
    trap - EXIT
fi
test "$(git -C "$afd" rev-parse HEAD)" = "$afd_commit"

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
bash "$root/scripts/prepare-cws-overlay.sh" "$ASCEND_SOURCE" "$runtime" "$case_dir/patches"

export PYTHONPATH="$overlay:$VLLM_SOURCE:${PYTHONPATH:-}"
if [[ -z "${CWS_VENDOR_DIR:-}" ]]; then
    CWS_VENDOR_DIR="$runtime/cws-native/vendors/cws32k_transformer"
    if [[ ! -f "$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so" ]]; then
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
    fi
else
    supplied_hash=$(sha256sum "$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so" | cut -d ' ' -f 1)
    test "$supplied_hash" = "$(value cws_reference_opapi_sha256)" || {
        echo "The supplied CWS vendor does not match the reference library hash." >&2
        exit 1
    }
fi
test -s "$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so"
test "$(basename -- "$CWS_VENDOR_DIR")" = cws32k_transformer
printf '%s\n' "$CWS_VENDOR_DIR" > "$runtime/cws-vendor.path"
if [[ ! -d "$skill_dir" ]]; then
    staging=$(mktemp -d "$runtime/skill.XXXXXX")
    trap 'rm -rf -- "$staging"' EXIT
    python3 -B "$root/scripts/prepare-runtime.py" \
        "$afd/.agents/skills/deploy-dsv4-flash-async/scripts" "$staging/scripts"
    mv -- "$staging/scripts" "$skill_dir"
    rmdir "$staging"
    trap - EXIT
fi

# CANN deletes temporary kernel files during compilation. Keep that work on
# the P container's local disk and publish only the installed wheel.
extension="afd_plugin/_C_ascend$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"
opapi=afd_plugin/_cann_ops_custom/vendors/afd-plugin/op_api/lib/libcust_opapi.so
if [[ ! -s "$afd_install/.source-commit" || "$(<"$afd_install/.source-commit")" != "$afd_commit" ||
      ! -s "$afd_install/$extension" || ! -s "$afd_install/$opapi" ]]; then
    build=$(mktemp -d /tmp/afd-build.XXXXXX)
    staging=$(mktemp -d "$runtime/afd-install.XXXXXX")
    trap 'rm -rf -- "$build" "$staging"' EXIT
    mkdir "$build/source"
    git -C "$afd" archive "$afd_commit" | tar -C "$build/source" -xf -
    (
        cd "$build/source"
        SETUPTOOLS_SCM_PRETEND_VERSION_FOR_VLLM_AFD_PLUGIN=0.30.0rc1.dev11+gbc80959 \
            SOC_VERSION=910c AFD_BUILD_ASCEND_OPS=1 TMPDIR="$build" \
            python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir "$build" .
    )
    wheels=("$build"/vllm_afd_plugin-*.whl)
    [[ "${#wheels[@]}" -eq 1 && -f "${wheels[0]}" ]]
    python3 -m pip install --no-index --no-deps --target "$staging" "${wheels[0]}"
    test -s "$staging/$extension"
    test -s "$staging/$opapi"
    printf '%s\n' "$afd_commit" > "$staging/.source-commit"
    rm -rf -- "$afd_install"
    mv -- "$staging" "$afd_install"
    rm -rf -- "$build"
    trap - EXIT
else
    printf 'Using the prepared AFD installation for %s\n' "$afd_commit"
fi

# Reproduce the A-only source copy used by the shared-expert DP run.
staging=$(mktemp -d "$runtime/afd-attention.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT
tar -C "$afd_install" --exclude=__pycache__ -cf - afd_plugin | tar -C "$staging" -xf -
GIT_CEILING_DIRECTORIES="$runtime" git -C "$staging" apply "$case_dir/patches/afd-shared-expert-dp.patch"
validator="$staging/afd_plugin/compat/npu/feature_validation.py"
test "$(sha256sum "$validator" | cut -d ' ' -f 1)" = "$(value afd_attention_validation_sha256)"
rm -rf -- "$attention_source"
mv -- "$staging" "$attention_source"
trap - EXIT

sha256sum "$CWS_VENDOR_DIR/op_api/lib/libcust_opapi.so" \
    "$attention_source/afd_plugin/compat/npu/feature_validation.py" \
    "$afd_install/$opapi"
