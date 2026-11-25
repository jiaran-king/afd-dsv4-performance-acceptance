"""Send a frozen prompt to one local service and verify its first token."""

import argparse
import asyncio
import json
from pathlib import Path

import aiohttp

from replay import request_body, send


def choose_row(dataset, min_prompt_tokens, max_prompt_tokens):
    with dataset.open(encoding="utf-8") as workload:
        for line in workload:
            row = json.loads(line)
            if min_prompt_tokens <= row["prompt_tokens"] <= max_prompt_tokens:
                return row
    raise ValueError(f"{dataset} has no prompt of {min_prompt_tokens}–{max_prompt_tokens} tokens")


async def smoke(args):
    row = choose_row(args.dataset, args.min_prompt_tokens, args.max_prompt_tokens)
    args.output.mkdir(parents=True)
    events = asyncio.Queue()
    url = args.endpoint.rstrip("/") + "/v1/completions"
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180), trust_env=False) as client:
        await send(client, url, row, request_body(row["prompt"]), events)
    result = events.get_nowait()
    report = json.dumps(result, indent=2) + "\n"
    (args.output / "result.json").write_text(report)
    print(report, end="")
    if result["status"] != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--min-prompt-tokens", type=int, default=1024)
    parser.add_argument("--max-prompt-tokens", type=int, default=32768)
    asyncio.run(smoke(parser.parse_args()))
