# 2026-11-28 单机 910C 性能验收（1128_4rps_mbt_8k，第 2 遍）

验收**通过**。相比同轮双 EP8，AFD 平均 TTFT 降幅为 **39.53%**，门槛为 20%。

| 用例 | 完成请求 | 实发 RPS | 平均 TTFT | P50 TTFT | P95 TTFT | 依赖跳过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 非分离双 EP8 | 1,200 | 4.0000 | 2.923 秒 | 2.744 秒 | 5.195 秒 | 0 |
| AFD 12A+4F | 1,200 | 4.0000 | 1.768 秒 | 1.594 秒 | 3.750 秒 | 0 |

运行 ID 为 `20261128T081225Z-59692`。在 `v0.3.0`（`4922a133`）上应用包内的 `1128_4rps_mbt_8k.patch` 后，执行 `./reproduce.sh --site site.env`。配置从原标签的 AFD MBT 16K 改为 8K，双 EP8 保持 8K，固定负载为 4 RPS。CWS 与 Prefix Cache 均关闭。

`repo/runs/20261128T081225Z-59692` 包含预检和准备日志、逐请求记录、服务日志、Prometheus 前后快照、F FULL 图重放、A 共享专家 DP 及 8A+8F 长短请求冒烟。使用同一台 910C 的 16 个逻辑 DIE。包内保留本遍终端记录、退出码、实际站点配置及镜像摘要。站点标识和单 token 作答文本已处理，逐请求计时和图计数保留原值。

[固定版本与配置](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docs/acceptance.md) · [冻结负载](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

[证据包](afd-single910c-performance-evidence-1128_4rps_mbt_8k-run2-20261128T081225Z-59692.tar.gz) · [验收报告](acceptance-1128_4rps_mbt_8k-run2-20261128T081225Z-59692.json) · [SHA256](SHA256SUMS)
