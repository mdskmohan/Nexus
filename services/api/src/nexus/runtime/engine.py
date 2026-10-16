"""Durable runs: start, execute, pause for a person, resume, stop, recover.

A run kind is a function registered with `@kind("name")` that takes a
`RunContext` and returns the run's output. It may be executed more than once:
when a run pauses for a person, its job ends, and when the person answers, a
new job executes the function again from the top. Two calls make that safe:

  * `ctx.checkpoint(key, fn)` runs `fn` once and saves its result in the run's
    state; on later executions it returns the saved result without running
    `fn` again, so paid or side-effecting work is never repeated;
  * `ctx.ask(key, ...)` asks a person for an approval or an answer. The first
    time, it records the request, moves the run to 'waiting' and ends this
    execution. Once the person has decided, it returns their decision.

Nothing is held in memory while a person decides.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from nexus import audit, jobs
from nexus.ai import registry
from nexus.ai.adapters import ModelRef, ModelUnavailable
from nexus.db import row, rows, scalar, tenant, unscoped
from nexus.runtime.recorder import RunRecorder
from nexus.security import can

log = logging.getLogger("nexus.runtime")

JOB_KIND = "run"
INTERRUPTED = "This run was interrupted before it finished (the server restarted). Please start it again."
REQUEST_KINDS = ("approval", "clarification")


class RunStopped(Exception):
    """The run cannot continue; the message is shown to people."""


class RunCancelled(Exception):
    """Someone stopped the run."""


class _Waiting(Exception):
    """The run is paused until a person decides."""


class DecisionError(Exception):
    """A decision that cannot be accepted; the message is shown to the person."""

    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Decision:
    status: str              # 'approved' | 'rejected' | 'answered'
    answer: str | None
    note: str | None
    decided_by: str

    @property
    def approved(self) -> bool:
        return self.status == "approved"


Handler = Callable[["RunContext"], dict]
_KINDS: dict[str, Handler] = {}


def kind(name: str) -> Callable[[Handler], Handler]:
    def register(handler: Handler) -> Handler:
        _KINDS[name] = handler
        return handler

    return register


def kinds() -> list[str]:
    return sorted(_KINDS)


class RunContext:
    def __init__(self, workspace_id: str, run: dict, recorder: RunRecorder):
        self.workspace_id = workspace_id
        self.run_id = str(run["id"])
        self.input: dict = run["input"]
        self.created_by = str(run["created_by"]) if run["created_by"] else None
        self.recorder = recorder
        self._state: dict = run["state"] or {}
        self._ai_model_id = str(run["ai_model_id"]) if run["ai_model_id"] else None
        self._model: ModelRef | None = None

    def step(self, kind: str, title: str, status: str = "ok", **detail: object) -> None:
        self.recorder.step(kind, title, status=status, **detail)

    def model(self) -> ModelRef:
        if self._model is None:
            self._model = registry.resolve(self.workspace_id, self._ai_model_id)
        return self._model

    def check_cancelled(self) -> None:
        if self.recorder.cancelled():
            raise RunCancelled

    def checkpoint(self, key: str, fn: Callable[[], Any]) -> Any:
        done = self._state.setdefault("done", {})
        if key in done:
            return done[key]
        self.check_cancelled()
        result = fn()
        done[key] = result
        with tenant(self.workspace_id) as s:
            scalar(s, "UPDATE runs SET state = CAST(:st AS jsonb) WHERE id = :r RETURNING id",
                   st=json.dumps(self._state, default=str), r=self.run_id)
        return result

    def ask(self, key: str, *, title: str, shown: dict | None = None, kind: str = "approval",
            permission: str = "approve_runs") -> Decision:
        """Ask a person. Returns their decision once there is one; until then the run waits."""
        if kind not in REQUEST_KINDS:
            raise ValueError(f"unknown request kind {kind!r}")
        with tenant(self.workspace_id) as s:
            existing = row(s, "SELECT * FROM human_requests WHERE run_id = :r AND key = :k", r=self.run_id, k=key)
            if existing and existing["status"] not in ("open", "cancelled"):
                return Decision(existing["status"], existing["answer"], existing["note"], str(existing["decided_by"]))
            if existing is None:
                request_id = scalar(
                    s,
                    """INSERT INTO human_requests (workspace_id, run_id, key, kind, title, shown, permission)
                       VALUES (:ws, :r, :k, :kind, :t, CAST(:shown AS jsonb), :p) RETURNING id""",
                    ws=self.workspace_id, r=self.run_id, k=key, kind=kind, t=title,
                    shown=json.dumps(shown or {}, default=str), p=permission,
                )
                audit.record(s, self.workspace_id, None, "run.asked_person", "human_request", request_id,
                             run_id=self.run_id, kind=kind, permission=permission)
            # The request and the pause commit together, so a decision can never arrive
            # for a run that is not yet waiting.
            paused = scalar(s, "UPDATE runs SET status = 'waiting' WHERE id = :r AND status = 'running' RETURNING id",
                            r=self.run_id)
        if paused is None:
            raise RunCancelled
        self.step("human", f"Waiting for a person: {title}", status="blocked", request_key=key, request_kind=kind)
        raise _Waiting


# Starting, stopping and deciding (called from the API) ---------------------

def start(session: Session, workspace_id: str, user_id: str | None, run_kind: str, title: str,
          input: dict | None = None, ai_model_id: str | None = None) -> str:
    if run_kind not in _KINDS:
        raise ValueError(f"unknown run kind {run_kind!r}")
    run_id = scalar(
        session,
        """INSERT INTO runs (workspace_id, kind, title, input, ai_model_id, created_by)
           VALUES (:ws, :k, :t, CAST(:i AS jsonb), :m, :u) RETURNING id""",
        ws=workspace_id, k=run_kind, t=title, i=json.dumps(input or {}, default=str), m=ai_model_id, u=user_id,
    )
    jobs.enqueue(session, workspace_id, JOB_KIND, {"run_id": str(run_id)}, max_attempts=1)
    audit.record(session, workspace_id, user_id, "run.started", "run", run_id, kind=run_kind)
    return str(run_id)


def cancel(session: Session, workspace_id: str, user_id: str, user_name: str, run_id: str) -> None:
    stopped = scalar(
        session,
        """UPDATE runs SET status = 'cancelled', error = :e, finished_at = now()
           WHERE id = CAST(:r AS uuid) AND status IN ('queued', 'running', 'waiting') RETURNING id""",
        e=f"Stopped by {user_name}.", r=run_id,
    )
    if stopped is None:
        raise DecisionError("This run has already finished.")
    scalar(session, """UPDATE human_requests SET status = 'cancelled'
                       WHERE run_id = CAST(:r AS uuid) AND status = 'open' RETURNING id""", r=run_id)
    audit.record(session, workspace_id, user_id, "run.cancelled", "run", run_id)


def decide(session: Session, workspace_id: str, user_id: str, role: str, request_id: str, decision: str,
           answer: str | None = None, note: str | None = None) -> None:
    """Record a person's decision and resume the run. Who may decide is set per request."""
    request = row(session, "SELECT * FROM human_requests WHERE id = CAST(:q AS uuid) FOR UPDATE", q=request_id)
    if request is None:
        raise DecisionError("No such request.", 404)
    if not can(role, request["permission"]):
        raise DecisionError("Your role does not allow you to decide this. Ask a colleague who can.", 403)
    if request["status"] != "open":
        raise DecisionError("This request has already been decided.")
    if request["kind"] == "approval" and decision not in ("approved", "rejected"):
        raise DecisionError("Approve or reject this request.", 422)
    if request["kind"] == "clarification":
        if decision != "answered" or not (answer or "").strip():
            raise DecisionError("Write an answer to continue.", 422)
    resumed = scalar(session, """UPDATE runs SET status = 'queued'
                                 WHERE id = :r AND status = 'waiting' RETURNING id""", r=request["run_id"])
    if resumed is None:
        raise DecisionError("This run is no longer waiting.")
    scalar(
        session,
        """UPDATE human_requests SET status = :st, answer = :a, note = :n, decided_by = :u, decided_at = now()
           WHERE id = :q RETURNING id""",
        st=decision, a=(answer or "").strip() or None, n=(note or "").strip() or None, u=user_id, q=request["id"],
    )
    jobs.enqueue(session, workspace_id, JOB_KIND, {"run_id": str(request["run_id"])}, max_attempts=1)
    audit.record(session, workspace_id, user_id, f"request.{decision}", "human_request", request["id"],
                 run_id=str(request["run_id"]), note=note)


