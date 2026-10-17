from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_care_plan import CarePlanError, generate_care_plan
from app.calculators.registry import get_calculator
from app.database import get_db
from app.models import AssessmentDefinition, AssessmentResult, Case

router = APIRouter(tags=["care-plan"])


@router.post("/api/cases/{case_id}/ckd-care-plan")
def generate_ckd_care_plan(case_id: str, payload: dict, db: Session = Depends(get_db)):
    """Generates the AI narrative care plan for a CKD staging assessment. Takes the
    same `answers` shape used for the deterministic staging submission — recomputes
    staging server-side (never trusts a client-supplied result) and looks up which
    other assessments are genuinely not yet completed for this specific case, so the
    AI can only ever suggest assessments that actually still make sense to do."""
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    answers = payload.get("answers", {})
    calculator = get_calculator("ckd_staging")
    staging = calculator.compute(answers)

    completed_ids = {
        r.assessment_definition_id
        for r in db.query(AssessmentResult).filter_by(case_id=case.id).all()
    }
    ckd_def = db.query(AssessmentDefinition).filter_by(key="ckd_staging").first()
    if ckd_def:
        completed_ids.add(ckd_def.id)

    available = [
        {"id": d.key, "title": d.title}
        for d in db.query(AssessmentDefinition).all()
        if d.id not in completed_ids
    ]

    try:
        care_plan = generate_care_plan(staging, answers, available)
    except CarePlanError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"staging": staging, "carePlan": care_plan}
