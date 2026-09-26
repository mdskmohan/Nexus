# Observability

Two audiences, one record.

## For lawyers: "What the AI did"

Every agent step is written to `run_steps` with a plain-language `title`, a
`status` (`ok`, `warning`, `blocked`, `error`) and a `kind`. The task page shows
these as a live timeline. Titles are generated deterministically from the tool
call, not by the model, so they are accurate:

| Step | Example title |
|---|---|
| search | Searched for "termination for convenience". 6 passages found in MSA.docx. |
| read | Read Globex MSA.pdf, page 12 to page 13. |
| finding | Duration of the obligations: deviates (page 2). |
| check (warning) | A safety check sent the AI's work back to fix: Statement 2 (…): The quoted words do not appear in the cited passage. |
| answer | Answer ready: 4 statements, 7 citations checked word for word. |
| model (warning) | Answered by the backup model (claude-opus-4-8). |
| error | Stopped at the spending limit for one task ($5.00). |

The *Safety & activity* page aggregates the last 30 days: tasks, quotes
verified, statements removed, tasks awaiting review, flagged documents, and cost.

## For engineers

- **Step detail.** `run_steps.detail` holds the tool name, input and outcome
  (passage ids returned, verification failures, finding payloads). In the UI:
  *Show technical details*.
- **Metering.** `runs.input_tokens`, `output_tokens`, `cache_read_tokens`,
  `cost_usd`, `model`, updated after every model call. Cost uses the per-model
  prices in `nexus/llm.py` (cache reads at 10% and 5-minute cache writes at
  125% of the input price).
- **Timing.** `runs.started_at` / `finished_at`, and `duration_ms` for each
  tool step.
- **Logs.** API and worker log to stdout (`nexus.api`, `nexus.jobs`,
  `nexus.tasks`); unhandled errors are logged with stack traces and shown to
  users as a generic message.
- **Health.** `GET /api/health` checks the database and reports whether a model
  key is configured.
- **Jobs.** The `jobs` table records attempts, last error and lock owner; stale
  locks (worker died) are reclaimed after 30 minutes.

## Useful queries

```sql
-- Slowest tasks this week
SELECT kind, title, finished_at - started_at AS took, cost_usd
FROM runs WHERE created_at > now() - interval '7 days' ORDER BY took DESC NULLS LAST LIMIT 20;

-- Citation send-backs by agent kind
SELECT kind, sum((guardrails->>'sent_back_to_fix')::int) AS sent_back, count(*) AS runs
FROM runs GROUP BY kind;

-- Failed jobs
SELECT kind, attempts, last_error FROM jobs WHERE status = 'failed' ORDER BY id DESC LIMIT 20;
```

(Run as the owner role, or inside a transaction with `app.firm_id` set, since
tenant tables are protected by row-level security.)
