"""LegalBench: 162 legal-reasoning tasks (Guha et al., NeurIPS 2023).

Includes the contract suites CUAD (38 clause-type tasks), ContractNLI (14)
and MAUD (34 merger-agreement tasks), plus rule application, issue spotting,
interpretation and rhetorical-understanding tasks.

Data and the per-task instruction, answer space and scoring method all come
from the official release (huggingface.co/datasets/nguha/legalbench), so
scores are comparable with other reported LegalBench numbers. Tasks are run
zero-shot with the official instruction. We report the official scoring
method for each task and, for classification tasks, balanced accuracy (the
headline metric in the LegalBench paper).
"""

import csv
import io
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nexus import llm

SOURCE = "https://huggingface.co/datasets/nguha/legalbench/resolve/main"

SUITES = {
    "contracts": lambda t: t.startswith(("cuad_", "contract_nli_", "maud_")) or t in {
        "consumer_contracts_qa", "contract_qa", "contract_nli_explicit_identification",
        "insurance_policy_interpretation", "jcrew_blocker", "unfair_tos",
        "supply_chain_disclosure_best_practice_accountability"},
    "cuad": lambda t: t.startswith("cuad_"),
    "contract_nli": lambda t: t.startswith("contract_nli_"),
    "maud": lambda t: t.startswith("maud_"),
    "all": lambda t: True,
}

SYSTEM = ("You are completing a legal reasoning benchmark. Read the task and answer it. "
          "Reply with the answer only: no explanation, no punctuation, no extra words.")


@dataclass
class TaskResult:
    task: str
    eval_method: str
    n: int = 0
    score: float = 0.0                 # official scoring method
    balanced_accuracy: float | None = None
    cost_usd: float = 0.0
    errors: int = 0
    examples: list[dict] = field(default_factory=list)


def _fetch(url: str, cache: Path) -> bytes:
    if cache.exists():
        return cache.read_bytes()
    cache.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 (fixed https source)
        data = response.read()
    cache.write_bytes(data)
    return data


def metadata(cache_dir: Path) -> dict:
    return json.loads(_fetch(f"{SOURCE}/task_metadata.json", cache_dir / "task_metadata.json"))


def load_task(task: str, cache_dir: Path) -> list[dict]:
    data = _fetch(f"{SOURCE}/data/{task}/test.tsv", cache_dir / task / "test.tsv").decode("utf-8")
    return list(csv.DictReader(io.StringIO(data), delimiter="\t"))


def render(instruction: str, row: dict) -> str:
    return re.sub(r"\{\{(\w+)\}\}", lambda m: row.get(m.group(1), ""), instruction)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def score_one(method: str, gold: str, output: str) -> bool:
    out = _norm(output)
    if method == "numeric_within_1pct":
        numbers = re.findall(r"-?\d[\d,]*\.?\d*", output.replace("$", ""))
        try:
            value, target = float(numbers[-1].replace(",", "")), float(gold.replace(",", ""))
        except (IndexError, ValueError):
            return False
        return abs(value - target) <= abs(target) * 0.01
    golds = [_norm(g) for g in gold.split(",")] if method in ("all_in_output", "any_in_output") else [_norm(gold)]
    if method == "all_in_output":
        return all(g in out for g in golds)
    if method == "any_in_output":
        return any(g in out for g in golds)
    return golds[0] == out or re.search(rf"\b{re.escape(golds[0])}\b", out) is not None


def predicted_label(output: str, answer_space: list[str]) -> str | None:
    """The single label in the answer space that the output names, if exactly one."""
    out = _norm(output)
    exact = [a for a in answer_space if _norm(a) == out]
    if exact:
        return exact[0]
    named = [a for a in answer_space if re.search(rf"\b{re.escape(_norm(a))}\b", out)]
    return named[0] if len(named) == 1 else None


def balanced_accuracy(pairs: list[tuple[str, str | None]]) -> float:
    by_class: dict[str, list[bool]] = {}
    for gold, pred in pairs:
        by_class.setdefault(_norm(gold), []).append(pred is not None and _norm(pred) == _norm(gold))
    recalls = [sum(v) / len(v) for v in by_class.values()]
    return sum(recalls) / len(recalls) if recalls else 0.0


def run_task(task: str, meta: dict, cache_dir: Path, limit: int | None, model: str | None,
             effort: str | None, workers: int) -> TaskResult:
    rows = load_task(task, cache_dir)[: limit or None]
    spec = meta[task]
    result = TaskResult(task, spec["eval_method"], n=len(rows))
    answer_space = spec.get("answer_space") or []
    options = (f"\n\n(Answer with one of: {', '.join(answer_space)})"
               if answer_space and len(answer_space) <= 12 else "")

    def ask(row: dict) -> tuple[dict, str, float]:
        prompt = render(spec["instruction"], row) + options
        try:
            response, usage = llm.call(system=SYSTEM, messages=[{"role": "user", "content": prompt}],
                                       max_tokens=4000, model=model, effort=effort)
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            return row, text, usage.cost_usd
        except llm.ModelUnavailable:
            raise
        except Exception as exc:  # one bad request should not end a benchmark run
            return row, f"__error__ {exc.__class__.__name__}", 0.0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        outputs = list(pool.map(ask, rows))

    correct, pairs = 0, []
    for row, text, cost in outputs:
        gold = row["answer"]
        result.cost_usd += cost
        if text.startswith("__error__"):
            result.errors += 1
        ok = score_one(spec["eval_method"], gold, text)
        correct += ok
        if answer_space and spec["eval_method"] == "contained_in_output":
            pairs.append((gold, predicted_label(text, answer_space)))
        if len(result.examples) < 5 and not ok:
            result.examples.append({"index": row.get("index"), "gold": gold, "output": text[:300]})
    result.score = correct / len(rows) if rows else 0.0
    if pairs:
        result.balanced_accuracy = balanced_accuracy(pairs)
    return result


def run(suite: str, tasks: list[str] | None, limit: int | None, cache_dir: Path, model: str | None,
        effort: str | None, workers: int = 8, max_cost: float | None = None, progress=print) -> dict:
    meta = metadata(cache_dir)
    selected = tasks or sorted(t for t in meta if SUITES[suite](t))
    unknown = [t for t in selected if t not in meta]
    if unknown:
        raise SystemExit(f"Unknown LegalBench task(s): {', '.join(unknown)}")
    results, spent = [], 0.0
    for i, task in enumerate(selected, 1):
        if max_cost is not None and spent >= max_cost:
            progress(f"Stopping: spending limit ${max_cost:.2f} reached.")
            break
        r = run_task(task, meta, cache_dir, limit, model, effort, workers)
        spent += r.cost_usd
        results.append(r)
        ba = f"  balanced acc {r.balanced_accuracy:.3f}" if r.balanced_accuracy is not None else ""
        progress(f"[{i}/{len(selected)}] {task}: {r.score:.3f} ({r.n} examples){ba}  ${r.cost_usd:.2f}")
    scored = [r for r in results if r.n]
    return {
        "benchmark": "legalbench",
        "suite": suite,
        "limit_per_task": limit,
        "tasks": len(scored),
        "examples": sum(r.n for r in scored),
        "mean_score": sum(r.score for r in scored) / len(scored) if scored else 0.0,
        "mean_balanced_accuracy": (lambda xs: sum(xs) / len(xs) if xs else None)(
            [r.balanced_accuracy for r in scored if r.balanced_accuracy is not None]),
        "cost_usd": round(spent, 4),
        "results": [asdict(r) for r in results],
    }
