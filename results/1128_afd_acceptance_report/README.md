# DeepSeek-V4-Flash 单机 910C AFD 验收测试报告

测试覆盖 2026 年 11 月 27 日至 28 日的单机 910C 验收。8A+8F 和 12A+4F 的长短请求均返回首 token。双 EP8 与 AFD 12A+4F 在同机、同为 8K MBT 的 3 RPS 和 4 RPS 对照中各完成两遍，四遍的平均 TTFT 降幅均超过 20%。两遍完整 GSM8K 精度验收均通过。

## 1 验证环境

| 项目 | 实测配置 |
| --- | --- |
| 硬件与资源 | 单机 Ascend 910C（A3），8 张物理卡、16 个逻辑 DIE。iTask 分配 128 vCPU、1,600 GiB 内存，ARM64。 |
| 软件栈 | Ascend 驱动 `25.5.1.1`，CANN `9.2.1`，Python `3.12.16`，PyTorch `2.10.0+cpu`，torch-npu `2.10.0.post4`。 |
| 推理版本 | vLLM `ced6857a`，vLLM-Ascend `8d4409d6`，AFD `0.30.0rc2+g98f45bb`。 |
| 模型 | DeepSeek-V4-Flash W4A8 + DSpark，权重 `UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test`。 |
| 验收版本 | `v0.3.0`（`4922a133`）。3 RPS 和等 MBT 用该版本的回放口径，配置差异随结果归档。 |

底座为 `quay.io/ascend/vllm-ascend:v0.30.0-a3-openeuler`，底座摘要为 `sha256:0b8bf5b484d49c667ceab717347eb3a8695388429aebd9084b79fa0f57a545c0`。实际派生镜像 ID 为 `sha256:1b895806dfdcc1ea38363ff23ae4912ad63e3764f8dc6f3f685059e49fa99014`，权重 revision 为 `59b8e36964b964140dad8e580e14247564744ac9`。本报告所列运行的镜像 ID 和模型配置、量化配置及 tokenizer 指纹均一致。性能采用单机 Prefill，最大模型长度 65,536，block size 128，CWS 和 Prefix Cache 关闭。 [固定环境和模型指纹](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/cases/910c-dsv4-w4a8-rps4/case.json) · [镜像构建配方](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docker/Dockerfile.a3)

## 2 功能验证结果

四遍等 MBT 8K 的完整验收中，两种配比每遍各发 1 条短请求和 1 条长请求，输入分别为 2,042 和 32,179 token。各配比均为 **8/8 成功**，每条返回 HTTP 200 和 1 个生成 token。

| A/F 配比 | 实测部署 | 结果 |
| --- | --- | --- |
| **8A+8F** | A 为 DP4/TP2，F 为 DP8/TP1/EP8、Eager | 长短请求均通过。 |
| **12A+4F** | A 为 DP3/TP4、Eager + DBO，F 为 DP4/TP1/EP4、layered W4A8 GMM、FULL | 长短请求均通过。12 个 A rank 均验证共享专家 DP，4 个 F rank 均观测到 FULL 图重放。 |

[3 RPS 功能和运行证据](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/6df65c79295542ecba504dc5a7b5503317d1de92/results/1128_3rps_mbt_8k/README.md) · [4 RPS 功能和运行证据](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/9dbf3b04a5e20d57ab483f62a69c370b053cdf88/results/1128_4rps_mbt_8k/README.md)

## 3 性能验证结果

MBT 指每实例或 A/F 每侧的 `max_num_batched_tokens`，8K 和 16K 分别为 8,192 和 16,384。双 EP8 由两个 DP2/TP4/EP8 实例组成，各用 8 个 DIE。每组先预热 16 条，再按固定顺序发送 1,200 条冻结 WildChat 正式请求，每条输出 1 token。实发 RPS 按该组整个入口计算。TTFT 从客户端发出请求计到收到首 token，多遍的分位数按合并后的逐请求记录计算。 [性能口径与验收规则](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docs/acceptance.md)

### 3.1 双 EP8 与 AFD 的等 MBT 8K 对照

