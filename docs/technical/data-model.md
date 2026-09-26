# Data model

Defined in `services/api/migrations/versions/`. Every table except `jobs` has
`firm_id` and row-level security.

```
firms 1─* users
firms 1─* matters 1─* documents 1─* passages
                  1─* runs 1─* run_steps
                           1─* artifacts
firms 1─* playbooks
firms 1─* audit_events
jobs (queue; firm_id recorded, no RLS)
```

| Table | Key columns | Notes |
|---|---|---|
| `firms` | `id`, `name`, `preferences` | `preferences` is read by every agent |
| `users` | `email` (unique, case-insensitive), `role`, `disabled`, `password_hash` | Roles: paralegal, associate, partner, admin |
| `matters` | `name`, `client_name`, `description`, `status` | |
| `documents` | `filename`, `content_type`, `sha256`, `storage_key`, `status`, `page_count`, `flags` | `flags`: hidden-instruction and sensitive-number scan results |
| `passages` | `document_id`, `seq`, `page`, `heading`, `text`, `tsv` | `tsv` is a generated, weighted full-text vector (heading A, text B) with a GIN index |
| `playbooks` | `slug`, `positions` (jsonb), `is_starter`, `validated_by`, `validated_at` | Edits clear validation |
| `runs` | `kind` (ask/review/draft), `status`, `input`, `output`, `guardrails`, tokens, `cost_usd`, `reviewed_by` | Status: queued → running → needs_review → approved/rejected, or failed |
| `run_steps` | `run_id`, `seq`, `kind`, `title`, `status`, `detail`, `duration_ms` | The activity record |
| `artifacts` | `run_id`, `filename`, `content_type`, `storage_key` | Generated Word/Excel/Markdown |
| `audit_events` | `actor_id`, `action`, `target_type`, `target_id`, `detail`, `at` | Append-only (trigger + no UPDATE/DELETE grant) |
| `jobs` | `kind`, `payload`, `status`, `attempts`, `run_after`, `locked_at` | Claimed with `FOR UPDATE SKIP LOCKED` |

`page` means page for PDFs, sheet for Excel and slide for PowerPoint; other
formats use 1 and are located by passage position.
