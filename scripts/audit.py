"""Audit complete single-node replay evidence and compare two runs of a frozen load."""

import argparse
import gzip
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

from graph_replay import verify_full_replay


def queues(run):
    peaks = defaultdict(int)
    pattern = re.compile(r"(\d\d:\d\d:\d\d).*Engine\s+(\d+):.*Waiting:\s*(\d+)\s+req", re.I)
    totals = defaultdict(dict)
    for log in sorted(run.glob("*-window.log")):
        if log.name not in {"p0-window.log", "p1-window.log", "prefill_attention_node0-window.log"}:
            continue
        for when, rank, waiting in pattern.findall(log.read_text()):
            engine = f"{log.stem}:{rank}"
            peaks[engine] = max(peaks[engine], int(waiting))
            totals[when][engine] = int(waiting)
    state = {}
    series = []
    for when, samples in sorted(totals.items()):
        state.update(samples)
        series.append({"time": when, "waiting": sum(state.values())})
    return dict(peaks), series


def prefill_phases(run):
    metrics = re.compile(
        r'^vllm:request_(queue|prefill)_time_seconds_(sum|count)\{[^\n]+\}\s+([\d.eE+-]+)$', re.M
    )

    def totals(paths):
        result = defaultdict(float)
        for path in paths:
            for phase, aggregate, value in metrics.findall(path.read_text()):
                result[phase, aggregate] += float(value)
        return result

    pairs = []
    for pre in run.glob("pre-71*.metrics"):
        post = run / pre.name.replace("pre-", "post-", 1)
        if pre.stat().st_size and post.is_file() and post.stat().st_size:
            pairs.append((pre, post))
    before = totals(pre for pre, _ in pairs)
    after = totals(post for _, post in pairs)
    result = {}
    for phase in ("queue", "prefill"):
        count = after[phase, "count"] - before[phase, "count"]
        seconds = after[phase, "sum"] - before[phase, "sum"]
        if count > 0 and seconds >= 0:
            result[phase] = {"requests": int(count), "mean_ms": seconds / count * 1000}
    return result


def arrival_windows(order):
    windows = []
    for first in range(0, len(order), 100):
        block = order[first:first + 100]
        start = block[0]["send_monotonic"]
        after = first + len(block)
        end = order[after]["send_monotonic"] if after < len(order) else block[-1]["send_monotonic"] + 0.25
        completed = [row for row in order if start <= row["completed_monotonic"] < end]
        windows.append({
            "first_slot": first,
            "seconds": end - start,
            "sent": len(block),
            "completed": len(completed),
            "input_tokens_sent_per_second": sum(row["input_tokens"] for row in block) / (end - start),
            "input_tokens_completed_per_second": sum(row["input_tokens"] for row in completed) / (end - start),
            "inflight_at_end": sum(row["completed_monotonic"] >= end for row in order[:after]),
            "mean_ttft_ms": 1000 * statistics.fmean(row["ttft_s"] for row in block),
        })
    return windows


def read_rows(path):
    if path.exists():
        with path.open(encoding="utf-8") as stream:
            return list(map(json.loads, stream))
    with gzip.open(str(path) + ".gz", "rt", encoding="utf-8") as stream:
        return list(map(json.loads, stream))


