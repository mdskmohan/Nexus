# Benchmarks

Nexus is measured on public legal benchmarks using their **official data and
official scoring**, so results are comparable with published numbers. Every run
calls the model and costs money; use the limits below.

Every command takes the model under test: `--provider anthropic|openai|google|openai_compatible`,
`--model`, and for compatible endpoints `--base-url`. Keys are read from `.env` or the
environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `NEXUS_BENCH_API_KEY`).
`--price IN OUT` (USD per million tokens) adds costs for models without list prices.

## Nexus India benchmarks

Nexus's own benchmarks for its Indian use cases. The data is original and
fictional; answer keys were written with the data and **have not yet been
validated by a practising lawyer**, and results say so.

| Command | Use case | Scored on |
|---|---|---|
| `nexus-bench india-review` | Contract review under Indian law: a Pune services agreement, a Bengaluru NDA and a Hyderabad employment agreement, each with planted issues | Issue recall, false alarms, citation integrity, completion |
| `nexus-bench india-notice` | Section 138 cheque-dishonour notices: five cases from ₹75,000 to ₹2.87 crore | Completed, first time right against the entered facts, no extra sums demanded, cites s.138 |

```bash
cd services/api
uv run nexus-bench --provider google --model <gemini model> india-review
uv run nexus-bench --provider anthropic --model claude-opus-5 india-notice
```

Public Indian benchmark: **IL-TUR** (ACL 2024; 8 tasks on Indian legal text,
including statute identification, judgment prediction and summarisation) is on
Hugging Face as `Exploration-Lab/IL-TUR`. It is gated (access is approved by
the authors) and licensed CC BY-NC-SA 4.0, so it can be used for internal
evaluation but not redistributed or used commercially.

## LegalBench (includes CUAD, ContractNLI, MAUD)

[LegalBench](https://hazyresearch.stanford.edu/legalbench/) (Guha et al.,
NeurIPS 2023) is 162 legal-reasoning tasks written by lawyers and legal
academics. It includes the main contract benchmarks as sub-suites:

| Suite (`--suite`) | Tasks | What it tests |
|---|---|---|
| `cuad` | 38 | Clause identification from the Contract Understanding Atticus Dataset |
| `contract_nli` | 14 | Whether an NDA clause entails a stated obligation (ContractNLI) |
| `maud` | 34 | Merger-agreement deal-point questions (MAUD) |
| `contracts` | 92 | All of the above plus six other contract tasks |
| `all` | 162 | Everything, including rule application, issue spotting and interpretation |

**Method.** Data, instructions, answer spaces and scoring methods come from the
official release (`nguha/legalbench` on Hugging Face) and are cached under
`var/bench/cache`. Tasks run zero-shot with the official instruction; the
allowed answers are appended when there are 12 or fewer. We report the official
scoring method for each task, and balanced accuracy for classification tasks
(the headline metric in the LegalBench paper).

```bash
cd services/api
# Contract suite, 25 examples per task, stop at $20
uv run nexus-bench --max-cost 20 legalbench --suite contracts --limit 25
# One task, all examples
uv run nexus-bench legalbench --task contract_nli_notice_on_compelled_disclosure
```

What it measures: the model with Nexus's defaults (model, effort) on
single-question legal reasoning. It does **not** exercise Nexus's agents or
citation checks; that is what LAB is for.

## Harvey LAB (Legal Agent Benchmark)

[LAB](https://github.com/harveyai/harvey-labs) (Harvey AI, MIT licence)'s
public repository has more than 1,600 tasks across 24 practice areas plus
contracting. Each gives an agent a matter
file (Word, Excel, PowerPoint, email, PDF) and instructions, and asks for
deliverables such as memos, issues lists and schedules. An LLM judge grades each
deliverable against expert-written rubric criteria. **A task scores 1 only if
every criterion passes.**

**Method.** `nexus-bench lab` runs the **real Nexus pipeline** on a LAB task:
it ingests the task's documents into a matter (inside an isolated "Benchmarks"
firm), runs the drafting agent on LAB's instructions with LAB's deliverable
names, and writes the files into LAB's results layout. **LAB's own evaluator
then grades them, unchanged.**

```bash
git clone https://github.com/harveyai/harvey-labs ~/harvey-labs   # ~3.5 GB
cd ~/harvey-labs && uv sync                                        # LAB's evaluator dependencies

cd <nexus>/services/api
# One task, graded with a Claude judge
uv run nexus-bench lab --lab-root ~/harvey-labs \
  --task antitrust-competition/analyze-antitrust-hsr-strategy --evaluate
# A reproducible random sample of 10 corporate M&A tasks, stop at $60
uv run nexus-bench --max-cost 60 lab --lab-root ~/harvey-labs --sample 10 --area corporate-ma --seed 1 --evaluate
```

**Judges.** LAB's standard profile uses two judges (`claude-sonnet-4-6` and
`gpt-5.5`) and needs an OpenAI key as well. `--judges` passes any LAB-supported
judge list through; results graded with a non-standard judge set are labelled
as such by LAB and should not be compared directly with the standard
leaderboard.

**Notes**
- Unsupported file types in a data room (images, for example) are skipped and
  counted in `metrics.json`.
- Tasks with more than `--max-docs` documents (default 150) are skipped.
- `metrics.json` records cost, tokens, duration, steps by kind, the guardrail
  summary and document ingestion results.

## Results

No results are published yet. Benchmark numbers will be added to
`docs/benchmarks/results.md` with the exact command, date, model, effort,
sample and cost for each run, so they can be reproduced.
