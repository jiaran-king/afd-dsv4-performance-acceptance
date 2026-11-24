# Ascend 910C 上机验收

下面从 **P 容器**发起，通过 SSH 在 **D 容器**执行命令。现场需要交付版仓库标签或提交、镜像地址和权重版本。

## 1. 准备环境

- **两台 Ascend 910C。** P 负责 Prefill，D 负责 Decode。两端各分配 **8 张物理卡、16 个逻辑 DIE**，测试期间独占这些设备。
- **相同镜像和权重。** 两端使用交付指定的 aarch64 镜像，挂载同一版本的 **DeepSeek-V4-Flash W4A8 + DSpark** checkpoint。预检会核对固定源码、CANN 和模型指纹。 [运行版本与模型指纹](../cases/910c-dsv4-w4a8-rps4/case.json)
- **共享目录和网络。** 两个容器通过同一个绝对路径访问验收仓，P 端可写入。P、D 的 Mooncake 数据网互通，开放用例使用的 HTTP、DP RPC 和 KV 端口。 [端口配置](../cases/910c-dsv4-w4a8-rps4/config.env) · [双 EP8 端口分配](../scripts/launch.sh#L74-L88)

## 2. 克隆仓库并填写 `site.env`

在 **P 容器**的共享目录下执行。将 `/shared` 和 `ACCEPTANCE_REF` 换成现场目录和交付版本。

~~~bash
cd /shared
git clone https://github.com/jiaran-king/afd-dsv4-performance-acceptance.git
cd afd-dsv4-performance-acceptance
ACCEPTANCE_REF='填写交付标签或提交'
git checkout --detach "$ACCEPTANCE_REF"
cp site.env.example site.env
~~~

在 **P、D 两个容器内分别查现场值**，然后编辑 `site.env`。

| 字段 | 怎么查、怎么填 |
| --- | --- |
| `P_NODE_IP`、`D_NODE_IP`、`P_NIC`、`D_NIC` | 执行 `ip -br -4 addr`，查 Mooncake 数据网卡和对应 IPv4。IP 字段填地址本身，去掉 `/24` 等前缀长度。 |
| `P_DEVICES`、`D_DEVICES` | 执行 `npu-smi info -m`，填各自分配给测试的 **16 个逻辑 DIE ID**，用逗号分隔。 |
| `P_MODEL_DIR`、`D_MODEL_DIR` | 填各自容器内的 checkpoint 根目录，该目录应直接包含 `config.json`、`quant_model_description.json`、`tokenizer.json` 和权重分片。两端挂载路径可以不同。 |
| `P_SSH`、`P_CONTAINER`、`D_SSH`、`D_CONTAINER` | 从 P 容器发起时，前两项留空。`D_SSH` 填 `用户@D宿主机`，`D_CONTAINER` 填宿主机上的容器名。SSH 直接进入 D 容器时，`D_CONTAINER` 留空。 |
| `VLLM_SOURCE`、`ASCEND_SOURCE`、`CANN_ROOT` | 交付镜像使用模板路径时保留默认值。容器内目录不同时填实际路径。 |

下面是填好的示例。地址、网卡、DIE、权重路径和 SSH 信息都要替换为现场值。数据网络使用 `D_NODE_IP`，远程命令使用 `D_SSH`，两者的地址可以不同。

~~~bash
P_NODE_IP=192.0.2.11
D_NODE_IP=192.0.2.12
P_NIC=enp65s0f0
D_NIC=enp65s0f0

P_DEVICES=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
D_DEVICES=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
P_MODEL_DIR=/models/dsv4-flash-w4a8-dspark
D_MODEL_DIR=/weights/dsv4-flash-w4a8-dspark

P_SSH=
P_CONTAINER=
D_SSH=tester@decode-host.example
D_CONTAINER=afd-d
~~~

填好后，从 **P 容器**检查 D 容器是否能读到配置。下面沿用示例值，退出码为 `0` 表示检查通过。

~~~bash
ssh tester@decode-host.example \
  'docker exec afd-d test -r /shared/afd-dsv4-performance-acceptance/site.env'
~~~

从独立控制机发起时，分别填 `P_SSH` 和 `D_SSH`，并用 `SHARED_ROOT` 指定两端容器中的共享仓库绝对路径。`SITE_REMOTE_FILE` 可指定共享的配置文件路径，默认为 `$SHARED_ROOT/site.env`。现场已有远程执行器时可使用 `NODE_EXEC`。 [配置模板](../site.env.example)

## 3. 准备冻结负载

默认由脚本下载请求包并校验指纹。现场无法访问 GitHub 时，在有网机器检出交付版验收仓，连同 `.git` 带入共享目录。将预下载的 `afd-wildchat-rps4-v2.tar.gz` 放到 P 容器可读的位置，在 `site.env` 填写 `WORKLOAD_ARCHIVE`。另按交付版 `case.json` 的 `runtime.afd` 检出固定 AFD 提交，把该 checkout 连同 `.git` 放到验收仓的 `.runtime/afd-plugin`。 [冻结请求包](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

## 4. 运行并查看结果

在 **P 容器的验收仓根目录**执行。

~~~bash
./reproduce.sh --site site.env --prepare-only &&
  ./reproduce.sh --site site.env
~~~

第一条检查环境并准备固定源码、补丁和算子。第二条在同一对节点上跑**双 EP8 8K 基线、12A+4F AFD 性能对照和 8A+8F 配比检查**。两组性能测试使用同一份 **1,200 条冻结请求、固定 4 RPS**，每组正式发压约 5 分钟，构建、模型加载和预热另计。 [验收配置与判定](acceptance.md)

打开正式运行生成的 `runs/<run-id>/acceptance.json`。**`acceptance_passed` 为 `true` 即通过**。`reduction_pct` 是相对**现场同轮双 EP8 基线**的平均 TTFT 降幅，门槛为**至少 20%**。若脚本中途退出，保留终端报错和该次运行目录供定位。
