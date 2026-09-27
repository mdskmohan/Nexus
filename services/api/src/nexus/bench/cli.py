"""nexus-bench: run public legal benchmarks against Nexus.

    uv run nexus-bench legalbench --suite contracts --limit 25 --max-cost 20
    uv run nexus-bench lab --lab-root ~/harvey-labs --task corporate-ma/... [--evaluate]
    uv run nexus-bench lab --lab-root ~/harvey-labs --sample 10 --seed 7

Every run costs real money (model calls). Use --limit / --sample and
--max-cost to control spend. Results are written to var/bench/results/.
"""

import argparse
import json
import random
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from nexus.ai.adapters import ANTHROPIC, COMPATIBLE, DEFAULT_PRICES, GOOGLE, KINDS, OPENAI, ModelRef
from nexus.bench import india_chronology, india_notice, india_review, lab, legalbench
from nexus.config import REPO_ROOT, settings

KEY_ENV = {ANTHROPIC: "ANTHROPIC_API_KEY", OPENAI: "OPENAI_API_KEY", GOOGLE: "GEMINI_API_KEY",
           COMPATIBLE: "NEXUS_BENCH_API_KEY"}

RESULTS = REPO_ROOT / "var" / "bench" / "results"
CACHE = REPO_ROOT / "var" / "bench" / "cache"


def _save(name: str, data: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{name}-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(data, indent=2, default=str))
    return path


def model_ref(args) -> ModelRef:
    """The model under test, from the command line. Keys come from the environment (or .env)."""
    import os

    from dotenv import dotenv_values

    env = {**dotenv_values(REPO_ROOT / ".env"), **os.environ}
    model = args.model or (settings().model if args.provider == ANTHROPIC else None)
    if not model:
        raise SystemExit(f"Give --model for provider {args.provider}.")
    key = env.get(KEY_ENV[args.provider]) or (env.get("GOOGLE_API_KEY") if args.provider == GOOGLE else None)
    if not key and args.provider != COMPATIBLE:
        raise SystemExit(f"Set {KEY_ENV[args.provider]} in .env or the environment.")
    price_in, price_out = args.price if args.price else DEFAULT_PRICES.get(model, (None, None))
    return ModelRef(kind=args.provider, model=model, api_key=key, base_url=args.base_url, label=model,
                    price_in=price_in, price_out=price_out, fallbacks=settings().model_fallbacks)


def cmd_legalbench(args) -> None:
    ref = model_ref(args)
    effort = args.effort or settings().effort
    data = legalbench.run(args.suite, args.task or None, args.limit, CACHE / "legalbench", ref,
                          effort, workers=args.workers, max_cost=args.max_cost)
    data.update(provider=ref.kind, model=ref.model, effort=effort)
    path = _save(f"legalbench-{args.suite}", data)
    ba = data["mean_balanced_accuracy"]
    print(f"\nLegalBench ({args.suite}): {data['tasks']} tasks, {data['examples']} examples")
    print(f"  mean score (official method): {data['mean_score']:.3f}")
    if ba is not None:
        print(f"  mean balanced accuracy:       {ba:.3f}")
    print(f"  cost: ${data['cost_usd']:.2f}\n  saved: {path}")


def cmd_lab(args) -> None:
    root = Path(args.lab_root).expanduser().resolve()
    ids = args.task or []
    if args.sample:
        pool = [t for t in lab.list_tasks(root) if not args.area or t.startswith(args.area)]
        # Seeded so a benchmark sample can be reproduced exactly; not security-sensitive.
        rng = random.Random(args.seed)  # noqa: S311
        ids = rng.sample(pool, min(args.sample, len(pool)))
    if not ids:
        raise SystemExit("Give --task (one or more) or --sample N.")
    ref = model_ref(args)
    results, spent = [], 0.0
    for i, task_id in enumerate(ids, 1):
        if args.max_cost is not None and spent >= args.max_cost:
            print(f"Stopping: spending limit ${args.max_cost:.2f} reached.")
            break
        print(f"[{i}/{len(ids)}] {task_id}")
        r = lab.run_task(root, task_id, args.max_docs, ref)
        spent += r.get("cost_usd", 0.0)
        if r.get("skipped"):
            print(f"  skipped: {r['skipped']}")
        else:
            print(f"  {r['status']} in {r['duration_seconds']}s, ${r['cost_usd']:.2f} -> {r['run_id']}")
            if args.evaluate and r["status"] == "needs_review":
                judges = args.judges or ["claude-opus-4-8"]
                uv = shutil.which("uv")
                if uv is None:
                    raise SystemExit("LAB's evaluator runs with uv; install it from https://docs.astral.sh/uv/")
                subprocess.run(  # noqa: S603 (fixed command; arguments come from this CLI)
                    [uv, "run", "python", "-m", "lab_core.evaluation.run_eval", "--run-id", r["run_id"],
                     "--task", task_id, "--judges", *judges], cwd=root, check=False)
                for name in ("scores_dual.json", "scores.json", *[f"scores_{j}.json" for j in judges]):
                    p = root / "results" / r["run_id"] / name
                    if p.exists():
                        s = json.loads(p.read_text())
                        r["score"] = {k: s.get(k) for k in ("score", "all_pass", "n_passed", "n_criteria")}
                        print(f"  graded: {r['score']}")
                        break
        results.append(r)
    path = _save("lab", {"benchmark": "harvey-lab", "provider": ref.kind, "model": ref.model,
                         "tasks": results, "cost_usd": round(spent, 4)})
    print(f"\nsaved: {path}")
    if not args.evaluate:
        print("Grade with LAB's own evaluator, from the LAB checkout:\n"
              "  uv run python -m lab_core.evaluation.run_eval --run-id <run_id> --task <task> "
              "[--judges claude-opus-4-8]")


