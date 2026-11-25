#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/environment.sh"

run=${CASE_RUN_DIR:?Set CASE_RUN_DIR}
group=${1:?Specify baseline, afd12 or afd8}
mode=${2:-}
p_run="$run/$group-p"
workload="$runtime/workload"
smoke_data="$workload/formal-candidate/requests.jsonl"

healthy() {
    curl --noproxy '*' -fsS --max-time 3 "http://127.0.0.1:$1/health" >/dev/null 2>&1
}

# The second HTTP frontend serves the baseline. AFD FFN uses the connector loop.
deadline=$((SECONDS + ${STARTUP_TIMEOUT_SECONDS:-1200}))
until healthy 7100 && { [[ "$group" != baseline ]] || healthy 7101; }; do
    if (( SECONDS >= deadline )); then
        printf 'Timed out waiting for %s. See %s.\n' "$group" "$p_run" >&2
        exit 1
    fi
    for pid_file in "$p_run"/pids/*.pid; do
        if [[ -s "$pid_file" ]] && ! kill -0 "$(<"$pid_file")" 2>/dev/null; then
            printf 'Service exited during startup. See %s.\n' "$p_run" >&2
            exit 1
        fi
    done
    sleep 5
done

endpoints=(--endpoint http://127.0.0.1:7100)
if [[ "$group" == baseline ]]; then endpoints+=(--endpoint http://127.0.0.1:7101); fi
if [[ "$mode" == --gsm8k ]]; then
    dataset=()
    if [[ -n ${GSM8K_FILE:-} ]]; then dataset=(--dataset "$GSM8K_FILE"); fi
    python3 -B "$root/scripts/gsm8k.py" run "${dataset[@]}" "${endpoints[@]}" \
        --out "$run/$group-gsm8k"
    exit 0
fi

probe() {
    local port=$1 output=$2
    shift 2
    python3 -B "$root/scripts/smoke.py" --endpoint "http://127.0.0.1:$port" \
        --dataset "$smoke_data" --output "$output" "$@"
}

graph="$p_run/graph-counters"
if [[ "$mode" == --smoke-only && "$group" == afd12 ]]; then
    python3 -B "$root/scripts/graph_replay.py" "$graph" before
fi
if [[ "$group" == baseline ]]; then
    probe 7100 "$p_run/p0-short" --max-prompt-tokens 4096
    probe 7101 "$p_run/p1-short" --max-prompt-tokens 4096
    probe 7100 "$p_run/p0-long" --min-prompt-tokens 32000
    probe 7101 "$p_run/p1-long" --min-prompt-tokens 32000
else
    probe 7100 "$p_run/short" --max-prompt-tokens 4096
    probe 7100 "$p_run/long" --min-prompt-tokens 32000
fi

python3 -B "$root/scripts/runtime-maps.py" "$p_run" > "$p_run/native-maps.json"
python3 -B "$root/scripts/verify-native.py" "$p_run/native-maps.json" "$runtime" "$group"
if [[ "$group" == afd12 ]]; then
    python3 -B "$root/scripts/shared_expert_dp.py" "$p_run/attention-ranks" \
        "$afd_install/afd_plugin/compat/npu/feature_validation.py" > "$p_run/attention-layout.json"
fi

if [[ "$mode" == --smoke-only && "$group" == afd12 ]]; then
    python3 -B "$root/scripts/graph_replay.py" "$graph" after \
        --verify "$p_run/short/result.json" "$p_run/long/result.json" | tee "$p_run/ffn-full-replay.json"
fi
if [[ "$mode" == --smoke-only || "$group" == afd8 ]]; then exit 0; fi

python3 -B "$root/scripts/replay.py" "${endpoints[@]}" \
    --workload "$workload/warmup/requests.jsonl" --out "$run/$group-warmup" --order fixed
if [[ "$group" == afd12 ]]; then
    python3 -B "$root/scripts/graph_replay.py" "$graph" before
fi
bash "$root/scripts/run-replay.sh" "$group" "$p_run" "$smoke_data" "$run/$group-formal"
if [[ "$group" == afd12 ]]; then
    python3 -B "$root/scripts/graph_replay.py" "$graph" after
fi
