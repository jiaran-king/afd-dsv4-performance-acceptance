# 单机用例与验收证据

| 要求 | 本仓执行的用例及证据 |
| --- | --- |
| vLLM、DeepSeek-V4-Flash W4A8 | 两组使用同一交付 checkpoint 和运行镜像。预检记录现场软件版本、模型指纹及权重分片。 |
| 单台 910C、同等卡数 | 在同一台 910C 的 8 张物理卡、16 个逻辑 DIE 上顺序运行。 |
| 双 `DP2/TP4`、MBT 8K、入口 4 RPS | 两个原生 EP8 实例各占 8 DIE。客户端向本机两个实例按会话交替分流，正式请求使用固定发送计划。 |
| 单机 Prefill、异步 A/F | 每条请求由本机前端返回 1 token。AFD 验证 12 个 A rank 的共享专家 DP 和 4 个 F rank 的 FULL 图实际重放。 |
| A/F 灵活配比 | 12A+4F 做正式性能对照。8A+8F 用 Eager 单机配置跑长短请求，核对首 token 结果。 |
| 平均 TTFT 降低至少 20% | 按同轮双 EP8 基线计算 `1 - AFD 平均 TTFT / 双 EP8 平均 TTFT`。 |
| GSM8K | 同一镜像和权重，独立运行官方测试集。报告两组数值答案正确率和差值。 |

## 执行配置

两组均关闭 CWS 和 Prefix Cache，使用现场 vLLM-Ascend 原生算子。

| 项目 | 双 EP8 基线 | AFD 12A+4F |
| --- | --- | --- |
| 并行 | 两套 DP2/TP4/EP8 | A DP3/TP4，F DP4/TP1/EP4 |
| MBT | 8,192 | A/F 各 16,384 |
| 执行 | MRV2、异步调度、Prefill MC2 | A 侧 MRV2、Eager + 双微批 DBO、共享专家 DP 开启。F 侧 Async CAM layered W4A8 GMM、FULL。 |
| 每 DP 最大序列数 | 8 | A/F 各 16 |
| 显存利用率参数 | 0.9 | A/F 各 0.7 |

8A+8F 用例为 A DP4/TP2、F DP8/TP1/EP8，A/F MBT 16,384，F Eager，A 侧共享专家 DP 关闭。[配置入口](../cases/910c-dsv4-w4a8-rps4/config.env) · [固定版本](../cases/910c-dsv4-w4a8-rps4/case.json)

## 计时和判定

每组先使用相同的 16 条预热请求，再以固定顺序发 1,200 条正式请求。每 250 ms 一个发送时隙，同会话的后一轮等待前一轮完成。客户端从发出请求到收到首个生成 token 计 TTFT。

脚本核对负载指纹、发送顺序、完成状态、输入和输出 token 数、实发 4 RPS（允许 0.01 RPS 调度误差）及零依赖空时隙。P50、P95 和可采集到的排队及 Prefill 时间随结果记录。

## GSM8K 评分

运行官方 1,319 道测试题。两组使用相同提示模板、温度 0、并发 32，每题最多生成 1,024 token。生成遇到 `Question:` 等停止标记就结束，从 `####` 后提取最后一个数值并与参考答案比较。缺少可解析数值计为答错。逐题记录和汇总保存在独立运行目录，正确率暂不设通过门槛。[GSM8K 停止标记](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/lm_eval/tasks/gsm8k/gsm8k.yaml)
