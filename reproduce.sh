#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "$0")" && pwd -P)
usage() {
    printf '%s\n' "Usage: ./reproduce.sh --site site.env [--prepare-only]"
    printf '%s\n' "       ./reproduce.sh --site site.env --resume-afd <run-id>"
}

if [[ ${1:-} == --help ]]; then usage; exit 0; fi
if [[ ${1:-} != --site || $# -lt 2 ]]; then usage >&2; exit 2; fi
mode=${3:-}
case "$mode" in
    ""|--prepare-only) [[ $# -le 3 ]] || { usage >&2; exit 2; } ;;
    --resume-afd) [[ $# -eq 4 && "$4" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9]+$ ]] || { usage >&2; exit 2; } ;;
    *) usage >&2; exit 2 ;;
esac
site=$(cd -- "$(dirname -- "$2")" && printf '%s/%s\n' "$(pwd -P)" "$(basename -- "$2")")
source "$site"

shared=${SHARED_ROOT:-$root}
case "$shared" in /*) ;; *) echo "SHARED_ROOT must be absolute inside both containers." >&2; exit 2 ;; esac
default_site="$shared/site.env"
if [[ "${shared%/}" == "$root" ]]; then default_site=$site; fi
remote_site=${SITE_REMOTE_FILE:-$default_site}
run="$shared/runs/$(date -u +%Y%m%dT%H%M%SZ)-$$"
baseline_run=$run
arms=(baseline afd12 afd8)
if [[ "$mode" == --resume-afd ]]; then
    baseline_run="$shared/runs/$4"
    arms=(afd12 afd8)
fi
site_runner=${NODE_EXEC:-}
group=

node() {
    local role=$1 remote_args ssh_target container
    shift
    if [[ -n "$site_runner" ]]; then
        "$site_runner" "$role" "$@"
        return
    fi
    case "$role" in
        P) ssh_target=${P_SSH:-}; container=${P_CONTAINER:-} ;;
        D) ssh_target=${D_SSH:?Set D_SSH or NODE_EXEC}; container=${D_CONTAINER:-} ;;
        *) return 2 ;;
    esac
    if [[ -n "$container" ]]; then
        set -- docker exec "$container" "$@"
    fi
    if [[ -n "$ssh_target" ]]; then
        printf -v remote_args '%q ' "$@"
        ssh -- "$ssh_target" "$remote_args"
    else
        "$@"
    fi
}

run_script() {
    local role=$1 script=$2
    shift 2
    node "$role" env "SITE_FILE=$remote_site" "CASE_RUN_DIR=$run" bash "$shared/scripts/$script" "$@"
}

stop_on() {
    local role=$1 dir=$2
    shift 2
    if node "$role" test -d "$dir"; then
        node "$role" python3 -B "$shared/scripts/stop.py" "$dir" "$@" --wait 45
    fi
}

stop_group() {
    local failed=0
    case "$group" in
        "") return 0 ;;
        baseline)
            stop_on P "$run/baseline-p0-proxy" proxy-p0 || failed=1
            stop_on P "$run/baseline-p1-proxy" proxy-p1 || failed=1
            stop_on P "$run/baseline-proxy" proxy || failed=1
            stop_on P "$run/baseline-p" p0 p1 || failed=1
            ;;
        afd12|afd8)
            stop_on P "$run/$group-proxy" proxy-afd || failed=1
            stop_on P "$run/$group-p" prefill_attention_node0 prefill_ffn_node0 || failed=1
            ;;
    esac
    stop_on D "$run/$group-d" decode || failed=1
    if (( failed )); then return 1; fi
    group=
}

node P test -r "$shared/reproduce.sh"
node D test -r "$shared/reproduce.sh"
node P test -r "$remote_site"
node D test -r "$remote_site"
node P mkdir -p "$shared/runs"
lock="$shared/runs/.active"

show_run_pids() {
    printf 'Run directory: %s\nPID files: %s/*/pids/*.pid\n' "$1" "$1" >&2
}

if ! node P mkdir "$lock"; then
    printf 'Cannot acquire the run lock at %s.\n' "$lock" >&2
    if owner=$(node P cat "$lock/run-dir" 2>/dev/null) && [[ -n "$owner" ]]; then
        show_run_pids "$owner"
    else
        printf 'Previous run PID files: %s/runs/*/*/pids/*.pid\n' "$shared" >&2
    fi
    exit 1
fi
finish() {
    status=$?
    trap - EXIT
    if stop_group; then
        node P bash -c 'rm -f -- "$1/run-dir" && rmdir -- "$1"' bash "$lock" || status=1
    else
        printf 'Cleanup needs attention. The run lock is at %s.\n' "$lock" >&2
        show_run_pids "$run"
        status=1
    fi
    exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
node P bash -c 'printf "%s\n" "$2" > "$1/run-dir"' bash "$lock" "$run"
node P mkdir "$run"
node D test -d "$run"

for role in P D; do
    case "$mode:$role" in
        --prepare-only:*) ports=() ;;
        *:D) ports=(7100) ;;
        --resume-afd:P) ports=(7100 7101 8000) ;;
        :P) ports=(7100 7101 8000 8001 8002) ;;
    esac
    node "$role" env "SITE_FILE=$remote_site" bash -eu -c '
        source "$1/scripts/environment.sh"
        activate_cann
        role=$2
        output=$3
        shift 3
        case "$role" in
            P) model=$P_MODEL_DIR; devices=$P_DEVICES ;;
            D) model=$D_MODEL_DIR; devices=$D_DEVICES ;;
        esac
        exec python3 -B "$root/scripts/preflight.py" "$role" "$model" "$devices" \
            "$VLLM_SOURCE" "$ASCEND_SOURCE" "$CANN_ROOT" "$P_NODE_IP" "$D_NODE_IP" "$output" "$@"
    ' bash "$shared" "$role" "$run/$role-preflight.json" "${ports[@]+"${ports[@]}"}"
done

node P env "SITE_FILE=$remote_site" bash -eu -c '
    source "$1/scripts/environment.sh"
    if [[ -n ${WORKLOAD_ARCHIVE:-} ]]; then
        exec python3 -B "$root/scripts/prepare-workload.py" --archive "$WORKLOAD_ARCHIVE"
    fi
    exec python3 -B "$root/scripts/prepare-workload.py"
' bash "$shared"
workload="$shared/.runtime/workload/formal-candidate/requests.jsonl"
if [[ "$mode" == --resume-afd ]]; then
    for role in P D; do
        node P python3 -B "$shared/scripts/preflight.py" --compare-baseline \
            "$baseline_run/$role-preflight.json" "$run/$role-preflight.json"
    done
    node P python3 -B "$shared/scripts/audit.py" "$workload" "$baseline_run/baseline-formal" \
        --baseline-warmup "$baseline_run/baseline-warmup" --check --output "$run/baseline-audit.json" >/dev/null
fi
run_script P prepare-runtime.sh
if [[ "$mode" == --prepare-only ]]; then
    printf 'Prepared the acceptance runtime at %s\n' "$run"
    exit 0
fi
if [[ "$mode" == --resume-afd ]]; then
    node P python3 -B "$shared/scripts/verify-native.py" "$baseline_run/baseline-p/native-maps.json" "$shared/.runtime" baseline
    printf 'Reusing the verified baseline at %s\n' "$baseline_run"
fi

for arm in "${arms[@]}"; do
    group=$arm
    run_script D launch.sh decode "$arm-d" "$arm"
    case "$arm" in
        baseline)
            run_script P launch.sh p0 baseline-p
            run_script P launch.sh p1 baseline-p
            run_script P launch.sh proxy baseline-proxy
            run_script P launch.sh proxy-p0 baseline-p0-proxy
            run_script P launch.sh proxy-p1 baseline-p1-proxy
            ;;
        afd12)
            run_script P launch.sh afd afd12-p 12a4f
            run_script P launch.sh proxy-afd afd12-proxy
            ;;
        afd8)
            run_script P launch.sh afd afd8-p 8a8f
            run_script P launch.sh proxy-afd afd8-proxy
            ;;
    esac
    run_script P run-group.sh "$arm"
    stop_group
done

node P python3 -B "$shared/scripts/audit.py" "$workload" \
    "$baseline_run/baseline-formal" "$run/afd12-formal" \
    --baseline-warmup "$baseline_run/baseline-warmup" --afd-warmup "$run/afd12-warmup" \
    --ffn-graph "$run/afd12-p/graph-counters" --flexible-ratio "$run/afd8-p" \
    --attention-layout "$run/afd12-p/attention-layout.json" \
    --environment "$run" \
    --check --output "$run/acceptance.json"
printf 'Artifacts are in %s\n' "$run"
