# DeepSeek-V4-Flash W4A8 AFD 性能验收

在两台 Ascend 910C 上，以相同设备预算和完整 PD 分离比较原生双 EP8 与 Prefill 异步 A/F。参考的两轮配对中，12A+4F 的平均 TTFT 分别降低 **23.40%** 和 **25.08%**。验收按各自同轮基线计算，要求降低至少 **20%**。

- [原表要求与判定](docs/acceptance.md)
- [910C 上机步骤](docs/reproduce-910c.md)
- [两轮实测证据](results/2026-11-24/README.md)
- [冻结请求包](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

## 先复算参考结果

在有 Bash 和 Python 3.9+ 的机器上克隆本仓，然后复算参考结果。

~~~bash
./reproduce.sh --verify-reference
~~~

脚本用逐请求计时、D 端 KV 收据和 F 端图重放计数复算两轮结果。

## 上机验收

准备同一对各有 16 DIE 的 910C 节点、匹配的容器镜像及同一份 W4A8/DSpark checkpoint。将本仓放在两端容器都能访问的共享目录。

~~~bash
cp site.env.example site.env
# 按现场环境填写 site.env。
./reproduce.sh --site site.env --prepare-only
./reproduce.sh --site site.env
~~~

默认性能用例为双 EP8 8K 对 **12A+4F、A 侧 DP3/TP4、A/F MBT 32K、F FULL、A 侧共享专家 DP 关闭**。入口随后用 8A+8F 实际跑 PD 请求，验证灵活配比。结果写入 `runs/<run-id>/acceptance.json`，同目录保留逐请求计时和运行证据。
