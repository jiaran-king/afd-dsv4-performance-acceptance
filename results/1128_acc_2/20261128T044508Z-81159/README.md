# 2026-11-28 单机 910C GSM8K 精度验收（1128_acc_2）

整体判定为**通过**。每个场景中，AFD 正确率最多允许比同轮双 EP8 基线低 1.5 个百分点。

| 场景 | 双 EP8 | AFD 12A+4F | AFD 正确率差 | 判定 |
| --- | ---: | ---: | ---: | --- |
| 0-shot | 279/300（93.00%） | 281/300（93.67%） | +0.67 pp | 通过 |
| 8-shot | 287/300（95.67%） | 286/300（95.33%） | -0.33 pp | 通过 |

运行 ID 为 `20261128T044508Z-81159`。两组在同一台 910C 的 16 个逻辑 DIE 上依次运行 `v0.3.0`（`4922a133`），使用同一镜像、DeepSeek-V4-Flash W4A8 权重和冻结的 GSM8K 前 300 题。0-shot 并发 32、输出上限 1,024 token，8-shot 并发 12、输出上限 512 token。

## 文件索引

- `repo/runs/20261128T044508Z-81159/gsm8k.json` 是现场验收报告。该目录也保存四组逐题作答、评分摘要、服务日志和运行时记录。
- `repo/.runtime/` 保存完整终端输出、退出状态和设备探针。包内包含实际站点配置、镜像 ID、底座摘要、模型和设备记录。
- `offline-rescore.json` 记录冻结评分器对全部 1,200 条作答的离线复核。发布包处理了站点和内部网络标识，逐题作答原文保留。
- `repo/scripts/gsm8k.py` 和对应题集均来自正式标签。题集许可随包保存，可使用 `SHA256SUMS` 校验包内文件。

[正式验收配置](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/blob/v0.3.0/docs/acceptance.md#gsm8k-评分) · [GSM8K 来源](https://github.com/openai/grade-school-math/tree/b0bb162abedc65e1fdd8e93ed090fd7598ee68bc)

[证据包](afd-single910c-accuracy-evidence-1128_acc_2-20261128T044508Z-81159.tar.gz) · [验收报告](gsm8k-acceptance-1128_acc_2-20261128T044508Z-81159.json) · [SHA256](SHA256SUMS)
