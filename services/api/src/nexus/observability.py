"""The activity record for AI runs.

Every step an agent takes is written as a plain-language line a lawyer can
read ("Searched the documents for 'termination'. 6 passages found.") plus a
structured `detail` for engineers. Each step is committed on its own so the
activity feed updates live while the agent is still working.
"""

import json
import time
from uuid import UUID

from nexus.ai.adapters import ModelRef, Usage
from nexus.db import row, scalar, tenant


class RunRecorder:
    def __init__(self, firm_id: UUID | str, run_id: UUID | str):
        self.firm_id = str(firm_id)
        self.run_id = str(run_id)
        self.usage = Usage()
        self._seq = 0

    def step(self, kind: str, title: str, status: str = "ok", duration_ms: int | None = None,
             **detail: object) -> None:
        self._seq += 1
        with tenant(self.firm_id) as s:
            scalar(
                s,
                """INSERT INTO run_steps (firm_id, run_id, seq, kind, title, status, detail, duration_ms)
                   VALUES (:firm, :run, :seq, :kind, :title, :status, CAST(:detail AS jsonb), :ms)
                   RETURNING id""",
                firm=self.firm_id, run=self.run_id, seq=self._seq, kind=kind, title=title,
                status=status, detail=json.dumps(detail, default=str), ms=duration_ms,
            )

    def meter(self, usage: Usage, model: str, ref: ModelRef | None = None) -> None:
        self.usage.add(usage)
        with tenant(self.firm_id) as s:
            scalar(
                s,
                """UPDATE runs SET input_tokens = :i, output_tokens = :o,
                          cache_read_tokens = :c, cost_usd = :cost, model = :model,
                          provider = coalesce(:provider, provider)
                   WHERE id = :run RETURNING id""",
                i=self.usage.input_tokens, o=self.usage.output_tokens,
                c=self.usage.cache_read_tokens, cost=round(self.usage.cost_usd, 4),
                model=model, provider=ref.kind if ref else None, run=self.run_id,
            )

    def start(self) -> None:
        with tenant(self.firm_id) as s:
            scalar(s, "UPDATE runs SET status = 'running', started_at = now() WHERE id = :r RETURNING id",
                   r=self.run_id)

    def finish(self, output: dict, guardrails: dict) -> None:
        with tenant(self.firm_id) as s:
            scalar(
                s,
                """UPDATE runs SET status = 'needs_review', output = CAST(:out AS jsonb),
                          guardrails = CAST(:g AS jsonb), finished_at = now()
                   WHERE id = :r RETURNING id""",
                out=json.dumps(output, default=str), g=json.dumps(guardrails, default=str),
                r=self.run_id,
            )

    def fail(self, message: str) -> None:
        with tenant(self.firm_id) as s:
            scalar(
                s,
                """UPDATE runs SET status = 'failed', error = :e, finished_at = now()
                   WHERE id = :r RETURNING id""",
                e=message, r=self.run_id,
            )


class Timer:
    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, *_):
        self.ms = int((time.monotonic() - self.start) * 1000)


def firm_metrics(firm_id: UUID | str, days: int = 30) -> dict:
    """Headline numbers for the Safety & Activity page."""
    with tenant(firm_id) as s:
        runs = row(
            s,
            """SELECT count(*) AS runs,
                      count(*) FILTER (WHERE status = 'failed') AS failed,
                      count(*) FILTER (WHERE status IN ('approved')) AS approved,
                      count(*) FILTER (WHERE status = 'needs_review') AS awaiting_review,
                      coalesce(sum(cost_usd), 0) AS cost_usd,
                      coalesce(sum((guardrails->>'citations_checked')::int), 0) AS citations_checked,
                      coalesce(sum((guardrails->>'citations_verified')::int), 0) AS citations_verified,
                      coalesce(sum((guardrails->>'statements_removed')::int), 0) AS statements_removed,
                      coalesce(avg(extract(epoch FROM finished_at - started_at))
                               FILTER (WHERE finished_at IS NOT NULL), 0) AS avg_seconds
               FROM runs WHERE created_at > now() - make_interval(days => :days)""",
            days=days,
        )
        docs = row(
            s,
            """SELECT count(*) AS documents,
                      count(*) FILTER (WHERE (flags->>'hidden_instruction_count')::int > 0) AS with_hidden_instructions,
                      count(*) FILTER (WHERE flags->'sensitive' <> '{}'::jsonb) AS with_sensitive_numbers
               FROM documents""",
        )
    return {**{k: float(v) if hasattr(v, "is_finite") else v for k, v in runs.items()}, **docs}
