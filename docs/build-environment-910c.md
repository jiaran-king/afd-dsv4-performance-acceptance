# 构建 910C 验收环境

从官方 ARM64 A3 镜像构建 `afd-910c-acceptance:single-rc2`。构建机需要 ARM64 Linux 和 Docker，上机使用一台 Ascend 910C 的 8 张物理卡、16 个逻辑 DIE。官方镜像在 A3 上的验证组合包含 CANN `9.2.1` 和 Ascend HDK `26.2.RC1`。[版本与来源](../README.md#运行环境与版本) · [官方软件栈](https://docs.vllm.ai/projects/ascend/en/v0.30.0/getting_started/installation.html#hardware-and-software-stack)

## 1. 构建镜像

首次使用时先克隆验收仓。

~~~bash
git clone https://github.com/jiaran-king/afd-dsv4-performance-acceptance.git
cd afd-dsv4-performance-acceptance
~~~

在验收仓根目录构建。`docker build` 按 Dockerfile 中的 digest 获取官方底座。

~~~bash
docker build --platform linux/arm64 -f docker/Dockerfile.a3 -t afd-910c-acceptance:single-rc2 docker
~~~

使用现场 PyPI 镜像时，可加入 `--build-arg PYPI_INDEX_URL=<镜像的 simple 地址>`。

底座为 `quay.io/ascend/vllm-ascend:v0.30.0-a3-openeuler`。构建保留镜像内的 vLLM `ced6857a` 和 CANN `9.2.1`，检出 vLLM-Ascend `8d4409d6` 及其子模块，安装对应 Python 依赖并编译 A3 算子。仅在编译时使用 `FLA_NPU_DISABLE_PTH=1`，避免底座预装的 FLA 抢先注册同名算子。上机时，验收入口会从官方 AFD `0.30.0rc2` 准备插件。[Dockerfile](../docker/Dockerfile.a3) · [上游同名算子冲突记录](https://github.com/vllm-project/vllm-ascend/issues/18073)

## 2. 准备权重路径

使用现场已有的 DeepSeek-V4-Flash W4A8 + DSpark 权重目录。需要获取权重时，在装有 Git LFS 的机器上执行以下命令。[ModelScope 权重](https://www.modelscope.cn/models/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test)

~~~bash
MODEL_DIR=/models/dsv4-flash-w4a8-dspark
git clone --no-checkout \
  https://www.modelscope.cn/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test.git "$MODEL_DIR"
git -C "$MODEL_DIR" lfs install --local --skip-smudge
git -C "$MODEL_DIR" checkout --detach 59b8e36964b964140dad8e580e14247564744ac9
git -C "$MODEL_DIR" lfs pull
~~~

## 3. 启动容器

下面以宿主机分配 DIE `0–15` 为例。从仓库根目录在 Bash 中执行，把 `MODEL_DIR` 换成宿主机权重的绝对路径。设备编号按现场分配填写，网卡和地址从容器内查找。[官方 A3 容器示例](https://docs.vllm.ai/projects/ascend/en/v0.30.0/getting_started/installation.html#installation-prebuilt-image)

~~~bash
MODEL_DIR=/models/dsv4-flash-w4a8-dspark
devices=()
for die in {0..15}; do devices+=(--device "/dev/davinci$die"); done
docker run --rm -it --network host --ipc host \
  "${devices[@]}" --device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /usr/local/dcmi:/usr/local/dcmi:ro \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro \
  -v /etc/ascend_install.info:/etc/ascend_install.info:ro \
  -v "$MODEL_DIR:/models/dsv4:ro" -v "$PWD:/work/acceptance" \
  -w /work/acceptance afd-910c-acceptance:single-rc2 bash
~~~

## 4. 核对运行环境

在容器内运行。两个提交分别以 `ced6857a` 和 `8d4409d6` 开头，NPU 数量为 `16`，张量加法结果为 `[2.0, 2.0]`。

~~~bash
git -C /vllm-workspace/vllm rev-parse HEAD
git -C /vllm-workspace/vllm-ascend rev-parse HEAD
source /usr/local/Ascend/ascend-toolkit/set_env.sh
npu-smi info -m
python3 - <<'PY'
import torch
import torch_npu
import vllm
import vllm_ascend

print(f"DIE count: {torch.npu.device_count()}")
print((torch.ones(2, device="npu:0") + 1).cpu().tolist())
PY
~~~

进入上机指南第 1 步，将 `P_MODEL_DIR` 填成 `/models/dsv4`。[上机指南](reproduce-910c.md)
