"""Verify per-rank FULL graph execution across the formal 12A+4F replay."""

import argparse
import json
from pathlib import Path
import time


RANKS = {12, 13, 14, 15}


def validate_snapshot(rows, boundary):
    if (len(rows) != len(RANKS) or {row["rank"] for row in rows} != RANKS
            or len({row["pid"] for row in rows}) != len(RANKS)):
        raise ValueError(f"Expected one FULL snapshot for each FFN rank at {boundary}")
    for row in rows:
        if (row["boundary"] != boundary or row["mode"] != "full"
                or row["capture_count"] < 1 or not row["layered_per_channel"]):
            raise ValueError(f"Unexpected FFN graph state at {boundary}: {row}")


def snapshot(directory, boundary):
    marker = directory / "snapshot-request.json"
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps({"boundary": boundary}) + "\n")
    temporary.replace(marker)
    deadline = time.monotonic() + 45
    while True:
        replies = [json.loads(path.read_text()) for path in sorted(directory.glob("rank-*.json"))]
        rows = [row for row in replies if row["boundary"] == boundary]
        if len(rows) == len(RANKS):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Only {len(rows)}/{len(RANKS)} FFN ranks replied at {boundary}")
        time.sleep(0.25)
    validate_snapshot(rows, boundary)
    (directory / f"{boundary}.json").write_text(json.dumps(rows, indent=2) + "\n")


def verify_full_replay(directory, requests):
    before, after = (json.loads((directory / f"{boundary}.json").read_text())
                     for boundary in ("before", "after"))
    validate_snapshot(before, "before")
    validate_snapshot(after, "after")
    first_send = min(row["send_monotonic"] for row in requests)
    last_completion = max(row["completed_monotonic"] for row in requests)
    if (max(row["observed_ns"] for row in before) / 1e9 >= first_send
            or min(row["observed_ns"] for row in after) / 1e9 <= last_completion):
        raise ValueError("FFN snapshots do not bracket the formal request window")
    previous = {row["rank"]: row for row in before}
    proof = []
    for row in sorted(after, key=lambda entry: entry["rank"]):
        rank = row["rank"]
        earlier = previous[rank]
        if (row["pid"], row["proc_start_ticks"]) != (earlier["pid"], earlier["proc_start_ticks"]):
            raise ValueError(f"FFN rank {rank} restarted during the formal run")
        bound = row["max_pending_replays"]
        if bound <= 0 or bound != earlier["max_pending_replays"]:
            raise ValueError(f"Invalid pending replay bound at FFN rank {rank}")
        submitted = row["submitted_replays"] - earlier["submitted_replays"]
        completed_lower_bound = submitted - bound
        if completed_lower_bound <= 0:
            raise ValueError(f"No completed FULL replays verified at FFN rank {rank}")
        proof.append({
            "rank": rank,
            "mode": "full",
            "capture_count": row["capture_count"],
            "submitted_replays_delta": submitted,
            "pending_replay_bound": bound,
            "completed_replays_lower_bound": completed_lower_bound,
        })
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("boundary", choices=("before", "after"))
    parser.add_argument("--verify", type=Path, nargs="+")
    args = parser.parse_args()
    snapshot(args.directory, args.boundary)
    if args.verify:
        requests = [json.loads(path.read_text()) for path in args.verify]
        print(json.dumps(verify_full_replay(args.directory, requests), indent=2))
