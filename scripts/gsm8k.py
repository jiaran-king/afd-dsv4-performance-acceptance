"""Run the frozen GSM8K 0-shot and 8-shot acceptance scenarios."""

import argparse
import asyncio
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


CASE_DIR = Path(__file__).resolve().parents[1] / "cases/910c-dsv4-w4a8-rps4"
CONFIG = CASE_DIR / "case.json"
PROMPT = "Solve the problem. End with a line in the form #### <number>.\n\nQuestion: {question}\nAnswer:"
STOP = ["Question:", "</s>", "<|im_end|>"]
MARKED_ANSWER = re.compile(r"####[ \t]*([+-]?\d[\d,]*(?:\.\d+)?)")
NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
STANDALONE_ANSWER = re.compile(
    r"\s*(?:\*\*|\$|\\\$){0,2}\s*(" + NUMBER
    + r")\s*(?:%|\$|[a-zA-Z]+(?:[ -][a-zA-Z]+){0,3})?\s*[.!]?\s*(?:\*\*)?\s*\Z",
    re.I,
)
LABELED_ANSWER = re.compile(
    r"(?im)(?:\b(?:the (?:final )?answer|final answer)\s*(?:is\b|:)|####)"
    + r"\s*(?:\*\*|\$|\\\$){0,2}\s*(" + NUMBER + r")(?=\s|[.!%*$]|\Z)(?![.,]\d)"
)
BOXED_ANSWER = re.compile(r"\\boxed\{\s*(?:\$)?\s*(" + NUMBER + r")\s*(?:\\?%)?\s*\}")


def decimal(text):
    return Decimal(text.replace(",", ""))


def extract_answer(text):
    marked = MARKED_ANSWER.findall(text)
    if marked:
        return decimal(marked[-1]), "marker"
    standalone = STANDALONE_ANSWER.fullmatch(text.strip())
    if standalone:
        return decimal(standalone[1]), "standalone"
    conclusions = [match for rule in (LABELED_ANSWER, BOXED_ANSWER) for match in rule.finditer(text)]
    if conclusions:
        return decimal(max(conclusions, key=lambda match: match.start())[1]), "conclusion"
    return None, None


def load_dataset(config):
    path = CASE_DIR / config["dataset"]
    payload = path.read_bytes()
    rows = [json.loads(line) for line in payload.splitlines()]
    if [row["question_index"] for row in rows] != list(range(config["questions"])):
        raise ValueError(f"Expected GSM8K questions 0 through {config['questions'] - 1} in {path}")
    return rows, hashlib.sha256(payload).hexdigest()


def request_plan(rows, name):
    if name == "0-shot":
        return [(row, PROMPT.format(question=row["question"])) for row in rows]
    return sorted(((row, row["prompt_8shot"]) for row in rows), key=lambda item: -len(item[1]))


async def solve(client, endpoint, example, payload):
    gold = decimal(example["answer"])
    async with client.post(endpoint, json=payload) as response:
        response.raise_for_status()
        reply = await response.json()
    choice = reply["choices"][0]
    text = choice["text"]
    predicted, source = extract_answer(text)
    return {
        "question_index": example["question_index"],
        "gold": str(gold),
        "status": "ok",
        "answer": str(predicted) if predicted is not None else None,
        "answer_source": source,
        "correct": predicted == gold,
        "finish_reason": choice.get("finish_reason"),
        "text": text,
        "completion_tokens": reply.get("usage", {}).get("completion_tokens"),
    }


def write_summary(path, data):
    raw = json.dumps(data, indent=2) + "\n"
    path.write_text(raw, encoding="utf-8")
    return raw


