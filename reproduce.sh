#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "$0")" && pwd -P)
usage() {
    printf '%s\n' 'Usage: ./reproduce.sh --site site.env [--prepare-only|--smoke-only|--gsm8k]'
}
if [[ ${1:-} == --help ]]; then usage; exit 0; fi
if [[ ${1:-} != --site || $# -lt 2 || $# -gt 3 ]]; then usage >&2; exit 2; fi
mode=${3:-}
case "$mode" in
    ""|--prepare-only|--smoke-only|--gsm8k) ;;
    *) usage >&2; exit 2 ;;
esac

export SITE_FILE
SITE_FILE=$(cd -- "$(dirname -- "$2")" && printf '%s/%s\n' "$(pwd -P)" "$(basename -- "$2")")
source "$root/scripts/environment.sh"
activate_cann
mkdir -p "$root/runs"
export CASE_RUN_DIR="$root/runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
run=$CASE_RUN_DIR
lock="$root/runs/.active"
group=

stop_group() {
    case "$group" in
        baseline) python3 -B "$root/scripts/stop.py" "$run/baseline-p" p0 p1 --wait 45 ;;
        afd12|afd8)
            python3 -B "$root/scripts/stop.py" "$run/$group-p" \
                prefill_attention_node0 prefill_ffn_node0 --wait 45
            ;;
    esac || return
    group=
}

if ! mkdir "$lock"; then
    printf 'Another run owns %s.\n' "$lock" >&2
    if [[ -r "$lock/run-dir" ]]; then cat "$lock/run-dir" >&2; fi
    exit 1
fi
finish() {
    local status=$?
    trap - EXIT
    if stop_group; then
        rm -f -- "$lock/run-dir"
        rmdir -- "$lock" || status=1
    else
        printf 'Check the processes recorded at %s before a fresh run.\n' "$run" >&2
        status=1
    fi
    exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '%s\n' "$run" > "$lock/run-dir"
mkdir "$run"
printf 'Artifacts are in %s\n' "$run"

ports=()
if [[ "$mode" != --prepare-only ]]; then
    ports=(7100 7101 12321 12421 1239)
fi
python3 -B "$root/scripts/preflight.py" "$P_MODEL_DIR" "$P_DEVICES" \
    "$VLLM_SOURCE" "$ASCEND_SOURCE" "$CANN_ROOT" "$P_NODE_IP" "$run/preflight.json" "${ports[@]}"
if [[ "$mode" != --gsm8k ]]; then
    archive=()
    if [[ -n ${WORKLOAD_ARCHIVE:-} ]]; then archive=(--archive "$WORKLOAD_ARCHIVE"); fi
    python3 -B "$root/scripts/prepare-workload.py" "${archive[@]}"
else
    python3 -B "$root/scripts/gsm8k.py" prepare
fi
bash "$root/scripts/prepare-runtime.sh"
if [[ "$mode" == --prepare-only ]]; then exit 0; fi

arms=(baseline afd12 afd8)
if [[ "$mode" == --gsm8k || "$mode" == --smoke-only ]]; then arms=(baseline afd12); fi
for arm in "${arms[@]}"; do
    group=$arm
    case "$arm" in
        baseline)
            bash "$root/scripts/launch.sh" p0 baseline-p
            bash "$root/scripts/launch.sh" p1 baseline-p
            ;;
        afd12) bash "$root/scripts/launch.sh" afd afd12-p 12a4f ;;
        afd8) bash "$root/scripts/launch.sh" afd afd8-p 8a8f ;;
    esac
    bash "$root/scripts/run-group.sh" "$arm" "$mode"
    stop_group
done

case "$mode" in
    --gsm8k)
        python3 -B "$root/scripts/gsm8k.py" compare "$run"
        ;;
    --smoke-only) ;;
    *)
        python3 -B "$root/scripts/audit.py" "$runtime/workload/formal-candidate/requests.jsonl" \
            "$run/baseline-formal" "$run/afd12-formal" --case "$case_dir/case.json" \
            --ffn-graph "$run/afd12-p/graph-counters" --flexible-ratio "$run/afd8-p" \
            --attention-layout "$run/afd12-p/attention-layout.json" \
            --environment "$run" --output "$run/acceptance.json"
        ;;
esac