# Executing (called from the worker) -----------------------------------------

def execute(workspace_id: str, payload: dict) -> None:
    run_id = payload["run_id"]
    with tenant(workspace_id) as s:
        run = row(s, "SELECT * FROM runs WHERE id = :r", r=run_id)
    if run is None:
        return
    recorder = RunRecorder(workspace_id, run_id)
    if run["status"] == "running":
        # A worker picked this run up before and died mid-way. Paid AI work is not
        # silently repeated: tell the person, who can start it again.
        recorder.fail(INTERRUPTED)
        return
    if run["status"] != "queued" or not recorder.start():
        return
    handler = _KINDS.get(run["kind"])
    try:
        if handler is None:
            raise RunStopped("This kind of run is no longer available.")
        output = handler(RunContext(workspace_id, run, recorder))
        recorder.succeed(output)
        with tenant(workspace_id) as s:
            audit.record(s, workspace_id, run["created_by"], "run.succeeded", "run", run_id,
                         kind=run["kind"], cost_usd=round(recorder.usage.cost_usd, 4))
    except _Waiting:
        pass
    except RunCancelled:
        recorder.step("error", "Stopped at your request.", status="warning")
    except ModelUnavailable as exc:
        log.error("run %s: %s", run_id, exc.technical)
        recorder.step("error", str(exc), status="error", error=exc.technical)
        recorder.fail(str(exc))
    except RunStopped as exc:
        recorder.step("error", str(exc), status="error")
        recorder.fail(str(exc))
    except Exception as exc:
        log.exception("run %s failed", run_id)
        recorder.step("error", "Something went wrong on our side. The run was stopped.", status="error",
                      error=f"{exc.__class__.__name__}: {exc}")
        recorder.fail("Something went wrong on our side. Please try again; if it keeps happening, "
                      "contact support with the run id.")


def close_orphaned_runs() -> int:
    """Runs left 'running' although their job is no longer being worked on."""
    with unscoped() as s:
        # A resumed run has several jobs; it is orphaned only if none of them is still live.
        finished = rows(s, f"""SELECT DISTINCT j.workspace_id, j.payload->>'run_id' AS run_id FROM jobs j
                               WHERE j.kind = '{JOB_KIND}' AND j.status IN ('done', 'failed')
                                 AND j.created_at > now() - interval '7 days'
                                 AND NOT EXISTS (SELECT 1 FROM jobs live
                                                 WHERE live.kind = j.kind AND live.status IN ('queued', 'running')
                                                   AND live.payload->>'run_id' = j.payload->>'run_id')""")
    closed = 0
    for j in finished:
        with tenant(j["workspace_id"]) as s:
            stuck = scalar(s, "SELECT 1 FROM runs WHERE id = CAST(:r AS uuid) AND status = 'running'", r=j["run_id"])
        if stuck:
            RunRecorder(str(j["workspace_id"]), j["run_id"]).fail(INTERRUPTED)
            closed += 1
    return closed


HANDLERS = {JOB_KIND: execute}
