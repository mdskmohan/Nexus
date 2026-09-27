# HTTP API

Interactive reference (OpenAPI): http://localhost:8100/api/docs when the API is
running.

All endpoints are under `/api`, use JSON, and authenticate with the session
cookie. State-changing requests need the header `X-Nexus-Client: <anything>`.
Errors are `{"detail": "<plain-English message>"}`.

## Auth and team

| Method | Path | Role | |
|---|---|---|---|
| POST | `/auth/signup` | — | Create a firm and its admin; seeds starter playbooks |
| POST | `/auth/login` | — | |
| POST | `/auth/logout` | — | |
| GET | `/me` | any | User, firm, whether a model key is configured |
| GET | `/team` | any | |
| POST | `/team` | admin | Add a member with a temporary password |
| PATCH | `/team/{user_id}` | admin | Change role or disable |
| PATCH | `/firm` | partner | Firm name and preferences |

## Matters and documents

| Method | Path | Role | |
|---|---|---|---|
| GET / POST | `/matters` | any | |
| GET / PATCH | `/matters/{id}` | any | |
| GET | `/matters/{id}/documents` | any | Includes status and scan flags |
| POST | `/matters/{id}/documents` | any | Multipart `files`; processing is asynchronous |
| GET | `/documents/{id}` | any | |
| GET | `/documents/{id}/passages` | any | The passages the AI searches and cites |
| GET | `/documents/{id}/file` | any | Original file (audited) |
| DELETE | `/documents/{id}` | associate | |

## AI tasks

| Method | Path | Role | Body |
|---|---|---|---|
| POST | `/matters/{id}/ask` | any | `{question}` |
| POST | `/matters/{id}/reviews` | any | `{document_id, playbook_id, client_role, instructions?}` |
| POST | `/matters/{id}/drafts` | any | `{instructions, deliverables: ["memo.docx", …]}` |
| POST | `/matters/{id}/notices/cheque` | any | Facts for a s.138 notice (see `ChequeNoticeRequest`) |
| POST | `/notices/cheque/timeline` | any | `{cheque_date, presented_on, information_received_on, amount?}`: statutory timeline only, no AI |
| GET | `/matters/{id}/runs` | any | |
| GET | `/runs/{id}` | any | Output, guardrail summary, steps, files, cost |
| POST | `/runs/{id}/approve` | associate | `{note?}` |
| POST | `/runs/{id}/reject` | associate | `{note?}` |
| POST | `/runs/{id}/cancel` | any | Stop a queued or running task |
| GET | `/files/{id}` | any | Generated file (audited) |

Task creation returns `{id}` immediately (201). Poll `GET /runs/{id}` until
`status` is `needs_review` or `failed`.

Every task body accepts an optional `model_id` (from `GET /ai/models`); without
it the firm's default model runs.

## AI models

| Method | Path | Role | |
|---|---|---|---|
| GET | `/ai/models` | any | Models a lawyer can choose, default first |
| GET | `/ai/presets` | admin | Provider types with suggested endpoints |
| GET / POST | `/ai/providers` | admin | Keys are write-only; the list shows the last four characters |
| PATCH / DELETE | `/ai/providers/{id}` | admin | Replace the key, rename, turn on/off, remove |
| GET | `/ai/providers/{id}/available-models` | admin | Model ids the provider offers this key |
| POST | `/ai/providers/{id}/test` | admin | One tiny real request; result stored and shown |
| POST | `/ai/models` | admin | `{provider_id, model, label?, price_in_per_mtok?, price_out_per_mtok?, is_default?}` |
| PATCH / DELETE | `/ai/models/{id}` | admin | Price, default, on/off, remove |

## Playbooks, activity, audit

| Method | Path | Role | |
|---|---|---|---|
| GET | `/playbooks` | any | |
| GET | `/playbooks/{id}` | any | |
| PUT | `/playbooks/{id}` | partner | Replaces positions; clears approval |
| POST | `/playbooks/{id}/validate` | partner | `{lawyer_name}` |
| GET | `/activity` | any | 30-day metrics, recent tasks, flagged documents, limits |
| GET | `/audit` | partner | Most recent 200 audit events |
| GET | `/health` | — | Database and model-key status |