def independently_audit(run, workload, digest):
    client = run / "client"
    meta = json.loads((client / "summary.json").read_text())
    rows = read_rows(client / "requests.jsonl")
    if len(rows) != len(workload) or set(row["id"] for row in rows) != set(workload):
        raise ValueError(f"Missing or repeated workload requests in {run}")
    if meta["workload_sha256"] != digest or meta["request_rate"] != 4:
        raise ValueError(f"Replay used a different workload or target rate: {run}")
    ends = {}
    order = sorted(rows, key=lambda row: row["send_monotonic"])
    for row in order:
        original = workload[row["id"]]
        send, done, elapsed = row["send_monotonic"], row["completed_monotonic"], row["ttft_s"]
        if (
            row["status"] != "ok"
            or row["http_status"] != 200
            or original != (row["session"], row["turn"], row["server_input_tokens"])
            or row["output_tokens"] != 1
            or not (
                all(math.isfinite(value) for value in (send, done, elapsed))
                and 0 < elapsed <= done - send
            )
        ):
            raise ValueError(f"Invalid request trace in {run}: {row['id']}")
        session = row["session"]
        turn = row["turn"]
        if turn and (session, turn - 1) not in ends:
            raise ValueError(f"Missing predecessor for {row['id']}")
        if turn and send < ends[session, turn - 1]:
            raise ValueError(f"Concurrent turns within session {session} in {run}")
        ends[session, turn] = done
    times = [row["send_monotonic"] for row in order]
    ttft = [row["ttft_s"] * 1000 for row in order]
    keys = list(workload)
    sent_ids = [row["id"] for row in order]
    if meta.get("scheduling_policy") == "fixed-slot-order, dependency-checked" and sent_ids != keys:
        raise ValueError(f"Observed sending order disagrees with the frozen slots in {run}")
    arrivals = (len(times) - 1) / (times[-1] - times[0])
    peaks, waiting = queues(run)
    return {
        "run": str(run.resolve()),
        "workload_sha256": digest,
        "scheduling_policy": meta.get("scheduling_policy", "round-first"),
        "completed": len(order),
        "observed_rps": arrivals,
        "missed_slots_for_dependency": meta["missed_slots_for_dependency"],
        "input_tokens_per_second": sum(row["input_tokens"] for row in order) / (times[-1] - times[0] + 0.25),
        "request_throughput": len(order) / (max(row["completed_monotonic"] for row in order) - times[0]),
        "mean_ttft_ms": statistics.fmean(ttft),
        "median_ttft_ms": statistics.median(ttft),
        "duration_s": max(row["completed_monotonic"] for row in order) - times[0],
        "p95_ttft_ms": statistics.quantiles(ttft, n=100, method="inclusive")[94],
        "ttft_quarter_means_ms": [statistics.fmean(ttft[i * len(ttft) // 4 : (i + 1) * len(ttft) // 4]) for i in range(4)],
        "inflight_at_last_send": sum(row["completed_monotonic"] > times[-1] for row in order),
        "p_request_phase_metrics": prefill_phases(run),
        "p_peak_waiting_by_engine": peaks,
        "p_waiting_timeseries": waiting,
        "arrival_windows": arrival_windows(order),
    }, sent_ids


def load_workload_index(rows):
    keys = {}
    for entry in rows:
        if entry["id"] in keys:
            raise ValueError(f"Duplicate workload ID {entry['id']}")
        keys[entry["id"]] = (entry["session"], entry["turn"], entry["prompt_tokens"])
    return keys


def at_target_rate(run):
    return (
        abs(run["observed_rps"] - 4) <= 0.01
        and run["missed_slots_for_dependency"] == 0
        and run["scheduling_policy"] == "fixed-slot-order, dependency-checked"
    )


def compare(keys, digest, baseline_run, afd_run, min_reduction):
    baseline, order = independently_audit(baseline_run, keys, digest)
    afd, other_order = independently_audit(afd_run, keys, digest)
    ceiling = baseline["mean_ttft_ms"] * (1 - min_reduction)
    replay_valid = at_target_rate(baseline) and at_target_rate(afd) and order == other_order
    ttft_passed = afd["mean_ttft_ms"] <= ceiling
    return {
        "baseline": baseline,
        "afd": afd,
        "identical_send_order": order == other_order,
        "acceptance_ceiling_ms": ceiling,
        "reduction_pct": (1 - afd["mean_ttft_ms"] / baseline["mean_ttft_ms"]) * 100,
        "ttft_gate_passed": ttft_passed,
        "replay_valid": replay_valid,
        "acceptance_passed": replay_valid and ttft_passed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workload", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("afd", type=Path)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--ffn-graph", type=Path, required=True)
    parser.add_argument("--attention-layout", type=Path, required=True)
    parser.add_argument("--flexible-ratio", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(args.workload.read_bytes()).hexdigest()
    keys = load_workload_index(read_rows(args.workload))
    expected = json.loads(args.case.read_text())["load"]
    if digest != expected["splits"]["formal_candidate"]["sha256"]:
        raise ValueError("The formal replay workload does not match the frozen case")
    result = compare(keys, digest, args.baseline, args.afd, expected["required_ttft_reduction"])
    requests = read_rows(args.afd / "client/requests.jsonl")
    result["ffn_full_replay"] = verify_full_replay(args.ffn_graph, requests)
    attention = json.loads(args.attention_layout.read_text())
    if attention["observed_ranks"] != 12 or not attention["all_12_ranks_resolved_shared_expert_dp"]:
        raise ValueError("Shared-expert DP was not verified on all 12 Attention ranks")
    result["attention_shared_expert_dp"] = attention
    smoke = {
        kind: json.loads((args.flexible_ratio / f"{kind}/result.json").read_text())
        for kind in ("short", "long")
    }
    if any(row["status"] != "ok" or row["output_tokens"] != 1 for row in smoke.values()):
        raise ValueError("8A+8F first-token smoke did not complete")
    result["afd8_prefill_smoke"] = smoke
    result["environment"] = {
        "P": json.loads((args.environment / "preflight.json").read_text()),
        "prepared": json.loads((args.environment / "prepared-runtime.json").read_text()),
    }
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(raw)
    print(raw, end="")
    if not result["acceptance_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
