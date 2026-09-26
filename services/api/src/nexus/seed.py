"""Create a demo firm with a ready-to-use matter: `uv run nexus-seed-demo`.

Sign in with the email and password printed at the end (defaults below, or
set NEXUS_DEMO_EMAIL / NEXUS_DEMO_PASSWORD). Safe to re-run: an existing demo
firm is left as it is.
"""

import hashlib
import os
from uuid import uuid4

from nexus import audit, jobs, storage
from nexus.api.auth import seed_playbooks
from nexus.db import row, scalar, tenant, unscoped
from nexus.ingest.extract import DOCX, TEXT
from nexus.samples import INJECTION_EMAIL, sample_nda_docx
from nexus.security import hash_password

DEMO_EMAIL = os.environ.get("NEXUS_DEMO_EMAIL", "demo@nexus.example")
DEMO_PASSWORD = os.environ.get("NEXUS_DEMO_PASSWORD", "nexus-demo-2026")


def main() -> None:
    with unscoped() as s:
        existing = row(s, "SELECT * FROM auth_lookup(:e)", e=DEMO_EMAIL)
    if existing:
        print(f"Demo firm already exists. Sign in as {DEMO_EMAIL}.")
        return

    firm_id = str(uuid4())
    with tenant(firm_id) as s:
        scalar(s, "INSERT INTO firms (id, name, preferences) VALUES (:id, :n, :p) RETURNING id",
               id=firm_id, n="Demo & Associates",
               p="- We mostly act for Indian technology companies contracting with overseas partners.\n"
                 "- Use the document's own defined terms.\n"
                 "- Be direct: lead with the answer, then the qualifications.")
        user_id = scalar(
            s, """INSERT INTO users (firm_id, email, name, password_hash, role)
                  VALUES (:f, :e, 'Demo Partner', :h, 'admin') RETURNING id""",
            f=firm_id, e=DEMO_EMAIL, h=hash_password(DEMO_PASSWORD),
        )
        seed_playbooks(s, firm_id)
        matter_id = scalar(
            s, """INSERT INTO matters (firm_id, name, client_name, description, created_by)
                  VALUES (:f, 'Acme / Brightline collaboration NDA', 'Acme Robotics Private Limited',
                          'Acme is exploring integrating Brightline''s analytics software into its warehouse robots. We act for Acme.', :u)
                  RETURNING id""",
            f=firm_id, u=user_id,
        )
        for name, content_type, data in [
            ("Acme - Brightline Mutual NDA.docx", DOCX, sample_nda_docx()),
            ("Email from Brightline - final NDA.txt", TEXT, INJECTION_EMAIL.encode()),
        ]:
            key = storage.put(firm_id, "documents", data, ".docx" if content_type == DOCX else ".txt")
            doc_id = scalar(
                s, """INSERT INTO documents (firm_id, matter_id, filename, content_type, size_bytes, sha256,
                                              storage_key, uploaded_by)
                      VALUES (:f, :m, :n, :ct, :sz, :sha, :k, :u) RETURNING id""",
                f=firm_id, m=matter_id, n=name, ct=content_type, sz=len(data),
                sha=hashlib.sha256(data).hexdigest(), k=key, u=user_id,
            )
            jobs.enqueue(s, firm_id, "ingest_document", {"document_id": str(doc_id)})
        audit.record(s, firm_id, user_id, "firm.created", "firm", firm_id, demo=True)
    print(f"Demo firm created. Sign in at http://localhost:3100 as {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print("(The worker must be running to process the two sample documents.)")
