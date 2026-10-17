"""
A single, shared helper for writing to the generic AuditLog table — every write
endpoint that logs an action calls this exact function, rather than each router
constructing its own AuditLog(...) row slightly differently. That consistency
matters: an audit trail where every entry has a subtly different shape is barely
better than no audit trail at all when someone actually needs to read it later.
"""

from sqlalchemy.orm import Session

from app.models import AuditLog, Staff


def log_audit(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    staff: Staff | None = None,
    details: dict | None = None,
    related_patient_id: str | None = None,
) -> None:
    """staff=None is a real, expected case — not every write happens in a
    request that resolved a staff identity (e.g. an unauthenticated context, or
    a background/system action) — recorded as 'system' rather than silently
    omitting who/what performed the action.

    related_patient_id is what makes "show me everything that happened to this
    patient" actually complete, even for a child entity (a task, a note) that's
    since been deleted — set it explicitly whenever the entity being logged
    belongs to a specific patient."""
    db.add(AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        performed_by=staff.name if staff else "system",
        details=details,
        related_patient_id=str(related_patient_id) if related_patient_id else None,
    ))
    db.commit()