async def evaluate_scenario(client, endpoints, out, rows, digest, name, settings):
    import aiohttp

    plan = request_plan(rows, name)
    requests = iter(enumerate(plan))
    generation = {
        "model": "dsv4",
        "max_tokens": settings["max_output_tokens"],
        "temperature": 0,
        "stop": STOP,
    }
    if "seed" in settings:
        generation["seed"] = settings["seed"]
    out.mkdir()
    record_file = out / "answers.jsonl"
    results = []
    print(f"GSM8K {name} started, {len(plan)} questions", flush=True)
    with record_file.open("x", encoding="utf-8", buffering=1) as output:
        async def worker():
            for position, (row, prompt) in requests:
                endpoint = endpoints[position % len(endpoints)]
                try:
                    result = await solve(client, endpoint, row, {**generation, "prompt": prompt})
                except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, IndexError, TypeError, ValueError) as error:
                    failure = {"question_index": row["question_index"], "status": "error", "error": str(error)}
                    output.write(json.dumps(failure, ensure_ascii=False) + "\n")
                    raise RuntimeError(f"GSM8K {name} request failed. See {record_file}") from error
                output.write(json.dumps(result, ensure_ascii=False) + "\n")
                results.append(result)
                if len(results) % 50 == 0 or len(results) == len(plan):
                    print(f"GSM8K {name} {len(results)}/{len(plan)}", flush=True)

        workers = [asyncio.create_task(worker()) for _ in range(settings["concurrency"])]
        try:
            await asyncio.gather(*workers)
        finally:
            for task in workers:
                task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)

    correct = sum(row["correct"] for row in results)
    write_summary(out / "summary.json", {
        "scenario": name,
        "dataset_sha256": digest,
        "questions": len(results),
        "correct": correct,
        "accuracy_pct": 100 * correct / len(results),
        "unparsed": sum(row["answer"] is None for row in results),
        "length_limited": sum(row["finish_reason"] == "length" for row in results),
        "max_output_tokens": settings["max_output_tokens"],
        "concurrency": settings["concurrency"],
        "temperature": generation["temperature"],
        "stop": generation["stop"],
        "seed": generation.get("seed"),
    })


async def evaluate(args, config):
    import aiohttp

    rows, digest = load_dataset(config)
    endpoints = [value.rstrip("/") + "/v1/completions" for value in args.endpoint]
    args.out.mkdir(parents=True)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300), trust_env=False) as client:
        for name, settings in config["scenarios"].items():
            await evaluate_scenario(client, endpoints, args.out / name, rows, digest, name, settings)


def compare(run, config):
    rows, digest = load_dataset(config)
    questions = len(rows)
    max_drop = Decimal(str(config["max_afd_drop_pp"]))
    outcomes = {}
    for name in config["scenarios"]:
        baseline, afd = (
            json.loads((run / f"{group}-gsm8k" / name / "summary.json").read_text(encoding="utf-8"))
            for group in ("baseline", "afd12")
        )
        if any(
            item["scenario"] != name or item["questions"] != questions or item["dataset_sha256"] != digest
            for item in (baseline, afd)
        ):
            raise ValueError(f"GSM8K {name} comparison requires two complete runs of the frozen questions")
        delta = afd["correct"] - baseline["correct"]
        outcomes[name] = {
            "baseline": baseline,
            "afd": afd,
            "afd_minus_baseline_pp": 100 * delta / questions,
            "passed": 100 * delta >= -max_drop * questions,
        }
    passed = all(outcome["passed"] for outcome in outcomes.values())
    print(write_summary(run / "gsm8k.json", {
        "questions": questions,
        "max_afd_drop_pp": config["max_afd_drop_pp"],
        "scenarios": outcomes,
        "gsm8k_passed": passed,
    }), end="")
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="mode", required=True)
    subcommands.add_parser("prepare")
    run = subcommands.add_parser("run")
    run.add_argument("--endpoint", action="append", required=True)
    run.add_argument("--out", type=Path, required=True)
    comparison = subcommands.add_parser("compare")
    comparison.add_argument("run", type=Path)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))["gsm8k"]
    if args.mode == "prepare":
        rows, _ = load_dataset(config)
        print(f"Prepared {len(rows)} frozen GSM8K questions for both scenarios")
    elif args.mode == "run":
        asyncio.run(evaluate(args, config))
    elif not compare(args.run, config):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
