# Ascend 910C 上机验收

从 **P 容器**发起验收，通过 SSH 在 **D 容器**执行命令。使用实测的 **A3/openEuler、CANN `9.1.0`** 镜像组合。已有约定镜像和同版权重时，从第 1 步开始。[正式验收版本](../README.md#运行环境与版本) · [重建原实测镜像](#重建原实测镜像) · [下载权重](#下载权重)

## 开始前

- **两台 Ascend 910C。** P 负责 Prefill，D 负责 Decode。两端各分配 **8 张物理卡、16 个逻辑 DIE** 供本次测试独占。
- **模型权重。** 两端挂载同一版本的 **DeepSeek-V4-Flash W4A8 + DSpark** checkpoint。
- **共享目录和网络。** 两个容器通过同一个绝对路径访问验收仓，且都能写入该目录。P 能通过 SSH 在 D 容器内执行命令。P、D 的 Mooncake 数据网互通，开放用例使用的 HTTP、DP RPC 和 KV 端口。[端口配置](../cases/910c-dsv4-w4a8-rps4/config.env) · [双 EP8 端口分配](../scripts/launch.sh#L89-L95)

## 1. 填写 `site.env`

已有交付版验收仓时，在 **P 容器**的仓库根目录将 `site.env.example` 复制为 `site.env`。首次获取验收仓时，在 P 容器执行下列命令，将 `/shared` 和 `ACCEPTANCE_REF` 换成现场目录和交付版本。

~~~bash
cd /shared
git clone https://github.com/jiaran-king/afd-dsv4-performance-acceptance.git
cd afd-dsv4-performance-acceptance
ACCEPTANCE_REF='填写交付标签或提交'
git checkout --detach "$ACCEPTANCE_REF"
cp site.env.example site.env
~~~

在 **P、D 两个容器内分别查现场值**，然后编辑共享目录中的 `site.env`。预检、准备和启动都读取这份配置。

| 字段 | 怎么查、怎么填 |
| --- | --- |
| `P_NODE_IP`、`D_NODE_IP`、`P_NIC`、`D_NIC` | 用 `ip -br -4 addr` 或部署环境提供的网络信息查 Mooncake 数据网卡和对应 IPv4。IP 字段填地址本身，去掉 `/24` 等前缀长度。 |
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

## 2. 运行验收

在 **P 容器的验收仓根目录**执行。

~~~bash
./reproduce.sh --site site.env
~~~

命令会自动下载并校验冻结请求包，然后跑**双 EP8 8K 基线、12A+4F AFD 16K 性能对照和 8A+8F PD 冒烟**。两组性能测试使用同一份 **1,200 条冻结请求、固定 4 RPS**，每组正式发压约 5 分钟，构建、模型加载和预热另计。[验收配置与判定](acceptance.md)

已有冻结请求包时，可以在 `site.env` 中用 `WORKLOAD_ARCHIVE` 指定 P 容器内的文件路径。[冻结请求包](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

验收命令获取官方 AFD 标签 `0.30.0rc2` 对应的固定提交，在 P 容器中构建算子。[官方标签](https://github.com/vllm-project/afd-plugin/tree/0.30.0rc2) · [AFD 固定提交](../cases/910c-dsv4-w4a8-rps4/case.json)

## 3. 查看结果

打开正式运行生成的 `runs/<run-id>/acceptance.json`。**`acceptance_passed` 为 `true` 即通过**。`reduction_pct` 是相对**现场同轮双 EP8 基线**的平均 TTFT 降幅，门槛为**至少 20%**。`environment` 记录两端实际软件版本和本轮准备的算子。若脚本中途退出，保留终端报错和该次运行目录供定位。

若报错提示运行锁 `runs/.active`，按给出的运行目录和 PID 文件在对应容器确认上一轮服务已退出，再清理锁并重跑。

## 续跑 AFD

若本用例的无 CWS 双 EP8 基线已完成，可以在原 P/D 容器、同一份权重、软件栈和设备配置下续跑 AFD 与配比检查。将 `RUN_ID` 填为原运行目录名。

~~~bash
./reproduce.sh --site site.env --resume-afd "$RUN_ID"
~~~

## 重建原实测镜像

从官方 vLLM-Ascend 标签 `v0.30.0rc1` 获取源码，检出 `8d4409d6`。这个提交自带的 A3/openEuler Dockerfile 从 CANN `9.1.0` 开始构建，命令同时指定 vLLM 的验收提交。[官方 Dockerfile](https://github.com/vllm-project/vllm-ascend/blob/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6/Dockerfile.a3.openEuler)

~~~bash
git clone --filter=blob:none --single-branch --no-checkout --branch v0.30.0rc1 \
  https://github.com/vllm-project/vllm-ascend.git
git -C vllm-ascend checkout --detach 8d4409d6256d8a6729140ddcc0d1889e3f96cdd6
docker build --platform linux/arm64 \
  -f vllm-ascend/Dockerfile.a3.openEuler \
  --build-arg VLLM_COMMIT=ced6857afa0ea7b2e3f0846a62e1394e90f15607 \
  -t afd-910c-acceptance:base vllm-ascend
~~~

用同一个镜像启动 P、D 容器，映射 Ascend 设备，并挂载验收共享目录和权重目录。[该版本的官方安装指南](https://github.com/vllm-project/vllm-ascend/blob/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6/docs/source/getting_started/installation.md#installation-prebuilt-image)

## 下载权重

在装有 Git LFS 的机器上下载固定版本的权重，将本地目录替换为现场路径。P、D 挂载同一版本。[ModelScope 权重](https://www.modelscope.cn/models/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test) · [安装 Git LFS](https://git-lfs.com/)

~~~bash
MODEL_DIR=/models/dsv4-flash-w4a8-dspark
git clone --no-checkout \
  https://www.modelscope.cn/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test.git "$MODEL_DIR"
git -C "$MODEL_DIR" lfs install --local --skip-smudge
git -C "$MODEL_DIR" checkout --detach 59b8e36964b964140dad8e580e14247564744ac9
git -C "$MODEL_DIR" lfs pull
~~~
