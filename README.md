# DeepSeek-V4-Flash W4A8 AFD 性能验收

在两台 Ascend 910C 上，以相同设备预算和完整 PD 分离比较原生双 EP8 8K 与开启共享专家 DP 的 12A+4F。参考实验中，平均 TTFT 从 **3.041 秒**降到 **1.732 秒**，降幅 **43.04%**。上机验收用同轮实测基线计算，要求降低至少 **20%**。

- [原表要求与判定](docs/acceptance.md)
- [910C 上机验收指南](docs/reproduce-910c.md)
- [实测证据](results/2026-11-24/README.md)
- [冻结请求包](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

## 上机验收

准备同一对各有 16 DIE 的 910C 节点、现场的 aarch64 运行时镜像及同一份 W4A8/DSpark checkpoint。按上机指南查询现场地址、网卡、DIE 和权重路径，填好 `site.env` 后从 P 容器运行。 [上机步骤与配置示例](docs/reproduce-910c.md)

默认性能用例为双 EP8 8K 对 **12A+4F、A 侧 DP3/TP4、A/F MBT 32K、F FULL、A 侧 `enable_shared_expert_dp=true`**。入口随后用 8A+8F 实际跑 PD 请求，验证灵活配比。结果写入 `runs/<run-id>/acceptance.json`，同目录保留逐请求计时和运行证据。
