from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import require_staff
from app.database import get_db
from app.models import CareNote, Patient, Staff
from app.schemas import CareNoteCreate, CareNoteOut

router = APIRouter(prefix="/api/patients", tags=["care-notes"])


@router.get("/{patient_id}/care-notes", response_model=list[CareNoteOut])
def list_care_notes(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return (
        db.query(CareNote)
        .filter_by(patient_id=patient_id)
        .order_by(CareNote.created_at.desc())
        .all()
    )


@router.post("/{patient_id}/care-notes", response_model=CareNoteOut, status_code=201)
def create_care_note(
    patient_id: str, payload: CareNoteCreate,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="Note content cannot be empty")
    note = CareNote(patient_id=patient_id, author_id=staff.id, content=payload.content.strip())
    db.add(note)
    db.commit()
    log_audit(db, "care_note", note.id, "created", staff, related_patient_id=patient_id)
    return note


@router.delete("/{patient_id}/care-notes/{note_id}", status_code=204)
def delete_care_note(
    patient_id: str, note_id: str,
    db: Session = Depends(get_db), staff: Staff = Depends(require_staff),
):
    note = db.query(CareNote).filter_by(id=note_id, patient_id=patient_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    # Restricted to the note's own author, or an admin — a nurse deleting a
    # care manager's note (or vice versa) is exactly the gap real role-based
    # authorization is meant to close, distinct from require_staff's much
    # broader "is this person registered as staff at all" check.
    if note.author_id != staff.id and staff.role != "admin":
        raise HTTPException(status_code=403, detail="You can only delete your own care notes, unless you're an admin.")
    db.delete(note)
    db.commit()
    log_audit(db, "care_note", note_id, "deleted", staff, related_patient_id=patient_id)
