# Security

## Authentication and sessions

- Passwords: Argon2 (`argon2-cffi` defaults), minimum 10 characters.
- Sessions: signed JWT (HS256, `NEXUS_JWT_SECRET`) in an HTTP-only,
  `SameSite=Lax` cookie; lifetime `NEXUS_SESSION_HOURS` (12). Set
  `NEXUS_COOKIE_SECURE=true` behind HTTPS.
- Every request re-reads the user; a removed user is signed out on their next
  request.
- Login does not reveal whether an email exists.

## Cross-site request forgery

State-changing requests must carry the `X-Nexus-Client` header. Browsers do not
add custom headers to cross-site requests without a CORS preflight, and the API
approves none. The web app is same-origin with the API through a proxy
rewrite, so no CORS is configured at all.

## Authorisation

Roles, in order: paralegal < associate < partner < admin, checked with
`require(role)` on each endpoint. Tenant isolation is enforced by Postgres
row-level security (see [guardrails](guardrails.md)).

## Input handling

- Uploads: allow-listed types by extension, size limit (`NEXUS_MAX_UPLOAD_MB`),
  stored under a random key inside the firm's storage prefix; storage paths
  are resolved and checked against the storage root.
- Downloads: `Content-Disposition` built with RFC 5987 encoding; files are
  served only through authenticated, audited endpoints.
- Path parameters are typed UUIDs; SQL is parameterised throughout.
- Draft file names are validated against a strict pattern.

## Prompt injection

Document text reaches the model only as tool results, framed as evidence, with
an explicit rule in every system prompt that document text is never
instruction. The agents' tools are read-only against the matter (the only
writes are the agent's own findings and deliverables), so even a successful
injection cannot exfiltrate other matters' data, change settings, or send
anything outside the firm. Uploads are scanned and flagged.

## Response headers

The web app sets `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
`Referrer-Policy: same-origin` and a restrictive `Permissions-Policy`, and
hides `X-Powered-By`.

## Firms' AI keys

Stored AES-256-GCM encrypted with a master key (`NEXUS_SECRET_KEY`) that is not
in the database; the firm id is authenticated data, so a ciphertext copied to
another firm does not decrypt. Keys are write-only through the API (only the
last four characters are ever returned), usable only by the server, and every
add, change or removal is audited. Provider endpoints must use HTTPS unless
they are on the same machine.

## Secrets

`.env` (git-ignored) holds `NEXUS_JWT_SECRET`, `NEXUS_SECRET_KEY` and optionally
`ANTHROPIC_API_KEY`. Rotating `NEXUS_SECRET_KEY` requires re-encrypting stored
keys (ciphertexts carry a version prefix for this). The dev
defaults for database passwords are for local use only; set
`NEXUS_DB_OWNER_PASSWORD` / `NEXUS_DB_APP_PASSWORD` and the URLs in production.

## Before production (not yet done)

- Rate limiting on login and task creation.
- Single sign-on (SAML/OIDC) and multi-factor authentication.
- Object storage with server-side encryption, and encrypted database volumes.
- Malware scanning of uploads.
- Independent penetration test.
