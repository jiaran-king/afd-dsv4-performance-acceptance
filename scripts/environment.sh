# Source this file in commands that run inside the test container.
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
source "${SITE_FILE:?Set SITE_FILE to a readable copy of site.env}"
case_dir="$root/cases/910c-dsv4-w4a8-rps4"
runtime="$root/.runtime"
afd_install="$runtime/afd-install"
skill_dir="$runtime/skill-shared-expert-dp"
: "${P_NODE_IP:?Set the local communication address}"
: "${P_NIC:?Set the local communication interface}"
: "${P_MODEL_DIR:?Set the model mount}"
: "${P_DEVICES:?List the 16 devices in logical rank order}"
VLLM_SOURCE=${VLLM_SOURCE:-/vllm-workspace/vllm}
ASCEND_SOURCE=${ASCEND_SOURCE:-/vllm-workspace/vllm-ascend}
CANN_ROOT=${CANN_ROOT:-/usr/local/Ascend/cann}
source "$case_dir/config.env"
export P_NODE_IP

activate_cann() {
    if [[ -r "$CANN_ROOT/set_env.sh" ]]; then
        set +u
        source "$CANN_ROOT/set_env.sh"
        set -u
    fi
}
