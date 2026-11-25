# Third-party notices

The reference run's [vLLM](https://github.com/vllm-project/vllm) and [vLLM-Ascend](https://github.com/vllm-project/vllm-ascend) revisions are recorded in [case.json](cases/910c-dsv4-w4a8-rps4/case.json). A new run uses the site's source trees and the AFD commit pinned in that file. The pinned commit is based on [AFD Plugin v0.30.0rc2](https://github.com/vllm-project/afd-plugin/tree/v0.30.0rc2). The CWS MRV2 patch retains its source and author attribution. Use the upstream source notices for the corresponding files and builds.

The request data have separate [attribution and license terms](cases/910c-dsv4-w4a8-rps4/DATASET.md), also supplied inside the Release payload. Use your existing container and model access to obtain the reference checkpoint and CANN runtime.
