#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/environment.sh"

group=${1:?Specify baseline or afd12}
p_run=${2:?Specify the running group directory}
workload=${3:?Specify frozen requests.jsonl}
out=${4:?Specify the output directory}

case "$group" in
    baseline) logs=(p0 p1); ports=(7100 7101) ;;
    afd12) logs=(prefill_attention_node0 prefill_ffn_node0); ports=(7100) ;;
    *) echo "Unknown run group: $group" >&2; exit 2 ;;
esac
mkdir "$out"
trap 'printf "%s\n" "$?" > "$out/exit-code"' EXIT
endpoints=()
for port in "${ports[@]}"; do
    endpoints+=(--endpoint "http://127.0.0.1:$port")
done

prefill_metrics() {
    local boundary=$1 port path
    for port in "${ports[@]}"; do
        path="$out/$boundary-$port.metrics"
        if ! curl --noproxy '*' -fsS --max-time 15 "http://127.0.0.1:$port/metrics" > "$path"; then
            rm -f -- "$path"
        fi
    done
}

prefill_metrics pre
offsets=()
for role in "${logs[@]}"; do
    offsets+=("$(stat -c %s "$p_run/$role.log" || true)")
done

status=0
python3 -B "$root/scripts/replay.py" "${endpoints[@]}" \
    --workload "$workload" --out "$out/client" --order fixed || status=$?
prefill_metrics post
for i in "${!logs[@]}"; do
    if [[ -n "${offsets[i]}" ]]; then
        tail -c "+$((offsets[i] + 1))" "$p_run/${logs[i]}.log" > "$out/${logs[i]}-window.log" || true
    fi
done
exit "$status"
