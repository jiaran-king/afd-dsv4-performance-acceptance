# 官方 A3 成品镜像派生方案

这套方案基于 CANN `9.2.1`，构建和上机验证待完成。正式验收使用已实测的 CANN `9.1.0` 环境。[正式上机指南](../../reproduce-910c.md)

Dockerfile 以 `quay.io/ascend/vllm-ascend:v0.30.0-a3-openeuler` 为底座，固定镜像 digest。它复用镜像内的 vLLM `ced6857a`，从官方 vLLM-Ascend 提交 `8d4409d6` 重新安装插件并编译 A3 自定义算子。[Dockerfile](Dockerfile.a3) · [官方镜像](https://docs.vllm.ai/projects/ascend/en/v0.30.0/getting_started/installation.html#installation-prebuilt-image)

在安装 Docker 的 ARM64 构建机上，从验收仓根目录执行。

~~~bash
cd docs/development/official-a3-image
docker build --platform linux/arm64 -f Dockerfile.a3 -t afd-910c-acceptance:official .
~~~
