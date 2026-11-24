# Ascend 910C 上机步骤

## 准备环境

在同一对 910C 机器上启动两个匹配的 aarch64 容器，分别分配 16 个逻辑 DIE，并挂载同一份 DeepSeek-V4-Flash W4A8/DSpark checkpoint。P/D 之间需要可达的 Mooncake 通信网卡。将 Git checkout 放在两端容器能以相同绝对路径访问的共享目录。

容器应包含固定版本的 vLLM 与 vLLM-Ascend 源码、Ascend custom vendor、CANN 开发工具链、Git、Bash、curl 和 Python 3.9+。参考镜像 tag、软件提交、算子和模型指纹见 [case.json](../cases/910c-dsv4-w4a8-rps4/case.json)。预检通过源码版本、模型配置、量化描述和 tokenizer 指纹核对准备环境。

## 设置现场参数

复制 `site.env.example` 为 `site.env`，填写 P/D 地址、网卡、逻辑设备列表和模型路径。

- 控制端在 P 容器时，`P_SSH` 留空。配置 `D_SSH`，SSH 到宿主机时一并填写 `D_CONTAINER`。
- 控制端独立运行时，填写 `P_SSH` 和 `D_SSH`。`SHARED_ROOT` 是两端容器内的 checkout 路径，`SITE_REMOTE_FILE` 可指定两端共享的配置文件。
- 集群有自带的执行器时，用 `NODE_EXEC` 指定可执行文件。它接收 `P` 或 `D`，以及在目标容器运行的命令和参数。

P 节点使用 HTTP 7100、7101、8000–8002，D 节点使用 HTTP 7100。为本次验收使用专用 P/D 容器，并开放相应的 DP RPC 和 KV 端口。 [端口配置](../cases/910c-dsv4-w4a8-rps4/config.env)

## 准备与运行

~~~bash
./reproduce.sh --site site.env --prepare-only
./reproduce.sh --site site.env
~~~

完整入口会自动准备运行时。可用 `--prepare-only` 提前检查和准备。入口从 Release 获取约 20 MB 的冻结请求包，并校验包及每个 split 的 SHA256。没有直连 GitHub 的环境可预先下载同一请求包，在 `site.env` 中设置 `WORKLOAD_ARCHIVE`。入口检出固定 AFD 版本并编译扩展，为 vLLM-Ascend 应用 CWS workspace 和 Mooncake KV 导出补丁，在专用运行时目录准备配套算子。已有同指纹的 CWS vendor 可以通过 `CWS_VENDOR_DIR` 指定。

上机阶段在同一对节点依次运行双 EP8、12A+4F FULL 和 8A+8F 功能用例。双 EP8 的两个 P 实例分别通过 PD 冒烟后合用正式 proxy。每组性能回放的发压约 5 分钟，环境构建、模型加载、冒烟和预热另计。F 图计数通过现有健康检查在正式窗口前后采样。

若 P 容器也无法从 GitHub 检出 AFD，在有网络的机器准备固定提交的 Git checkout，再将其连同 `.git` 放在共享仓库的 `.runtime/afd-plugin` 下。准备入口会核对提交。 [AFD 提交](../cases/910c-dsv4-w4a8-rps4/case.json)

## 查看与复核

查看 `runs/<run-id>/acceptance.json` 的 `acceptance_passed`、`reduction_pct` 和两个回放结果。四个 F rank 的图重放在 `ffn_full_replay`，8A+8F 的两次 PD 请求在 `afd8_pd_smoke`。预检、启动日志、实加载库、客户端计时及 KV 记录位于同一运行目录。 [验收标准](acceptance.md)
