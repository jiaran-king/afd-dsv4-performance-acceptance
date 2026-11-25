"""Run the official GSM8K test split and report numerical exact-match accuracy."""

import argparse
import asyncio
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen

import aiohttp


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "cases/910c-dsv4-w4a8-rps4/case.json"
DATASET = ROOT / ".runtime/downloads/gsm8k-test.jsonl"
ANSWER = re.compile(r"####[ \t]*([+-]?\d[\d,]*(?:\.\d+)?)")
PROMPT = "Solve the problem. End with a line in the form #### <number>.\n\nQuestion: {question}\nAnswer:"
STOP = ["Question:", "</s>", "<|im_end|>"]
CONCURRENCY = 32


def final_number(text):
    answers = ANSWER.findall(text)
    return Decimal(answers[-1].replace(",", "")) if answers else None


def load_dataset(config, dataset, download=False):
    path = dataset if dataset is not None else DATASET
    if download and dataset is None and not path.is_file():
        with urlopen(config["source"], timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != config["sha256"]:
            raise ValueError("Downloaded GSM8K test split has the wrong checksum")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != config["sha256"]:
        raise ValueError(f"GSM8K test split has the wrong checksum: {path}")
    rows = [json.loads(line) for line in payload.splitlines()]
    if len(rows) != config["questions"] or any(final_number(row["answer"]) is None for row in rows):
        raise ValueError("Expected the complete GSM8K test split with numerical answers")
    return rows


async def solve(client, endpoint, index, example, max_tokens):
    gold = final_number(example["answer"])
    payload = {
        "model": "dsv4",
        "prompt": PROMPT.format(question=example["question"]),
        "temperature": 0,
        "max_tokens": max_tokens,
        "stop": STOP,
    }
    base = {"question_index": index, "gold": str(gold)}
    try:
        async with client.post(endpoint, json=payload) as response:
            response.raise_for_status()
            reply = await response.json()
        choice = reply["choices"][0]
        text = choice["text"]
        predicted = final_number(text)
        return {
            **base, "status": "ok", "answer": str(predicted) if predicted is not None else None,
            "correct": predicted == gold, "finish_reason": choice.get("finish_reason"), "text": text,
            "completion_tokens": reply.get("usage", {}).get("completion_tokens"),
        }
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, IndexError, ValueError) as error:
        return {**base, "status": "error", "correct": False, "error": str(error)}


async def evaluate(args, config):
    rows = load_dataset(config, args.dataset)
    urls = [value.rstrip("/") + "/v1/completions" for value in args.endpoint]
    args.out.mkdir(parents=True)
    results = []
    questions = iter(enumerate(rows))
    with (args.out / "answers.jsonl").open("x", encoding="utf-8", buffering=1) as output:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300), trust_env=False) as client:
            async def worker():
                for index, example in questions:
                    row = await solve(client, urls[index % len(urls)], index, example, config["max_output_tokens"])
                    output.write(json.dumps(row, ensure_ascii=False) + "\n")
                    if row["status"] == "error":
                        raise RuntimeError(f"GSM8K request failed. See {args.out / 'answers.jsonl'}")
                    results.append(row)
                    if len(results) % 128 == 0 or len(results) == len(rows):
                        print(f"GSM8K {len(results)}/{len(rows)}", flush=True)

            workers = [asyncio.create_task(worker()) for _ in range(CONCURRENCY)]
            try:
                await asyncio.gather(*workers)
            finally:
                for task in workers:
                    task.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
    correct = sum(row["correct"] for row in results)
    summary = {
        "dataset_sha256": config["sha256"],
        "questions": len(results),
        "correct": correct,
        "accuracy_pct": 100 * correct / len(results),
        "unparsed": sum(row["answer"] is None for row in results),
        "length_limited": sum(row["finish_reason"] == "length" for row in results),
        "max_output_tokens": config["max_output_tokens"],
        "temperature": 0,
        "concurrency": CONCURRENCY,
        "stop": STOP,
        "prompt_template": PROMPT,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def compare(run, config):
    baseline, afd = (
        json.loads((run / f"{group}-gsm8k/summary.json").read_text())
        for group in ("baseline", "afd12")
    )
    for summary in (baseline, afd):
        if summary["questions"] != config["questions"] or summary["dataset_sha256"] != config["sha256"]:
            raise ValueError("GSM8K comparison requires both complete test sets")
    report = {
        "baseline": baseline, "afd": afd,
        "afd_minus_baseline_pp": afd["accuracy_pct"] - baseline["accuracy_pct"],
    }
    raw = json.dumps(report, indent=2) + "\n"
    (run / "gsm8k.json").write_text(raw)
    print(raw, end="")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="mode", required=True)
    prepare = subcommands.add_parser("prepare")
    prepare.add_argument("--dataset", type=Path)
    run = subcommands.add_parser("run")
    run.add_argument("--dataset", type=Path)
    run.add_argument("--endpoint", action="append", required=True)
    run.add_argument("--out", type=Path, required=True)
    comparison = subcommands.add_parser("compare")
    comparison.add_argument("run", type=Path)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())["gsm8k"]
    if args.mode == "prepare":
        rows = load_dataset(config, args.dataset, download=True)
        print(f"Prepared the official GSM8K test split ({len(rows)} questions)")
    elif args.mode == "run":
        asyncio.run(evaluate(args, config))
    else:
        compare(args.run, config)


if __name__ == "__main__":
    main()
