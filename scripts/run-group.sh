#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/environment.sh"

run=${CASE_RUN_DIR:?Set CASE_RUN_DIR}
group=${1:?Specify baseline, afd12 or afd8}
p_run="$run/$group-p"
d_run="$run/$group-d"
workload="$runtime/workload"
smoke_data="$runtime/afd-plugin/.agents/skills/deploy-dsv4-flash-async/assets/workloads/formal_0_1_2_vllm_bench.jsonl.gz"

healthy() {
    curl -fsS --max-time 3 "$1" >/dev/null 2>&1
}

ready() {
    healthy "http://$D_NODE_IP:7100/health" &&
    healthy "http://$P_NODE_IP:7100/health" || return 1
    if [[ "$group" == baseline ]]; then
        healthy "http://$P_NODE_IP:7101/health"
    fi
}

wait_for_startup() {
    if (( SECONDS >= deadline )); then
        echo "Startup timed out waiting for $1. See $p_run and $d_run." >&2
        exit 1
    fi
    sleep 5
}

deadline=$((SECONDS + ${STARTUP_TIMEOUT_SECONDS:-1200}))
until ready; do
    wait_for_startup "P/D HTTP health"
done

smoke() {
    local port=$1 output=$2
    shift 2
    python3 -B "$root/scripts/smoke.py" --proxy "$P_NODE_IP:$port" --decoder "$D_NODE_IP:7100" \
        --decode-log "$d_run/decode.log" --output "$output" "$@"
}

probe() {
    local port=$1 label=$2
    if [[ "$group" == baseline ]]; then
        smoke "$port" "$p_run/$label-short"
    else
        local attempt=1 startup_dir="$p_run/$label-startup-1"
        until smoke "$port" "$startup_dir"; do
            # A completed request with a failed KV check is an acceptance failure.
            [[ ! -f "$startup_dir/result.json" ]] || return 1
            wait_for_startup "the short AFD PD request"
            attempt=$((attempt + 1))
            startup_dir="$p_run/$label-startup-$attempt"
        done
        mv -- "$startup_dir" "$p_run/$label-short"
    fi
    smoke "$port" "$p_run/$label-long" --dataset "$smoke_data" --min-prompt-tokens 32000
}

if [[ "$group" == baseline ]]; then
    probe 8001 p0
    probe 8002 p1
else
    probe 8000 pd
fi
python3 -B "$root/scripts/runtime-maps.py" "$p_run" > "$p_run/native-maps.json"
python3 -B "$root/scripts/verify-native.py" "$p_run/native-maps.json" "$runtime" "$group"

if [[ "$group" == afd12 ]]; then
    python3 -B "$root/scripts/shared_expert_dp.py" "$p_run/attention-ranks" \
        "$afd_install/afd_plugin/compat/npu/feature_validation.py" > "$p_run/attention-layout.json"
fi

if [[ "$group" == afd8 ]]; then
    exit 0
fi

warmup() {
    python3 -B "$root/scripts/replay.py" --proxy "http://$P_NODE_IP:8000" \
        --workload "$workload/warmup/requests.jsonl" --out "$run/$1"
}

measure() {
    bash "$root/scripts/run-replay.sh" "$1" "$p_run" "$d_run" "$workload/$2/requests.jsonl" "$3" fixed
}

warmup "$group-warmup"
if [[ "$group" == afd12 ]]; then
    python3 -B "$root/scripts/graph_replay.py" "$p_run/graph-counters" before
    measure "$group-formal" formal-candidate afd
    python3 -B "$root/scripts/graph_replay.py" "$p_run/graph-counters" after
else
    measure "$group-formal" formal-candidate baseline
fi
