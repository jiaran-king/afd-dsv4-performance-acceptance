# 两轮同节点配对参考结果

2026-11-24，Ascend 910C，同一个 P/D 节点对，DeepSeek-V4-Flash W4A8。正式用例为原生双 EP8 8K 对 12A+4F、A DP3/TP4、A/F MBT 32,768、F FULL、A 侧共享专家 DP 关闭。

| 配对 | 双 EP8 平均 TTFT | AFD FULL 平均 TTFT | 平均 TTFT 降幅 |
| --- | ---: | ---: | ---: |
| 第一轮 | 3.009 s | 2.305 s | **23.40%** |
| 第二轮 | 3.041 s | 2.278 s | **25.08%** |

每个正式窗口均以 4 RPS 完成 1,200 条请求，D 端均核对到 1,200 条对应的 KV 传输。两轮的四个 F rank 均确认捕获并重放 FULL 图。每个 rank 的已完成重放数下界分别为 75,164 和 75,379。该下界从正式窗口内的提交数扣除可能仍在途的重放数。

[逐请求与图计数证据](evidence) · [参考数值](reference.json) · [固定负载指纹](../../cases/910c-dsv4-w4a8-rps4/case.json)

在仓库根目录运行 `./reproduce.sh --verify-reference` 可以从发布的逐请求计时、KV 收据、指标和图计数重新计算两轮结果。复核用负载索引保留请求身份、顺序与长度，完整冻结 token ID 由 Release 提供。

灵活配比另有 8A+8F 功能记录。2,331 和 33,936 token 两条输入均完成生成，D 侧分别收到 2,330 和 33,935 个外部 KV token。本次上机入口会执行同配置的配比检查。 [8A+8F 实测记录](evidence/flexible-ratio.json)
