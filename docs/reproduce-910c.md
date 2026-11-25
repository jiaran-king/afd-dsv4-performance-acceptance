# 单台 Ascend 910C 上机验收

使用同一台 910C 上的 **8 张物理卡、16 个逻辑 DIE**。以下命令均在**容器内的正式版本仓库根目录**执行。

- 现场已提供运行中的验收容器时，进入容器，在可写目录[克隆正式版本](build-environment-910c.md#获取验收仓)，确认权重挂载路径后填写 `site.env`。
- 从宿主机准备时，按[环境指南](build-environment-910c.md)获取仓库、挂载权重并启动容器。

## 1. 填写 `site.env`

在容器的验收仓根目录执行，将模板字段改成现场值。

~~~bash
cp site.env.example site.env
~~~

| 字段 | 怎么填 |
| --- | --- |
| `P_NODE_IP`、`P_NIC` | 在容器里运行 `ip -br -4 addr`，从本机用于 HCCL / Gloo 通信的同一行取 IPv4 地址和网卡名。`P_NODE_IP` 只填 IPv4 地址本身。 |
| `P_DEVICES` | 在容器里运行 `npu-smi info -m`，从 `Chip Logic ID` 列取本次分配的 **16 个编号**，用逗号分隔。 |
| `P_MODEL_DIR` | 填容器内的 checkpoint 根目录。按环境指南挂载时填 `/models/dsv4`。 |
| `VLLM_SOURCE`、`ASCEND_SOURCE`、`CANN_ROOT` | 交付镜像使用模板路径时采用默认值。现场路径不同时填实际值。 |

## 2. 运行性能验收

首次在现场启用验收镜像时，可先执行 `./reproduce.sh --site site.env --smoke-only`。它启动双 EP8 和 12A+4F，用长短请求验证模型加载和首 token。

~~~bash
./reproduce.sh --site site.env
~~~

脚本自动准备固定的 AFD 提交和冻结请求包，顺序运行双 EP8 8K、12A+4F AFD 16K 和 8A+8F 单机冒烟。两组正式回放各用 1,200 条请求，固定 4 RPS，关闭 Prefix Cache，每条输出 1 token。每组正式发压约 5 分钟，环境准备和模型加载另计。已有冻结包时，可在 `site.env` 用 `WORKLOAD_ARCHIVE` 指定容器内的文件路径。[用例和判定](acceptance.md)

打开终端 `Artifacts are in ...` 提示的目录，查看 `acceptance.json`。**`acceptance_passed` 为 `true` 即通过**。`reduction_pct` 是相对同轮双 EP8 基线的平均 TTFT 降幅，门槛为至少 **20%**。逐请求计时、F FULL 重放和 8A+8F 冒烟证据都在这个目录。

## 3. 运行 GSM8K 精度验收

~~~bash
./reproduce.sh --site site.env --gsm8k
~~~

双 EP8 和 AFD 各启动一次，各完成仓内前 300 题的 0-shot 与 8-shot。终端会打印各场景的完成题数。在这次命令打印的运行目录打开 `gsm8k.json`，查看每个场景的答对题数、正确率、百分点差值及判定。**`gsm8k_passed` 为 `true` 即通过**，要求两个场景各自满足 AFD 最多落后双 EP8 **1.5 个百分点**。逐题作答和提取结果在 `baseline-gsm8k/` 和 `afd12-gsm8k/` 下各自的场景目录中。[精度配置和评分](acceptance.md#gsm8k-评分)

## 查看日志

AFD 准备日志在本次运行目录的 `prepare.log`。服务启动和加载日志在 `baseline-p/`、`afd12-p/` 和 `afd8-p/` 对应的 `.log` 文件里。
