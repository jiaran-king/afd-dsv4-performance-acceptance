#!/usr/bin/env bash
set -euo pipefail

ascend_source=$1
runtime=$(cd -- "$2" && pwd -P)
patches=$3
stack_key=${4:-}
overlay="$runtime/vllm-ascend-cws"
cws_patch="$patches/cws-v030-mrv2.patch"
kv_patch="$patches/cws-pd-logical-pages.patch"

apply_patch() {
    local tree=$1
    shift
    GIT_CEILING_DIRECTORIES="$runtime" git -C "$tree" apply --whitespace=nowarn --exclude='tests/*' "$@"
}

verified() {
    apply_patch "$1" --check --reverse "$kv_patch" &&
        apply_patch "$1" --check --reverse "$cws_patch"
}

if [[ -n "$stack_key" && -s "$overlay/.stack-key" && "$(<"$overlay/.stack-key")" == "$stack_key" ]] \
    && verified "$overlay" >/dev/null 2>&1; then
    printf 'Verified cached CWS and Mooncake KV export patches in %s\n' "$overlay"
    exit 0
fi

staging=$(mktemp -d "$runtime/cws.XXXXXX")
trap 'rm -rf -- "$staging"' EXIT
mkdir "$staging/source"
tar -C "$ascend_source" --exclude=.git --exclude=__pycache__ \
    --exclude=./csrc/build --exclude=./csrc/build_out -cf - . | tar -C "$staging/source" -xf -
for patch in "$cws_patch" "$kv_patch"; do
    if apply_patch "$staging/source" --check --reverse "$patch" >/dev/null 2>&1; then
        printf 'Site source includes %s\n' "${patch##*/}"
    elif ! apply_patch "$staging/source" "$patch"; then
        printf 'Cannot apply %s to the site vLLM-Ascend source at %s.\n' "${patch##*/}" "$ascend_source" >&2
        exit 1
    fi
done
verified "$staging/source"
printf '%s\n' "$stack_key" > "$staging/source/.stack-key"

if [[ -e "$overlay" ]]; then
    mv -- "$overlay" "$staging/previous-source"
fi
mv -- "$staging/source" "$overlay"
printf 'Applied and verified CWS and Mooncake KV export patches in %s\n' "$overlay"
