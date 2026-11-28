# 2026-11-28 单机 910C 性能验收（1128_4rps）

验收通过。AFD 12A+4F 的平均 TTFT 相对同轮双 EP8 基线降低 **52.88%**，门槛为至少 20%。

| 用例 | 完成请求 | 平均 TTFT | P95 TTFT | 实发 RPS |
| --- | ---: | ---: | ---: | ---: |
| 双 EP8，MBT 8K | 1,200 | 2.896 秒 | 5.267 秒 | 4.0000 |
| 12A+4F，A/F MBT 16K | 1,200 | 1.365 秒 | 2.920 秒 | 4.0000 |

运行 ID 为 `20261128T015045Z-1784`。在同一台 910C 的 16 个逻辑 DIE 上运行正式标签 `v0.3.0`（`4922a133`）。每组按 4 RPS 回放同一批 1,200 条冻结请求，两组使用相同的 16 条预热，关闭 CWS 和 Prefix Cache，每条输出 1 token。AFD 的 12 个 A rank 通过共享专家 DP 核对，4 个 F rank 均有 FULL 重放证据。8A+8F 的长、短输入均返回首 token。

## 文件索引

- `repo/runs/20261128T015045Z-1784/acceptance.json` 保存验收判定、两组指标、图重放计数和运行时身份。
- 同一运行目录保存预检与准备日志、服务日志、逐请求数据、预热、Prometheus 前后快照和 8A+8F 冒烟。
- `repo/.runtime/` 保存正式终端输出、退出状态和 NPU 探针。包内还包含实际站点配置、镜像 ID、底座摘要、型号与设备记录。
- `SHA256SUMS` 提供包内文件校验。站点地址、内部标识和单 token 作答文本已处理，计时、顺序、token 数与计数器保留原值。

[固定版本与配置](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docs/acceptance.md) · [冻结负载](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

[证据包](afd-single910c-performance-evidence-1128_4rps-20261128T015045Z-1784.tar.gz) · [验收报告](acceptance-1128_4rps-20261128T015045Z-1784.json) · [SHA256](SHA256SUMS)
