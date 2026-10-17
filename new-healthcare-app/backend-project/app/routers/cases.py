from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Case, Patient
from app.schemas import CaseContextUpdate, CaseCreate, CaseOut

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("", response_model=CaseOut, status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(id=payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    case = Case(patient_id=payload.patient_id, label=payload.label)
    db.add(case)
    db.commit()
    return case


@router.get("", response_model=list[CaseOut])
def list_cases(patient_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Case)
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    return query.all()


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.patch("/{case_id}/context", response_model=CaseOut)
def update_case_context(case_id: str, payload: CaseContextUpdate, db: Session = Depends(get_db)):
    """Updates the shared patient snapshot for this case — mirrors the original app's
    state.patientContext, which is used to prefill matching fields across any
    assessment, not just recorded once and forgotten."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.context = payload.context
    db.commit()
    return case
