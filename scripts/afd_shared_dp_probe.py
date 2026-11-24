"""Record graph-independent shared-expert layout after each A worker loads weights."""
from functools import wraps
import json
import os
from pathlib import Path

from afd_plugin.compat.npu import feature_validation
from afd_plugin.v1.worker.npu.attention_worker import AFDNPUAttentionWorker
from vllm_ascend.ascend_config import get_ascend_config

_LOAD = AFDNPUAttentionWorker.load_model
_DIRECTORY = Path(os.environ["AFD_SHARED_DP_PROBE_DIR"]).resolve()


def linear_layout(projection):
    return {
        "tp_size": getattr(projection, "tp_size", None),
        "disable_tp": getattr(projection, "disable_tp", None),
        "input_size": getattr(projection, "input_size", None),
        "input_size_per_partition": getattr(projection, "input_size_per_partition", None),
        "weight_shape": list(projection.weight.shape),
    }


def snapshot(worker):
    from vllm.distributed import get_tp_group

    runtime = worker.vllm_config
    layouts = []
    for name, module in worker.get_model().named_modules():
        if type(module).__name__ != "AFDDeepseekV4SharedExperts":
            continue
        layouts.append({
            "layer": name,
            "weights_replicated": bool(module.weights_replicated),
            "is_sequence_parallel": bool(module.is_sequence_parallel),
            "gate_up": linear_layout(module.gate_up_proj),
            "down": linear_layout(module.down_proj),
        })
    return {
        "pid": os.getpid(),
        "dp_rank": runtime.parallel_config.data_parallel_rank,
        "tp_rank": get_tp_group().rank_in_group,
        "tp_size": runtime.parallel_config.tensor_parallel_size,
        "requested_shared_dp": runtime.additional_config.get("enable_shared_expert_dp", False),
        "resolved_shared_dp": bool(get_ascend_config().enable_shared_expert_dp),
        "feature_validation_source": str(Path(feature_validation.__file__).resolve()),
        "shared_experts": layouts,
    }


@wraps(_LOAD)
def load_with_snapshot(self, *args, **kwargs):
    output = _LOAD(self, *args, **kwargs)
    try:
        data = snapshot(self)
    except Exception as exc:
        data = {"pid": os.getpid(), "observation_error": repr(exc)}
    path = _DIRECTORY / f"worker-{os.getpid()}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)
    return output


AFDNPUAttentionWorker.load_model = load_with_snapshot


class Worker:
    def force_shared_dp_startup_layout(self):
        return snapshot(self)
