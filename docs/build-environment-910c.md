# 构建 910C 验收环境

从官方 ARM64 A3 镜像构建 `afd-910c-acceptance:single-rc2`。构建机需要 ARM64 Linux 和 Docker，上机使用一台 Ascend 910C 的 8 张物理卡、16 个逻辑 DIE。官方镜像在 A3 上的验证组合包含 CANN `9.2.1` 和 Ascend HDK `26.2.RC1`。[版本与来源](../README.md#运行环境与版本) · [官方软件栈](https://docs.vllm.ai/projects/ascend/en/v0.30.0/getting_started/installation.html#hardware-and-software-stack)

## 获取验收仓

自己构建或启动 Docker 容器时，在 ARM64 Linux 宿主机上克隆正式版本。现场已提供运行中的验收容器时，可在容器内的可写目录克隆，再按[上机指南](reproduce-910c.md)操作。

~~~bash
git clone --branch v0.3.0 --depth 1 https://github.com/jiaran-king/afd-dsv4-performance-acceptance.git
cd afd-dsv4-performance-acceptance
~~~

从宿主机使用现成验收镜像和权重时，克隆完成后直接进入[第 3 步启动容器](#3-启动容器)。

## 1. 从官方镜像回退 vLLM-Ascend

**下面的 `docker build` 就是回退步骤。** Dockerfile 按固定摘要获取官方镜像 `quay.io/ascend/vllm-ascend:v0.30.0-a3-openeuler`。它卸载底座预装的 vLLM-Ascend，检出 `8d4409d6256d8a6729140ddcc0d1889e3f96cdd6` 及其子模块，安装配套依赖并重新编译 A3 算子。构建复用官方镜像中的 vLLM `ced6857a` 和 CANN `9.2.1`，产出验收镜像 `afd-910c-acceptance:single-rc2`。[Dockerfile 回退步骤](../docker/Dockerfile.a3#L6-L14)

在验收仓根目录执行。

~~~bash
docker build --platform linux/arm64 -f docker/Dockerfile.a3 -t afd-910c-acceptance:single-rc2 docker
~~~

使用现场 PyPI 镜像时，先把 `PYPI_INDEX_URL` 设为现场镜像的 simple URL，再把 `--build-arg "PYPI_INDEX_URL=$PYPI_INDEX_URL"` 放在构建命令最后一个 `docker` 参数之前。

Dockerfile 在编译算子时设置 `FLA_NPU_DISABLE_PTH=1`，避免底座预装的 FLA 抢先注册同名算子。启动容器后，按[第 4 步](#4-核对运行环境)确认实际 vLLM-Ascend 提交为 `8d4409d6`。验收入口会从官方 AFD `0.30.0rc2` 准备插件。[上游同名算子冲突记录](https://github.com/vllm-project/vllm-ascend/issues/18073)

## 2. 准备权重路径

已有 DeepSeek-V4-Flash W4A8 + DSpark 权重时，记下它在宿主机上的目录，进入第 3 步。需要获取权重时，在装有 Git LFS 的机器上执行以下命令。[ModelScope 权重](https://www.modelscope.cn/models/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test)

~~~bash
MODEL_DIR=/models/dsv4-flash-w4a8-dspark
git clone --no-checkout \
  https://www.modelscope.cn/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test.git "$MODEL_DIR"
git -C "$MODEL_DIR" lfs install --local --skip-smudge
git -C "$MODEL_DIR" checkout --detach 59b8e36964b964140dad8e580e14247564744ac9
git -C "$MODEL_DIR" lfs pull
~~~

## 3. 启动容器

在宿主机的验收仓根目录用 Bash 执行。`MODEL_DIR` 填宿主机权重的绝对路径，`IMAGE` 填本机验收镜像名。`DIE_IDS` 填现场分配的 16 个逻辑 DIE 编号，可用 `npu-smi info -m` 查看。下面以 `0–15` 为例。

命令把仓库挂到容器的 `/work/acceptance`，把权重挂到 `/models/dsv4`。容器里的 `P_MODEL_DIR` 填挂载后的路径。[官方 A3 容器示例](https://docs.vllm.ai/projects/ascend/en/v0.30.0/getting_started/installation.html#installation-prebuilt-image)

~~~bash
MODEL_DIR=/models/dsv4-flash-w4a8-dspark
IMAGE=afd-910c-acceptance:single-rc2
DIE_IDS=(0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15)
devices=()
for die in "${DIE_IDS[@]}"; do devices+=(--device "/dev/davinci$die"); done
docker run --rm -it --network host --ipc host \
  "${devices[@]}" --device /dev/davinci_manager --device /dev/devmm_svm --device /dev/hisi_hdc \
  -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \
  -v /usr/local/dcmi:/usr/local/dcmi:ro \
  -v /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro \
  -v /etc/ascend_install.info:/etc/ascend_install.info:ro \
  -v "$MODEL_DIR:/models/dsv4:ro" -v "$PWD:/work/acceptance" \
  -w /work/acceptance "$IMAGE" bash
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
