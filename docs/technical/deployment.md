# Deployment

Nexus is three processes and two stateful services:

| Process | Command | Scale |
|---|---|---|
| API | `uvicorn nexus.main:app --host 0.0.0.0 --port 8100` | Horizontally; stateless |
| Worker | `nexus-worker` | Horizontally; jobs are claimed with `SKIP LOCKED` |
| Web | `next build && next start --port 3100` | Horizontally; set `NEXUS_API_URL` to the API's internal URL |

| Service | Notes |
|---|---|
| Postgres 16+ | Create the `nexus_app` role as in `infra/postgres/init/01-roles.sh`; run migrations as the owner role |
| File storage | `NEXUS_STORAGE_DIR` on a persistent volume today; object storage behind the same three functions in `nexus/storage.py` (`put`, `get`, `delete`) is the production path |

Container images: `services/api/Dockerfile` (API and worker, choose the command)
and `apps/web/Dockerfile`.

> **Not yet verified.** These Dockerfiles have not been built successfully yet:
> on the development machine, Docker Desktop hung while pulling base images.
> Build and smoke-test both images before relying on them.

## Checklist

- [ ] `NEXUS_JWT_SECRET` from a secret store; `NEXUS_COOKIE_SECURE=true`; HTTPS only
- [ ] Database passwords set; app connects as `nexus_app`, migrations as owner
- [ ] Encrypted database and storage volumes; backups with restore tested
- [ ] `ANTHROPIC_API_KEY` from a secret store; confirm data-retention terms for the account
- [ ] Worker count sized for peak AI tasks (each task is a single worker for its duration)
- [ ] Log shipping for API and worker stdout
- [ ] Items under "Before production" in [security](security.md)

## Roadmap items that affect deployment

- Object storage backend (S3-compatible) with server-side encryption.
- Claude through the firm's own cloud (Amazon Bedrock, Google Vertex AI), for
  data-residency requirements.
- SSO (SAML/OIDC).
