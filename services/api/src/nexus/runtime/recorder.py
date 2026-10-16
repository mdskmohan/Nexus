"""The activity record of a run.

Every step is written as a plain-language line a person can read ("Asked
Priya to approve the plan.") plus a structured `detail` for engineers. Each
step is committed on its own so the activity feed updates live while the run
is still working. Tokens and cost add up across every stretch of a run,
including after it resumes from a pause.
"""

import json
import time
from uuid import UUID

from nexus.ai.adapters import ModelRef, Usage
from nexus.db import row, scalar, tenant


class RunRecorder:
    def __init__(self, workspace_id: UUID | str, run_id: UUID | str):
        self.workspace_id = str(workspace_id)
        self.run_id = str(run_id)
        self._seq: int | None = None
        self.usage = Usage()

    def load(self) -> None:
        """Pick up the step count and the usage so far (a resumed run continues both)."""
        with tenant(self.workspace_id) as s:
            r = row(s, """SELECT input_tokens, output_tokens, cache_read_tokens, cost_usd,
                                 (SELECT coalesce(max(seq), 0) FROM run_steps WHERE run_id = :r) AS seq
                          FROM runs WHERE id = :r""", r=self.run_id)
        if r:
            self._seq = r["seq"]
            self.usage = Usage(r["input_tokens"], r["output_tokens"], r["cache_read_tokens"], 0, float(r["cost_usd"]))

    def step(self, kind: str, title: str, status: str = "ok", duration_ms: int | None = None,
             **detail: object) -> None:
        with tenant(self.workspace_id) as s:
            if self._seq is None:
                self._seq = scalar(s, "SELECT coalesce(max(seq), 0) FROM run_steps WHERE run_id = :r", r=self.run_id)
            self._seq += 1
            scalar(
                s,
                """INSERT INTO run_steps (workspace_id, run_id, seq, kind, title, status, detail, duration_ms)
                   VALUES (:ws, :run, :seq, :kind, :title, :status, CAST(:detail AS jsonb), :ms)
                   RETURNING id""",
                ws=self.workspace_id, run=self.run_id, seq=self._seq, kind=kind, title=title,
                status=status, detail=json.dumps(detail, default=str), ms=duration_ms,
            )

    def meter(self, usage: Usage, model: str, ref: ModelRef | None = None) -> None:
        self.usage.add(usage)
        with tenant(self.workspace_id) as s:
            scalar(
                s,
                """UPDATE runs SET input_tokens = input_tokens + :i, output_tokens = output_tokens + :o,
                          cache_read_tokens = cache_read_tokens + :c, cost_usd = cost_usd + :cost,
                          model = :model, provider = coalesce(:provider, provider)
                   WHERE id = :run RETURNING id""",
                i=usage.input_tokens, o=usage.output_tokens, c=usage.cache_read_tokens,
                cost=round(usage.cost_usd, 4), model=model, provider=ref.kind if ref else None, run=self.run_id,
            )

    def cancelled(self) -> bool:
        with tenant(self.workspace_id) as s:
            return scalar(s, "SELECT status = 'cancelled' FROM runs WHERE id = :r", r=self.run_id) is True

    def start(self) -> bool:
        """Mark the run as running. False if it is no longer queued (stopped meanwhile)."""
        with tenant(self.workspace_id) as s:
            started = scalar(s, """UPDATE runs SET status = 'running', started_at = coalesce(started_at, now())
                                   WHERE id = :r AND status = 'queued' RETURNING id""", r=self.run_id)
        if started:
            self.load()
        return started is not None

    def succeed(self, output: dict) -> None:
        with tenant(self.workspace_id) as s:
            scalar(
                s,
                """UPDATE runs SET status = 'succeeded', output = CAST(:out AS jsonb), finished_at = now()
                   WHERE id = :r AND status = 'running' RETURNING id""",
                out=json.dumps(output, default=str), r=self.run_id,
            )

    def fail(self, message: str) -> None:
        with tenant(self.workspace_id) as s:
            scalar(
                s,
                """UPDATE runs SET status = 'failed', error = :e, finished_at = now()
                   WHERE id = :r AND status IN ('queued', 'running') RETURNING id""",
                e=message, r=self.run_id,
            )


class Timer:
    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, *_):
        self.ms = int((time.monotonic() - self.start) * 1000)