同一台 910C 上顺序运行两组。每遍两组的实发速率均达到目标，1,200 条正式请求全部完成，依赖空时隙为 0。验收按每遍相对双 EP8 的平均 TTFT 降幅判定，门槛为 20%。

| 负载和遍次 | 双 EP8 平均 / P95（秒） | AFD 平均 / P95（秒） | 平均降幅 | 判定 |
| --- | ---: | ---: | ---: | --- |
| 3 RPS 第 1 遍 | 1.813 / 3.519 | 0.922 / 2.305 | 49.15% | 通过 |
| 3 RPS 第 2 遍 | 1.808 / 3.478 | 0.928 / 2.322 | 48.70% | 通过 |
| 4 RPS 第 1 遍 | 2.915 / 5.176 | 1.714 / 3.648 | 41.20% | 通过 |
| 4 RPS 第 2 遍 | 2.923 / 5.195 | 1.768 / 3.750 | 39.53% | 通过 |

[3 RPS 两遍报告和证据](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/6df65c79295542ecba504dc5a7b5503317d1de92/results/1128_3rps_mbt_8k/README.md) · [4 RPS 两遍报告和证据](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/9dbf3b04a5e20d57ab483f62a69c370b053cdf88/results/1128_4rps_mbt_8k/README.md)

### 3.2 双 EP8 的 8K 与 16K 对比

四档都在与等 MBT 对照相同的节点运行。3 RPS、8K 共汇总三遍，其中补跑的归档目录是 `1128_3rps_baseline_mbt_16k_2`，其报告和两套服务日志均记录实际 MBT 为 8,192。

| 目标 RPS | MBT | 实发 RPS | 运行和请求数 | 平均 / P50 / P95 TTFT（秒） |
| ---: | ---: | ---: | --- | ---: |
| 3 | 8K | 3.000 | 3 遍 / 3,600 条 | 1.809 / 1.665 / 3.527 |
| 3 | 16K | 3.000 | 1 遍 / 1,200 条 | 2.537 / 2.360 / 5.328 |
| 4 | 8K | 4.000 | 2 遍 / 2,400 条 | 2.919 / 2.738 / 5.194 |
| 4 | 16K | 3.661 | 1 遍 / 1,200 条 | 11.789 / 10.831 / 24.272 |

3 RPS 下，16K 的平均 TTFT 比 8K 高 **40.3%**，P95 高 51.1%。16K、目标 4 RPS 的单次回放有 111 个依赖空时隙，服务端平均排队 8.306 秒，实发未达到 4 RPS。该记录来自本地归档，运行 ID 为 `20261128T063047Z-2064`。 [3 RPS 16K 报告](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/download/v0.3.0/baseline-acceptance-1128_3rps_baseline_mbt_16k-20261128T065127Z-1697.json) · [3 RPS 8K 补跑报告](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/89b9a9fe50418e5490f6f5cc6307191277bf835f/results/1128_3rps_baseline_mbt_16k_2/20261128T095451Z-2788/README.md)

### 3.3 AFD 12A+4F 的 8K 与 16K 对比

四档均达到目标速率，所有正式请求均完成，依赖空时隙均为 0。4 RPS、8K 含两遍等 MBT 对照及一次 AFD 单组补测 `20261128T072132Z-2630`。4 RPS、16K 合并 `1127_4rps` 与 `1128_4rps` 两遍。

| 目标 RPS | A/F MBT | 实发 RPS | 运行和请求数 | 平均 / P50 / P95 TTFT（秒） |
| ---: | ---: | ---: | --- | ---: |
| 3 | 8K | 3.000 | 2 遍 / 2,400 条 | 0.925 / 0.787 / 2.317 |
| 3 | 16K | 3.000 | 1 遍 / 1,200 条 | 0.836 / 0.657 / 1.978 |
| 4 | 8K | 4.000 | 3 遍 / 3,600 条 | 1.745 / 1.569 / 3.689 |
| 4 | 16K | 4.000 | 2 遍 / 2,400 条 | 1.402 / 1.265 / 3.008 |

