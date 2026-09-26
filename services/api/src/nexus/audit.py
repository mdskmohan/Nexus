"""The audit trail: an append-only record of who did what, kept per firm."""

import json
from uuid import UUID

from sqlalchemy.orm import Session

from nexus.db import rows, scalar


def record(
    session: Session,
    firm_id: UUID | str,
    actor_id: UUID | str | None,
    action: str,
    target_type: str,
    target_id: UUID | str | None = None,
    **detail: object,
) -> None:
    scalar(
        session,
        """INSERT INTO audit_events (firm_id, actor_id, action, target_type, target_id, detail)
           VALUES (:firm, :actor, :action, :ttype, :tid, CAST(:detail AS jsonb)) RETURNING id""",
        firm=str(firm_id),
        actor=str(actor_id) if actor_id else None,
        action=action,
        ttype=target_type,
        tid=str(target_id) if target_id else None,
        detail=json.dumps(detail, default=str),
    )


def recent(session: Session, limit: int = 100) -> list[dict]:
    return rows(
        session,
        """SELECT a.id, a.action, a.target_type, a.target_id, a.detail, a.at,
                  u.name AS actor_name
           FROM audit_events a LEFT JOIN users u ON u.id = a.actor_id
           ORDER BY a.at DESC LIMIT :limit""",
        limit=limit,
    )
