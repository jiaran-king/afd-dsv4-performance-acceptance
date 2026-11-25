# DeepSeek-V4-Flash W4A8 AFD 性能验收

在同一对 Ascend 910C 节点上，以相同设备预算和完整 PD 分离比较原生双 EP8 8K 与 AFD 12A+4F。两组关闭 CWS。验收按现场同轮基线计算平均 TTFT 降幅，要求达到 **20%**。

## 运行环境与版本

| 组件 | 本用例版本 | 公开来源 |
| --- | --- | --- |
| 运行镜像 | aarch64 · A3/openEuler 24.03 · Python 3.12 · CANN 9.1.0 | 基础镜像 `quay.io/ascend/cann:9.1.0-a3-openeuler24.03-py3.12`。[官方 A3 Dockerfile](https://github.com/vllm-project/vllm-ascend/blob/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6/Dockerfile.a3.openEuler) |
| 模型权重 | DeepSeek-V4-Flash W4A8 + DSpark，revision `59b8e36964b964140dad8e580e14247564744ac9` | [ModelScope 模型 UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test](https://www.modelscope.cn/models/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test) |
| vLLM | 官方标签 `v0.30.0` · `ced6857afa0ea7b2e3f0846a62e1394e90f15607` | [官方提交](https://github.com/vllm-project/vllm/commit/ced6857afa0ea7b2e3f0846a62e1394e90f15607) |
| vLLM-Ascend | 构建提交 `8d4409d6256d8a6729140ddcc0d1889e3f96cdd6` | [获取起点 `v0.30.0rc1`](https://github.com/vllm-project/vllm-ascend/tree/v0.30.0rc1) · [官方提交](https://github.com/vllm-project/vllm-ascend/commit/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6) |
| AFD | `release/v0.30.0rc2` · `98f45bbff76bb5165789313c1076fea5c92d8c44` | [官方提交，包含共享专家 DP 修复](https://github.com/vllm-project/afd-plugin/commit/98f45bbff76bb5165789313c1076fea5c92d8c44) |

AFD 的 `v0.30.0rc2` 标签指向修复前的 `39017a1`，本用例固定该发布分支合入修复后的 `98f45bb`。vLLM-Ascend 的构建提交在 `v0.30.0rc1` 的历史中，实测包版本为 `0.19.1rc2.dev2448+g8d4409d62`。[AFD RC2 标签](https://github.com/vllm-project/afd-plugin/tree/v0.30.0rc2)

实测使用的 Ascend 驱动为 `25.5.1.1`，`torch-npu` 为 `2.10.0.post4`。现场已有兼容镜像和同版权重时可以直接使用，验收会记录实际版本。[镜像构建和权重下载](docs/reproduce-910c.md#从公开来源准备镜像和权重) · [用例配置](cases/910c-dsv4-w4a8-rps4/case.json)

## 上机验收

准备同一对各有 16 DIE 的 910C 节点，按指南填写 `site.env`，从 P 容器执行以下命令。[上机指南](docs/reproduce-910c.md)

~~~bash
./reproduce.sh --site site.env
~~~

默认性能用例为双 EP8 8K 对 **12A+4F、A 侧 DP3/TP4、A/F MBT 16K、F FULL、A 侧 `enable_shared_expert_dp=true`**。另跑 8A+8F PD 冒烟验证灵活配比。结果写入 `runs/<run-id>/acceptance.json`，同目录保留逐请求计时和运行证据。

[原表要求与判定](docs/acceptance.md) · [冻结请求包](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)