已测记录中，16K 的平均 TTFT 在 3 RPS 低 **9.6%**，在 4 RPS 低 **19.7%**。8K 与历史 16K 使用相同镜像和负载，运行节点不同。4 RPS 的两遍 16K 也分别在不同节点运行。 [3 RPS 16K 报告](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/download/v0.3.0/acceptance-1128_3rps-20261128T022959Z-2625.json) · [1127 的 4 RPS 16K 报告](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/6df65c79295542ecba504dc5a7b5503317d1de92/results/1127_4rps/20261127T085717Z-4021/acceptance.json) · [1128 的 4 RPS 16K 报告](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/download/v0.3.0/acceptance-1128_4rps-20261128T015045Z-1784.json)

## 4 GSM8K 精度对比

两遍完整对照使用相同镜像和冻结的 GSM8K 测试集前 300 题。双 EP8 使用 8K MBT，AFD 12A+4F 的 A/F 两侧均用 16K MBT。0-shot 并发 32、输出上限 1,024 token，8-shot 并发 12、输出上限 512 token。两场景温度均为 0，8-shot 请求种子为 1234。每个场景允许 AFD 正确率最多比同轮双 EP8 低 1.5 个百分点。

| 归档 | 场景 | 双 EP8 | AFD 12A+4F | AFD 差值（百分点） | 判定 |
| --- | --- | ---: | ---: | ---: | --- |
| `1128_acc` | 0-shot | 279/300（93.00%） | 276/300（92.00%） | -1.00 | 通过 |
| `1128_acc` | 8-shot | 285/300（95.00%） | 285/300（95.00%） | 0.00 | 通过 |
| `1128_acc_2` | 0-shot | 279/300（93.00%） | 281/300（93.67%） | +0.67 | 通过 |
| `1128_acc_2` | 8-shot | 287/300（95.67%） | 286/300（95.33%） | -0.33 | 通过 |

四个场景均通过。首次尝试在双 EP8 的 8-shot 阶段完成 220 条后服务提前退出，正式判定来自同配置的两遍完整运行。 [1128_acc 报告](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/download/v0.3.0/gsm8k-acceptance-1128_acc-20261128T040841Z-32520.json) · [1128_acc_2 报告](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/download/v0.3.0/gsm8k-acceptance-1128_acc_2-20261128T044508Z-81159.json) · [冻结评测与评分规则](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docs/acceptance.md#gsm8k-评分)

## 5 业务代码与测试脚本

### 业务代码

- AFD 分离插件和 Ascend Async CAM 运行时，提交 `98f45bbf`。 [AFD 固定提交](https://github.com/vllm-project/afd-plugin/commit/98f45bbff76bb5165789313c1076fea5c92d8c44)

- vLLM 引擎和 Ascend 适配，提交分别为 `ced6857a` 和 `8d4409d6`。 [vLLM 固定提交](https://github.com/vllm-project/vllm/commit/ced6857afa0ea7b2e3f0846a62e1394e90f15607) · [vLLM-Ascend 固定提交](https://github.com/vllm-project/vllm-ascend/commit/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6)

### 测试入口

- 验收仓固定标签为 `v0.3.0`。性能对照和 8A+8F 功能冒烟执行 `./reproduce.sh --site site.env`。GSM8K 执行 `./reproduce.sh --site site.env --gsm8k`。 [验收仓](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/tree/v0.3.0) · [reproduce.sh](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/reproduce.sh) · [上机复现说明](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docs/reproduce-910c.md)

- 拓扑和 MBT 由验收配置和启动脚本传入。3 RPS 和各 MBT 变体的补丁随上文对应结果归档。 [case.json](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/cases/910c-dsv4-w4a8-rps4/case.json) · [config.env](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/cases/910c-dsv4-w4a8-rps4/config.env) · [launch.sh](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/scripts/launch.sh)

- [功能探针 smoke.py](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/scripts/smoke.py) · [性能回放 replay.py](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/scripts/replay.py) · [性能判定 audit.py](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/scripts/audit.py) · [精度测评 gsm8k.py](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/scripts/gsm8k.py)
