"""Snapshot host graph counters through the pinned FFN health RPC."""

from functools import wraps
import json
import os
from pathlib import Path
import time

from afd_plugin.v1.worker.npu.ffn_worker import AFDNPUFFNWorker


_DIRECTORY = Path(os.environ["AFD_GRAPH_PROBE_DIR"]).resolve()
_MARKER = _DIRECTORY / "snapshot-request.json"
_ORIGINAL_HEALTH = AFDNPUFFNWorker.raise_ffn_loop_error_if_any


def graph_counters(worker):
    runner = worker.model_runner
    executor = runner._layered_executor
    return {
        "rank": int(runner.connector.world_rank),
        "pid": os.getpid(),
        "proc_start_ticks": Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19],
        "observed_ns": time.monotonic_ns(),
        "mode": runner.effective_mode,
        "capture_count": runner._graph_capture_count,
        "submitted_replays": runner._graph_replay_count,
        "pending": runner._graph_pending,
        "max_pending_replays": len(runner.layer_ids),
        "layered_per_channel": bool(executor is not None and executor.per_channel),
    }


@wraps(_ORIGINAL_HEALTH)
def observe_ffn_health(self):
    result = _ORIGINAL_HEALTH(self)
    try:
        stamp = _MARKER.stat().st_mtime_ns
    except FileNotFoundError:
        return result
    if getattr(self, "_afd_benchmark_graph_snapshot_stamp", None) == stamp:
        return result
    request = json.loads(_MARKER.read_text())
    data = graph_counters(self)
    data["boundary"] = request["boundary"]
    path = _DIRECTORY / f"rank-{data['rank']}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data) + "\n")
    temporary.replace(path)
    self._afd_benchmark_graph_snapshot_stamp = stamp
    return result


AFDNPUFFNWorker.raise_ffn_loop_error_if_any = observe_ffn_health


class Worker:
    def afd_benchmark_graph_counters(self):
        return graph_counters(self)
