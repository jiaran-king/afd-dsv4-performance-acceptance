"""Recompute the published case from its prompt-free evidence."""

import hashlib
import json
import math
from pathlib import Path

from audit import compare, load_workload_index, read_rows
from graph_replay import verify_full_replay
from shared_expert_dp import verify_layout


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases/910c-dsv4-w4a8-rps4"
RESULT = ROOT / "results/2026-11-24"


def equivalent(expected, observed, path=()):
    if isinstance(expected, dict):
        for key, value in expected.items():
            equivalent(value, observed[key], (*path, key))
    elif isinstance(expected, float) and math.isclose(expected, observed, rel_tol=1e-12):
        return
    elif expected != observed:
        raise ValueError(f"Reference mismatch at {'.'.join(path)}: {expected!r} != {observed!r}")


def main():
    case = json.loads((CASE / "case.json").read_text())
    plan = case["load"]
    index = RESULT / "workload-index.jsonl"
    payload = Path(str(index) + ".gz").read_bytes()
    if hashlib.sha256(payload).hexdigest() != plan["reference_index_sha256"]:
        raise ValueError("Reference workload index checksum mismatch")
    formal = plan["splits"]["formal_candidate"]
    rows = load_workload_index(read_rows(index))
    if len(rows) != formal["requests"]:
        raise ValueError("Unexpected reference workload size")
    expected = json.loads((RESULT / "reference.json").read_text())
    runtime = case["runtime"]
    cws = {"cws_opapi": runtime["cws_reference_opapi_sha256"]}
    expected_native = {
        "baseline": cws,
        "afd": dict(
            cws,
            afd_opapi=runtime["afd_reference_opapi_sha256"],
            afd_extension=runtime["afd_reference_extension_sha256"],
            afd_attention_opapi=runtime["afd_reference_opapi_sha256"],
            afd_attention_extension=runtime["afd_reference_extension_sha256"],
        ),
    }
    evidence = RESULT / "evidence"
    baseline, afd = evidence / "baseline", evidence / "afd"
    report = compare(rows, formal["sha256"], baseline, afd, baseline / "warmup", afd / "warmup")
    report["ffn_full_replay"] = verify_full_replay(afd / "graph-counters", read_rows(afd / "client/requests.jsonl"))
    report["attention_shared_expert_dp"] = verify_layout(read_rows(afd / "attention-ranks.jsonl"))
    equivalent(expected, report)
    equivalent(expected_native, json.loads((evidence / "loaded-native.json").read_text()))
    if not report["acceptance_passed"]:
        raise ValueError("Reference run did not pass")
    print(f"Dual EP8 {report['baseline']['mean_ttft_ms']:.3f} ms, "
          f"AFD FULL + shared-expert DP {report['afd']['mean_ttft_ms']:.3f} ms, "
          f"reduction {report['reduction_pct']:.2f}%")


if __name__ == "__main__":
    main()
