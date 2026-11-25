# DeepSeek-V4-Flash W4A8 AFD 性能与精度验收

正式验收使用 [`v0.3.0`](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.3.0)。

性能验收在**一台 Ascend 910C** 上顺序比较原生双 EP8 8K 与 AFD 12A+4F 16K。两组使用同一镜像、权重和冻结请求，每条输出 **1 token**。验收按现场同轮基线计算平均 TTFT 降幅，要求达到 **20%**。

## 运行环境与版本

| 组件 | 本用例版本 | 公开来源 |
| --- | --- | --- |
| 运行镜像底座 | aarch64 · A3/openEuler 24.03 · Python 3.12 · CANN 9.2.1 | `quay.io/ascend/vllm-ascend:v0.30.0-a3-openeuler`。[Dockerfile](docker/Dockerfile.a3) |
| 模型权重 | DeepSeek-V4-Flash W4A8 + DSpark，revision `59b8e36964b964140dad8e580e14247564744ac9` | [ModelScope 模型 UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test](https://www.modelscope.cn/models/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test) |
| vLLM | 官方标签 `v0.30.0` · `ced6857afa0ea7b2e3f0846a62e1394e90f15607` | [官方提交](https://github.com/vllm-project/vllm/commit/ced6857afa0ea7b2e3f0846a62e1394e90f15607) |
| vLLM-Ascend | 回退目标 `8d4409d6256d8a6729140ddcc0d1889e3f96cdd6` | [官方源码提交](https://github.com/vllm-project/vllm-ascend/commit/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6) · [上游版本参照 `v0.30.0rc1`](https://github.com/vllm-project/vllm-ascend/tree/v0.30.0rc1) |
| 推理依赖 | PyTorch `2.10.0` · TorchNPU `2.10.0.post4` · Triton Ascend `3.2.2` | [固定 Ascend 提交的依赖表](https://github.com/vllm-project/vllm-ascend/blob/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6/requirements.txt) |
| AFD | 官方标签 `0.30.0rc2` · `98f45bbff76bb5165789313c1076fea5c92d8c44` | [官方标签](https://github.com/vllm-project/afd-plugin/tree/0.30.0rc2) · [共享专家 DP 修复提交](https://github.com/vllm-project/afd-plugin/commit/98f45bbff76bb5165789313c1076fea5c92d8c44) |

运行镜像复用预装的 vLLM，并从表中固定提交重新编译 vLLM-Ascend 的 A3 算子。现场软件版本和模型指纹随结果记录。[准备权重路径](docs/build-environment-910c.md#2-准备权重路径) · [用例配置](cases/910c-dsv4-w4a8-rps4/case.json)

## 上机验收

### 1. 在宿主机获取验收仓

需要一台 Ascend 910C（8 张物理卡、16 个逻辑 DIE），宿主机使用 ARM64 Linux 并已安装 Ascend 驱动和 Docker。记下宿主机上模型权重的根目录，也就是包含 `config.json` 的目录。[权重获取方法](docs/build-environment-910c.md#2-准备权重路径)

~~~bash
git clone --branch v0.3.0 --depth 1 https://github.com/jiaran-king/afd-dsv4-performance-acceptance.git
cd afd-dsv4-performance-acceptance
~~~

### 2. 在宿主机准备镜像并启动容器

已有按本用例构建的验收镜像时，直接执行下方的 `docker run`。使用官方底座时，先在验收仓根目录执行下面一行。

~~~bash
docker build --platform linux/arm64 -f docker/Dockerfile.a3 -t afd-910c-acceptance:single-rc2 docker
~~~

这条命令从官方 `quay.io/ascend/vllm-ascend:v0.30.0-a3-openeuler` 获取底座，沿用其中的 vLLM 和 CANN，把 vLLM-Ascend 回退到 `8d4409d6` 并重新编译 A3 算子。Dockerfile 在编译时自动设置 `FLA_NPU_DISABLE_PTH=1`，避免底座预装的 FLA 抢先注册同名算子。[Dockerfile](docker/Dockerfile.a3)

在宿主机的验收仓根目录用 Bash 执行下列命令。将 `MODEL_DIR` 改为宿主机权重的绝对路径。用 `npu-smi info -m` 查看本次可用的 16 个逻辑 DIE，将编号填入 `DIE_IDS`。如本地验收镜像用了其他名称，相应修改 `IMAGE`。

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

示例使用 Ascend 驱动的默认挂载路径。宿主机没有 `/etc/ascend_install.info` 时可去掉该文件的挂载行，并在下一步用 `npu-smi info -m` 确认设备可见。

命令将仓库和权重分别挂到容器内的 `/work/acceptance` 和 `/models/dsv4`，并进入容器的仓库根目录。可在容器内执行 `git -C /vllm-workspace/vllm-ascend rev-parse --short=8 HEAD`，核对回退后的提交为 `8d4409d6`。

### 3. 在容器内填写 site.env

首次配置时复制模板，并查看容器内的网卡和逻辑 DIE 编号。

~~~bash
cp site.env.example site.env
ip -br -4 addr
npu-smi info -m
~~~

若容器内没有 `ip`，可用 `ifconfig` 查看网卡和 IPv4 地址。打开 `site.env`，按下表修改并保存。

| 字段 | 填写方法 |
| --- | --- |
| `P_NODE_IP` | 填供 HCCL / Gloo 使用的网卡的 IPv4 地址，去掉末尾的 CIDR 前缀长度。 |
| `P_NIC` | 填该 IPv4 地址所属的网卡名。 |
| `P_DEVICES` | 按第 2 步的设备顺序填写 `Chip Logic ID` 列中的 16 个编号，以逗号分隔。 |
| `P_MODEL_DIR` | 填容器内的权重路径，按上一步挂载时填 `/models/dsv4`。 |

上述镜像使用模板中 `VLLM_SOURCE`、`ASCEND_SOURCE` 和 `CANN_ROOT` 的默认值。首次上机可用 `./reproduce.sh --site site.env --smoke-only` 检查双 EP8 和 12A+4F 是否能加载模型并返回首 token。

### 4. 依次运行性能和精度验收

在容器内的验收仓根目录运行性能验收。

~~~bash
./reproduce.sh --site site.env
~~~

性能运行结束后，再执行 GSM8K 精度验收。

~~~bash
./reproduce.sh --site site.env --gsm8k
~~~

脚本首次运行会获取固定版本的 AFD 并在容器内编译插件，随后顺序启动双 EP8 与 AFD。性能入口会自动获取并校验冻结请求包。已有冻结包时，也可在 `site.env` 的 `WORKLOAD_ARCHIVE` 中填入它在容器内的路径。

### 5. 查看两份验收报告

每次运行会在终端提示 `Artifacts are in ...`。在各自提示的目录查看对应报告。

| 报告 | 通过条件 |
| --- | --- |
| 性能 `acceptance.json` | `acceptance_passed` 为 `true`。平均 TTFT 相对同轮双 EP8 基线至少降低 **20%**，并通过 8A+8F 冒烟。 |
| 精度 `gsm8k.json` | `gsm8k_passed` 为 `true`。0-shot 和 8-shot 各自要求 AFD 正确率最多落后双 EP8 **1.5 个百分点**。 |

逐请求计时、逐题作答和服务日志保存在各自的运行目录。AFD 准备日志为 `prepare.log`。退出容器后，可在宿主机仓库的 `runs/` 下继续查看。

## 测试设计

### 性能

两组在同一台 910C 上顺序运行，使用相同镜像、权重和请求。基线为双 EP8、MBT 8K，AFD 为 12A+4F、A 侧 DP3/TP4、A/F MBT 16K、F 侧 FULL 图、A 侧 `enable_shared_expert_dp=true`。验收会核对 F 侧实际重放 FULL 图，并用 8A+8F 的长短请求验证该配比能返回首 token。

两组各用 16 条请求预热，再以固定顺序按 4 RPS 发送 1,200 条正式请求。关闭 Prefix Cache，每条请求输出 1 token。TTFT 从客户端发出请求计到接收首个生成 token。

性能负载来自 AllenAI 的 **WildChat-4.8M**，内容是真实用户与 ChatGPT 的多轮对话。[上游数据集](https://huggingface.co/datasets/allenai/WildChat-4.8M/tree/c827c6df8fcf008219ffaffa4d1dd77491099367)

### 精度

双 EP8 和 AFD 各运行 GSM8K 官方测试集的前 300 题，分别做 0-shot 和 8-shot。0-shot 直接给题目和答案格式要求，8-shot 额外提供 8 道带解答的示例。同一场景的两组使用相同提示词和生成设置，按最终数值答案评分。

[环境构建细节](docs/build-environment-910c.md) · [上机与日志参考](docs/reproduce-910c.md) · [用例参数和评分规则](docs/acceptance.md) · [冻结请求包](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

[历史双机 PD 复现](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/tree/e60348b0c9f9c48b28711e15fb5bf061d52ad38a)
