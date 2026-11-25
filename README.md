# DeepSeek-V4-Flash W4A8 AFD 性能验收

在**一台 Ascend 910C** 上顺序比较原生双 EP8 8K 与 AFD 12A+4F 16K。两组使用同一镜像、权重和冻结请求，每条输出 **1 token**。验收按现场同轮基线计算平均 TTFT 降幅，要求达到 **20%**。

已有约定镜像和权重时，从填写 `site.env` 开始。需要准备镜像时，按环境构建指南拉取官方底座、构建并核对容器。[上机指南](docs/reproduce-910c.md) · [构建 910C 验收环境](docs/build-environment-910c.md)

## 运行环境与版本

| 组件 | 本用例版本 | 公开来源 |
| --- | --- | --- |
| 运行镜像底座 | aarch64 · A3/openEuler 24.03 · Python 3.12 · CANN 9.2.1 | `quay.io/ascend/vllm-ascend:v0.30.0-a3-openeuler`。[Dockerfile](docker/Dockerfile.a3) |
| 模型权重 | DeepSeek-V4-Flash W4A8 + DSpark，revision `59b8e36964b964140dad8e580e14247564744ac9` | [ModelScope 模型 UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test](https://www.modelscope.cn/models/UploadWeight/DeepSeek-V4-Flash-DSpark-w4a8-test) |
| vLLM | 官方标签 `v0.30.0` · `ced6857afa0ea7b2e3f0846a62e1394e90f15607` | [官方提交](https://github.com/vllm-project/vllm/commit/ced6857afa0ea7b2e3f0846a62e1394e90f15607) |
| vLLM-Ascend | 构建提交 `8d4409d6256d8a6729140ddcc0d1889e3f96cdd6` | [获取起点 `v0.30.0rc1`](https://github.com/vllm-project/vllm-ascend/tree/v0.30.0rc1) · [官方提交](https://github.com/vllm-project/vllm-ascend/commit/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6) |
| 推理依赖 | PyTorch `2.10.0` · TorchNPU `2.10.0.post4` · Triton Ascend `3.2.2` | [固定 Ascend 提交的依赖表](https://github.com/vllm-project/vllm-ascend/blob/8d4409d6256d8a6729140ddcc0d1889e3f96cdd6/requirements.txt) |
| AFD | 官方标签 `0.30.0rc2` · `98f45bbff76bb5165789313c1076fea5c92d8c44` | [官方标签](https://github.com/vllm-project/afd-plugin/tree/0.30.0rc2) · [共享专家 DP 修复提交](https://github.com/vllm-project/afd-plugin/commit/98f45bbff76bb5165789313c1076fea5c92d8c44) |

运行镜像复用预装的 vLLM，并从表中固定提交重新编译 vLLM-Ascend 的 A3 算子。现场软件版本和模型指纹随结果记录。[准备权重路径](docs/build-environment-910c.md#2-准备权重路径) · [用例配置](cases/910c-dsv4-w4a8-rps4/case.json)

## 上机验收

在 **910C 容器的验收仓根目录**运行。

~~~bash
./reproduce.sh --site site.env
~~~

默认性能用例为双 EP8 8K 对 **12A+4F、A 侧 DP3/TP4、A/F MBT 16K、F FULL、A 侧 `enable_shared_expert_dp=true`**。另跑 8A+8F 单机首 token 冒烟验证灵活配比。结果写入 `runs/<run-id>/acceptance.json`，同目录保留逐请求计时和运行证据。

GSM8K 使用独立入口，报告基线和 AFD 的数值答案正确率及差值。

~~~bash
./reproduce.sh --site site.env --gsm8k
~~~

[原表要求与判定](docs/acceptance.md) · [冻结请求包](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/releases/tag/v0.1.0)

[历史双机 PD 复现](https://github.com/jiaran-king/afd-dsv4-performance-acceptance/tree/e60348b0c9f9c48b28711e15fb5bf061d52ad38a)
