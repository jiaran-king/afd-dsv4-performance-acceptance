# 2026-11-28 单机 910C 双 EP8 基线验收（1128_4rps_baseline_mbt_16k）

本轮基线回放验收**未通过**。在一台 910C 的 16 个逻辑 DIE 上运行两个 DP2/TP4/EP8 实例。两套服务的 MBT 均为 **16,384**。

| 完成请求 | 实发 RPS | 平均 TTFT | P50 TTFT | P95 TTFT | 依赖空时隙 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,200 | 3.6611 | 11.789 秒 | 10.831 秒 | 24.272 秒 | 111 |

运行 ID 为 `20261128T063047Z-2064`。基于 `v0.3.0`（`4922a133`）运行基线用例。使用 16 条预热请求和 1,200 条正式冻结请求，按 4 RPS 发送，每条输出 1 token。CWS 和 Prefix Cache 均关闭。

回放验收要求实发接近 4 RPS（允许 ±0.01 RPS）且依赖空时隙为 0。表中时延按本轮实发统计。

## 文件索引

- `repo/runs/20261128T063047Z-2064/baseline-acceptance.json` 保存判定、两套服务的生效参数、每个端点的完成数和回放指标。
- 同一运行目录保存预检、启动日志、native 映射、长短输入探针、预热、逐请求数据和 Prometheus 前后快照。
- `repo/.runtime/` 保存完整终端输出、退出状态和设备探针。包内还包含实际站点配置、镜像 ID、底座摘要、型号及设备记录。
- 在 `v0.3.0` 上应用 `1128_4rps_baseline_mbt_16k.patch` 后，使用 `./reproduce.sh --site site.env --baseline-only` 可运行本用例。站点标识和单 token 作答文本已处理，完整原始证据在本地留档。
- `SHA256SUMS` 提供包内文件校验。

[固定版本与配置](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docs/acceptance.md) · [冻结负载](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

[证据包](afd-single910c-baseline-performance-evidence-1128_4rps_baseline_mbt_16k-20261128T063047Z-2064.tar.gz) · [验收报告](baseline-acceptance-1128_4rps_baseline_mbt_16k-20261128T063047Z-2064.json) · [SHA256](SHA256SUMS)
