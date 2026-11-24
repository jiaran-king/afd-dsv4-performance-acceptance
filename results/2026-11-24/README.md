# 双 EP8 与共享专家 DP 开启版

2026-11-24，Ascend 910C，DeepSeek-V4-Flash W4A8。开启版采用 12A+4F、A DP3/TP4、A/F MBT 32,768、F FULL，A 侧使用 `bc80959` 加实跑校验补丁并开启共享专家 DP。比较沿用同一对 P/D 节点上已实测的双 EP8 8K 基线。

| 用例 | 正式请求完成 | 平均 TTFT | 平均 TTFT 降幅 |
| --- | ---: | ---: | ---: |
| 双 EP8 8K | 1,200/1,200 | 3.041 秒 | |
| AFD FULL + 共享专家 DP | 1,200/1,200 | 1.732 秒 | **43.04%** |

两组都以 4 RPS 回放同一份冻结请求，D 端逐请求核对通过。开启版的 12 个 A rank 均加载了复制的共享专家权重，四个 F rank 均实际重放 FULL 图。

在仓库根目录运行 `./reproduce.sh --verify-reference`，可以从逐请求计时、KV 收据、A 侧权重布局和 F 侧图计数复算参考成绩。测试同学上机时按自己同轮的双 EP8 基线计算降幅，并按原表至少 20% 判定。 [逐请求和运行证据](evidence) · [参考数值](reference.json) · [冻结负载指纹](../../cases/910c-dsv4-w4a8-rps4/case.json)

同节点基线来自此前发布的第二轮。8A+8F 功能用例的 2,331 和 33,936 token 输入均完成生成，D 侧分别收到 2,330 和 33,935 个外部 KV token。 [基线来源](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.1.0/results/2026-11-24/README.md) · [8A+8F 实测记录](evidence/flexible-ratio.json)
