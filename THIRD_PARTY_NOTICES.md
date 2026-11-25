# Third-party notices

The [vLLM](https://github.com/vllm-project/vllm) and [vLLM-Ascend](https://github.com/vllm-project/vllm-ascend) source revisions, official base image, and [AFD Plugin](https://github.com/vllm-project/afd-plugin/tree/0.30.0rc2) commit are recorded in [case.json](cases/910c-dsv4-w4a8-rps4/case.json). See the upstream source notices for each component.

The frozen performance requests have separate [attribution and license terms](cases/910c-dsv4-w4a8-rps4/DATASET.md), also supplied inside the Release payload.

The [GSM8K bundle](cases/910c-dsv4-w4a8-rps4/gsm8k-first300.jsonl) contains the first 300 test questions and their reference numbers from the [official OpenAI GSM8K revision](https://github.com/openai/grade-school-math/tree/b0bb162abedc65e1fdd8e93ed090fd7598ee68bc). The frozen 8-shot prompts reproduce the archived evaluation inputs and use training examples from the same revision. See the [GSM8K license](cases/910c-dsv4-w4a8-rps4/GSM8K-LICENSE).
