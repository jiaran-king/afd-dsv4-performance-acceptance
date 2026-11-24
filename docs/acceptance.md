# 原表要求与验收证据

| 原表要求 | 本仓执行的用例及证据 |
| --- | --- |
| vLLM、DeepSeek-V4-Flash W4A8 | 两组用同一 checkpoint，预检核对模型配置、量化描述和 tokenizer 指纹。 |
| 910C、1–2 节点、8–16 卡（16–32 DIE），同等卡数对照 | 固定用同一对节点顺序运行。P、D 各一台、各 8 张物理卡和 16 DIE。 |
| 双 `DP2/TP4`，MBT=8K，入口 4 RPS | 两个独立原生 P 实例各占 8 DIE、EP8、MBT 8,192。正式请求从 PD proxy 以固定计划发出。 |
| 完整 PD，Prefill 异步 A/F | AFD 12A+4F 使用 Async CAM。正式回放逐请求核对 D 端 KV 传输，并验证四个 F rank 的 FULL 图捕获和实际重放。发压前核对 12 个 A rank 的共享专家 DP 都已生效。 |
| A/F 灵活配比 | 12A+4F 做正式性能对照。8A+8F 以已验证的 Eager 设置实际接收请求，通过异步 A/F、P→D KV 和生成检查。 |
| 平均 TTFT 降低至少 20% | 两组播放同一份请求后计算 `1 - AFD 平均 TTFT / 同轮双 EP8 平均 TTFT`。原表的 8.7 秒是历史基线参考。 |

## 执行配置

| 项目 | 双 EP8 基线 | AFD 12A+4F |
| --- | --- | --- |
| P 节点 | 两套 DP2/TP4/EP8 | A DP3/TP4，F DP4/TP1/EP4 |
| MBT | P 8,192 | A/F 各 32,768 |
| P 执行 | MRV2、异步调度、CWS、Fused MC2 | A 侧 MRV2、Eager + 双微批 DBO，应用实跑校验补丁并开启共享专家 DP。F 侧 Async CAM layered W4A8 GMM、FULL。 |
| 每 DP 最大序列数 | 8 | A/F 各 16 |
| P 侧显存利用率参数 | 0.9 | A/F 各 0.7 |
| D 节点 | DP16/TP1/EP16、MBT 120、每 DP 最多 2 序列、主模型 FULL_DECODE_ONLY、DSpark 5-token draft Eager | 使用同规格 D，KV 生产者拓扑填 A 的 DP3/TP4 |

灵活配比用例采用 A DP4/TP2、F DP8/TP1/EP8，A/F MBT 32,768，F Eager，A 侧共享专家 DP 关闭。 [配置入口](../cases/910c-dsv4-w4a8-rps4/config.env) · [运行时指纹](../cases/910c-dsv4-w4a8-rps4/case.json)

## 计时和判定

每组冒烟后使用同一份 16 条独立预热请求，再以固定顺序发 1,200 条正式请求。每 250 毫秒一个发送时隙，同会话的后轮等待前轮完成。两组都关闭 prefix cache，每条请求输出 1 token。客户端从发出流式请求到收到首个生成 token 计 TTFT。

脚本核对两组的负载指纹、发送顺序、完成状态、实发 4 RPS（允许 0.01 RPS 的调度误差）、零依赖空时隙和逐请求 P→D KV 传输。平均 TTFT 是原表性能判定指标。P50、P95、P 侧排队和 Prefill 时间用于核对性能差异。

复测低于 20% 时，可用运行证据核对负载、实发速率、KV 传输、A 侧共享权重布局和 F FULL 重放。