def cmd_india(args) -> None:
    ref = model_ref(args)
    print(f"Nexus India contract review: {len(india_review.CASES)} contracts on {ref.model}")
    data = india_review.run(ref)
    data.update(provider=ref.kind, model=ref.model)
    path = _save("india-review", data)
    recall = data["issue_recall"]
    print(f"\n  issue recall: {recall:.0%}" if recall is not None else "\n  no review completed")
    print(f"  false alarms: {data['false_alarms']}\n  citations verified: {data['citations_verified']}")
    print(f"  cost: ${data['cost_usd']:.2f}\n  saved: {path}")
    print("  (answer keys not yet validated by a practising lawyer)")


def cmd_india_notice(args) -> None:
    ref = model_ref(args)
    print(f"Nexus India s.138 notices: {len(india_notice.CASES)} cases on {ref.model}")
    data = india_notice.run(ref)
    data.update(provider=ref.kind, model=ref.model)
    path = _save("india-notice", data)
    for k in ("completed", "first_time_right", "no_extra_demand", "cites_section_138"):
        print(f"  {k.replace('_', ' ')}: {data[k]:.0%}")
    print(f"  cost: ${data['cost_usd']:.2f}\n  saved: {path}")


def cmd_india_chronology(args) -> None:
    ref = model_ref(args)
    print(f"Nexus India list of dates: {len(india_chronology.EXPECTED)} expected events on {ref.model}")
    data = india_chronology.run(ref)
    data.update(provider=ref.kind, model=ref.model)
    print(f"  saved: {_save('india-chronology', data)}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="nexus-bench", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=KINDS, default=ANTHROPIC, help="Model provider under test.")
    parser.add_argument("--model", default=None, help="Model id (default: NEXUS_MODEL for anthropic).")
    parser.add_argument("--base-url", default=None, help="Endpoint for openai_compatible (e.g. Ollama).")
    parser.add_argument("--price", type=float, nargs=2, metavar=("IN", "OUT"),
                        help="USD per million input/output tokens, for cost reporting.")
    parser.add_argument("--effort", default=None, help="Override NEXUS_EFFORT for this run.")
    parser.add_argument("--max-cost", type=float, default=None, help="Stop once this many USD are spent.")
    sub = parser.add_subparsers(required=True)

    lb = sub.add_parser("legalbench", help="LegalBench (incl. CUAD, ContractNLI, MAUD)")
    lb.add_argument("--suite", choices=sorted(legalbench.SUITES), default="contracts")
    lb.add_argument("--task", action="append", help="Run only this task (repeatable).")
    lb.add_argument("--limit", type=int, default=None, help="Examples per task (default: all).")
    lb.add_argument("--workers", type=int, default=8)
    lb.set_defaults(func=cmd_legalbench)

    lb2 = sub.add_parser("lab", help="Harvey LAB (Legal Agent Benchmark)")
    lb2.add_argument("--lab-root", required=True, help="Path to a checkout of github.com/harveyai/harvey-labs")
    lb2.add_argument("--task", action="append", help="Task id, e.g. corporate-ma/... (repeatable).")
    lb2.add_argument("--sample", type=int, default=0, help="Run N randomly chosen tasks.")
    lb2.add_argument("--area", default="", help="With --sample: only tasks under this practice area.")
    lb2.add_argument("--seed", type=int, default=0)
    lb2.add_argument("--max-docs", type=int, default=150, help="Skip tasks with more documents than this.")
    lb2.add_argument("--evaluate", action="store_true", help="Grade each run with LAB's evaluator.")
    lb2.add_argument("--judges", nargs="+", help="LAB judge models (default claude-opus-4-8).")
    lb2.set_defaults(func=cmd_lab)

    ind = sub.add_parser("india-review", help="Nexus India contract-review benchmark (planted issues)")
    ind.set_defaults(func=cmd_india)
    sub.add_parser("india-notice", help="Nexus India s.138 cheque-dishonour notices").set_defaults(func=cmd_india_notice)
    sub.add_parser("india-chronology", help="Nexus India list of dates and events").set_defaults(
        func=cmd_india_chronology)

    args = parser.parse_args()
    args.func(args)
