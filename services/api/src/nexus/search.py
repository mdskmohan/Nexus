"""Full-text search over a matter's passages (Postgres, English stemming).

Search first requires every term; if that finds too little it falls back to
any term, ranked by how many match and how close together they are. The
agents run several searches with different wording, which is what recovers
recall that keyword search alone would miss.
"""

import re
from uuid import UUID

from sqlalchemy.orm import Session

from nexus.db import rows

_COLUMNS = """p.id, p.document_id, d.filename, p.page, p.seq, p.heading, p.text"""


def _any_terms_query(query: str) -> str:
    words = re.findall(r"[A-Za-z0-9]{2,}", query)
    return " OR ".join(words)


def search(
    session: Session,
    matter_id: UUID | str,
    query: str,
    document_id: UUID | str | None = None,
    limit: int = 8,
) -> list[dict]:
    scope = "p.matter_id = :matter" + (" AND p.document_id = :doc" if document_id else "")
    params = {"matter": str(matter_id), "doc": str(document_id) if document_id else None,
              "limit": limit}
    sql = f"""
        SELECT {_COLUMNS}, ts_rank_cd(p.tsv, q, 32) AS rank
        FROM passages p JOIN documents d ON d.id = p.document_id,
             websearch_to_tsquery('english', :q) q
        WHERE {scope} AND p.tsv @@ q
        ORDER BY rank DESC, p.seq LIMIT :limit"""
    found = rows(session, sql, q=query, **params)
    if len(found) < limit // 2:
        loose = _any_terms_query(query)
        if loose:
            seen = {r["id"] for r in found}
            more = rows(session, sql, q=loose, **params)
            found += [r for r in more if r["id"] not in seen][: limit - len(found)]
    return found


def passages_by_id(session: Session, matter_id: UUID | str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    return rows(
        session,
        f"""SELECT {_COLUMNS} FROM passages p JOIN documents d ON d.id = p.document_id
            WHERE p.matter_id = :matter AND p.id = ANY(CAST(:ids AS uuid[]))
            ORDER BY d.filename, p.seq""",
        matter=str(matter_id),
        ids=ids,
    )


def passages_by_position(
    session: Session, matter_id: UUID | str, document_id: UUID | str, start_seq: int, count: int
) -> list[dict]:
    return rows(
        session,
        f"""SELECT {_COLUMNS} FROM passages p JOIN documents d ON d.id = p.document_id
            WHERE p.matter_id = :matter AND p.document_id = :doc
              AND p.seq >= :start AND p.seq < :end
            ORDER BY p.seq""",
        matter=str(matter_id),
        doc=str(document_id),
        start=start_seq,
        end=start_seq + count,
    )
