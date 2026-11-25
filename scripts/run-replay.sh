#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
source "$root/scripts/environment.sh"
name=${1:?Specify an unused run name}
p_run=${2:?Specify the live P run directory}
d_run=${3:?Specify the live D run directory}
workload=${4:?Specify frozen requests.jsonl}
mode=${5:?Specify baseline or afd}
order=${6:-ready}

case "$mode" in
    baseline) logs=(p0 p1); ports=(7100 7101) ;;
    afd) logs=(prefill_attention_node0 prefill_ffn_node0); ports=(7100) ;;
    *) echo "Unknown mode: $mode" >&2; exit 2 ;;
esac

out="${CASE_RUN_DIR:?Set CASE_RUN_DIR}/$name"
mkdir "$out"
trap 'printf "%s\n" "$?" > "$out/exit-code"' EXIT

prefill_metrics() {
    local boundary=$1 port path
    for port in "${ports[@]}"; do
        path="$out/$boundary-$port.metrics"
        if ! curl -fsS --max-time 15 "http://$P_NODE_IP:$port/metrics" > "$path"; then
            rm -f -- "$path"
        fi
    done
}

prefill_metrics pre
curl -fsS --max-time 15 "http://$D_NODE_IP:7100/metrics" > "$out/pre-d.metrics"
d_offset=$(stat -c %s "$d_run/decode.log")
printf '%s\n' "$d_offset" > "$out/decode-start-byte-offset"
offsets=()
for role in "${logs[@]}"; do
    offsets+=("$(stat -c %s "$p_run/$role.log" || true)")
done

set +e
python3 -B "$root/scripts/replay.py" --proxy "http://$P_NODE_IP:8000" \
    --workload "$workload" --out "$out/client" --order "$order"
status=$?
set -e

prefill_metrics post
curl -fsS --max-time 15 "http://$D_NODE_IP:7100/metrics" > "$out/post-d.metrics" || true
PYTHONPATH="$root/scripts${PYTHONPATH:+:$PYTHONPATH}" python3 -B - "$d_run/decode.log" "$d_offset" "$out" "$status" <<'PY'
from pathlib import Path
import sys

from audit import snapshot_decode_log

source, offset, run, status = sys.argv[1:]
snapshot_decode_log(Path(source), int(offset), Path(run), status == "0")
PY
for i in "${!logs[@]}"; do
    role=${logs[i]}
    if [[ -n "${offsets[i]}" ]]; then
        tail -c "+$((offsets[i] + 1))" "$p_run/$role.log" > "$out/$role-window.log" || true
    fi
done
exit "$status"
