"""Verify the replicated DeepSeek V4 shared-expert layout at startup."""

from collections import Counter
import json
from pathlib import Path
import sys


def verify_layout(rows):
    ranks = {(dp, tp) for dp in range(3) for tp in range(4)}
    observed = {(row.get("dp_rank"), row.get("tp_rank")) for row in rows}
    if len(rows) != len(ranks) or observed != ranks:
        raise ValueError("Expected one shared-expert layout snapshot for each DP3/TP4 rank")

    layouts = Counter()
    for row in rows:
        rank = (row["dp_rank"], row["tp_rank"])
        if not (row["requested_shared_dp"] and row["resolved_shared_dp"] and row["tp_size"] == 4):
            raise ValueError(f"Shared-expert DP did not take effect on rank {rank}")
        if len(row["shared_experts"]) != 43:
            raise ValueError(f"Unexpected shared-expert layer count on rank {rank}")
        for expert in row["shared_experts"]:
            if not (expert["weights_replicated"] and expert["is_sequence_parallel"]):
                raise ValueError(f"Shared expert is not replicated on rank {rank}: {expert['layer']}")
            for projection in (expert["gate_up"], expert["down"]):
                if (projection["tp_size"] != 1
                        or projection["input_size"] != projection["input_size_per_partition"]):
                    raise ValueError(f"Shared-expert projection is sharded on rank {rank}")
            layout = {key: value for key, value in expert.items() if key != "layer"}
            layouts[json.dumps(layout, sort_keys=True)] += 1

    return {
        "observed_ranks": len(observed),
        "all_12_ranks_resolved_shared_expert_dp": True,
        "projection_layouts": [dict(json.loads(layout), instances=count)
                               for layout, count in sorted(layouts.items())],
    }


def main():
    directory, source = map(Path, sys.argv[1:])
    expected = source.resolve(strict=True)
    rows = [json.loads(path.read_text()) for path in sorted(directory.glob("worker-*.json"))]
    for row in rows:
        found = row.get("feature_validation_source")
        if not found or Path(found).resolve(strict=True) != expected:
            raise ValueError("An Attention worker did not load the validator from the prepared AFD installation")
    report = verify_layout(rows)
    report["feature_validation_source"] = str(expected)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
