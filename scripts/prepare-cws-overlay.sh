#!/usr/bin/env bash
set -euo pipefail

ascend_source=$1
runtime=$(cd -- "$2" && pwd -P)
patches=$3
overlay="$runtime/vllm-ascend-cws"
cws_patch="$patches/cws-v030-mrv2.patch"
kv_patch="$patches/cws-pd-logical-pages.patch"

apply_patch() {
    local tree=$1
    shift
    GIT_CEILING_DIRECTORIES="$runtime" git -C "$tree" apply --whitespace=nowarn "$@"
}

verified() {
    apply_patch "$1" --check --reverse "$kv_patch" &&
        apply_patch "$1" --check --reverse "$cws_patch"
}

if [[ -d "$overlay" ]] && verified "$overlay" >/dev/null 2>&1; then
    printf 'Verified cached CWS and Mooncake KV export patches in %s\n' "$overlay"
    exit 0
fi

staging=$(mktemp -d "$runtime/cws.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT
mkdir "$staging/source"
tar -C "$ascend_source" --exclude=.git --exclude=__pycache__ \
    --exclude=./csrc/build --exclude=./csrc/build_out -cf - . | tar -C "$staging/source" -xf -
apply_patch "$staging/source" "$cws_patch"
apply_patch "$staging/source" "$kv_patch"
verified "$staging/source"

# An existing installer output can have been built from the unpatched cache.
# Invalidate it before publishing the verified source so retries rebuild it.
if [[ -e "$runtime/cws-native" ]]; then
    mv -- "$runtime/cws-native" "$staging/previous-native"
fi
if [[ -e "$overlay" ]]; then
    mv -- "$overlay" "$staging/previous-source"
fi
mv -- "$staging/source" "$overlay"
printf 'Applied and verified CWS and Mooncake KV export patches in %s\n' "$overlay"
