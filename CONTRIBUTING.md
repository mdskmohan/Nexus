# Contributing to Nexus

These are the standards every change is held to. They exist so the codebase stays
legible as it grows and so review can focus on design rather than formatting.

---

## Principles

1. **The IR is sacred.** `PipelineSpec` is the contract between every subsystem. Changing
   it is an ADR-level decision, never a drive-by edit.
2. **The LLM never executes.** Models propose; the control plane decides and acts. Any
   code path where model output reaches a production system without passing through the
   policy engine is a bug, not a feature.
3. **Evidence over assertion.** A diagnosis without a timestamped, sourced piece of
   evidence behind it does not ship. We would rather say "unknown" than guess confidently.
4. **Deterministic where possible.** Use the model for ranking, explanation and language.
   Use ordinary code for collecting facts, traversing graphs, and generating artifacts.

---

## Python (services/api)

- **Version:** 3.11+
- **Formatting:** `ruff format` (line length 100)
- **Linting:** `ruff check` — the configured rule set is not advisory
- **Typing:** `mypy --strict`. Every public function is annotated. `Any` requires a comment
  explaining why it is unavoidable.
- **Models:** Pydantic v2 for anything crossing a boundary (API, IR, persisted state).
- **Docstrings:** every public module, class and function. Explain *why*, not *what* —
  the signature already says what.
- **Errors:** raise domain exceptions from `nexus.errors`. Never raise bare `Exception`,
  never swallow one silently.

```python
def rank_hypotheses(
    incident: Incident,
    evidence: Sequence[Evidence],
) -> list[RankedHypothesis]:
    """Order candidate root causes by supporting evidence strength.

    Ranking is deliberately separate from evidence collection so that the
    collectors stay deterministic and independently testable.
    """
```

## TypeScript (apps/web)

- **Formatting:** Prettier, 2-space indent, no semicolon debates — the config decides
- **Linting:** ESLint with the Next.js config, `no-explicit-any` enabled
- **Typing:** `strict: true`. No `any`, no non-null assertions without a comment.
- **Components:** function components only. Props typed via an exported `interface`.
- **State:** server components by default; `"use client"` only where interaction requires it.

## Design system

The UI is token-driven. Read `apps/web/app/globals.css` before writing a component.

- Use semantic tokens (`bg-danger-soft`, `text-muted-foreground`), never raw palette
  values (`bg-red-500/15`).
- Typography is a five-step scale: `display`, `h1`, `h2`, `body`, `caption`. Do not add
  a sixth. Never `text-[13px]`.
- Spacing follows a 4px rhythm. No `py-3.5`.
- Light and dark are parity-locked: every token defined in one is defined in the other.

---

## Testing

- Unit tests live beside the code they cover, in `services/api/tests/`.
- Every evidence collector has a test that feeds it a known-bad environment and asserts
  the evidence it produces — these are the tests that decide whether the product works.
- The compiler has golden-file tests: a `PipelineSpec` in, an exact artifact out.
- Tests must not reach the network. Fixtures over live connections, always.

```bash
make test              # everything
pytest services/api/tests/test_ir.py -v
```

## Commits

Conventional commits, imperative mood, scope required:

```
feat(ir): add freshness contract to Source
fix(compiler): emit incremental strategy for append-only models
docs(adr): record the decision to drop vendor recommendation
```

The subject line says what changed. The body says why it was worth changing.

## Pull requests

A PR is ready when:

- [ ] `make check` and `make test` pass
- [ ] New behaviour has a test that would fail without the change
- [ ] Public functions and modules are documented
- [ ] Any IR or architecture change has a corresponding ADR
- [ ] The description explains the *why*, not a restatement of the diff
