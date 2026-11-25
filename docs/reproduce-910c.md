# 单台 Ascend 910C 上机验收

使用同一台 910C 上的 **8 张物理卡、16 个逻辑 DIE**。在已启动的验收容器内，从第 1 步开始。[正式验收版本](../README.md#运行环境与版本) · [构建镜像和挂载权重](build-environment-910c.md)

## 1. 填写 `site.env`

在容器的验收仓根目录执行，将模板字段改成现场值。

~~~bash
cp site.env.example site.env
~~~

| 字段 | 怎么填 |
| --- | --- |
| `P_NODE_IP`、`P_NIC` | 填本机用于 HCCL / Gloo 通信的 IPv4 和对应网卡。可用 `ip -br -4 addr` 或现场网络信息查询。 |
| `P_DEVICES` | 从 `npu-smi info -m` 取分配给本次测试的 **16 个逻辑 DIE ID**，用逗号分隔。 |
| `P_MODEL_DIR` | 填容器内的 checkpoint 根目录，其中包含模型配置、量化描述、tokenizer 和权重分片。 |
| `VLLM_SOURCE`、`ASCEND_SOURCE`、`CANN_ROOT` | 交付镜像使用模板路径时采用默认值。现场路径不同时填实际值。 |

## 2. 运行验收

~~~bash
./reproduce.sh --site site.env
~~~

脚本自动准备固定的 AFD 提交和冻结请求包。它顺序运行双 EP8 8K、12A+4F AFD 16K 和 8A+8F 单机冒烟。两组正式回放各用 1,200 条请求，固定 4 RPS，关闭 Prefix Cache，每条输出 1 token。已有冻结包时可通过 `WORKLOAD_ARCHIVE` 指定它。[用例和判定](acceptance.md)

## 3. 查看结果

打开运行目录里的 `acceptance.json`。**`acceptance_passed` 为 `true` 即通过**。`reduction_pct` 是相对同轮双 EP8 基线的平均 TTFT 降幅。逐请求记录、F FULL 重放证据、8A+8F 冒烟和实际软件版本都在同一个运行目录。

## 运行 GSM8K

~~~bash
./reproduce.sh --site site.env --gsm8k
~~~

两组分别完成官方测试集，输出完整解答。脚本用相同的提示模板、确定性生成设置和数值匹配规则评分。打开独立运行目录中的 `gsm8k.json`，查看两组正确率和 AFD 相对基线的百分点差值。结果用于报告，暂不设通过门槛。已有固定版本的测试集时，可通过 `GSM8K_FILE` 指定它。[官方 GSM8K](https://github.com/openai/grade-school-math/tree/b0bb162abedc65e1fdd8e93ed090fd7598ee68bc)
