from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssessmentDefinition, AssessmentVersion, Patient, Program
from app.schemas import AssessmentDefinitionOut

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def _filter_intake_fields_by_program(fields: dict, patient_program_keys: set[str]) -> dict:
    """Only ever called for basic_intake, and only when the patient already has at
    least one established program — a brand-new patient with none yet sees the
    full, unfiltered intake, since answering it is how a program gets assigned in
    the first place. A question with no 'programs' tag is general and always
    stays; one tagged with multiple programs (diabetes, pregnancy, swelling,
    shortness of breath) stays visible if the patient has ANY of them, since the
    routing engine itself treats those as genuinely cross-program signals."""
    new_steps = []
    for step in fields.get("steps") or []:
        kept_fields = [
            f for f in step["fields"]
            if not f.get("programs") or set(f["programs"]) & patient_program_keys
        ]
        if kept_fields:
            new_steps.append({**step, "fields": kept_fields})
    return {**fields, "steps": new_steps}


@router.get("", response_model=list[AssessmentDefinitionOut])
def list_assessments(program: str | None = None, db: Session = Depends(get_db)):
    """program=kidney or program=kidney,cardiology (comma-separated) filters;
    omitting it returns everything — mirrors the JS hub's 'All programs' vs
    specific-program filter pills, extended to support a patient with more than
    one clinical program at once. Custom assessments (program_id NULL) always show
    regardless of filter, the same cross-cutting pattern already used for general
    question-library items."""
    query = db.query(AssessmentDefinition)
    if program:
        keys = [p.strip() for p in program.split(",") if p.strip()]
        program_rows = db.query(Program).filter(Program.key.in_(keys)).all()
        if not program_rows:
            raise HTTPException(status_code=404, detail=f"Unknown program(s) '{program}'")
        program_ids = [p.id for p in program_rows]
        query = query.filter(
            (AssessmentDefinition.program_id.in_(program_ids))
            | (AssessmentDefinition.program_id.is_(None))
        )
    return query.all()


@router.get("/{key}", response_model=AssessmentDefinitionOut)
def get_assessment(key: str, patient_id: str | None = None, db: Session = Depends(get_db)):
    definition = db.query(AssessmentDefinition).filter_by(key=key).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Assessment not found")
    version = (
        db.query(AssessmentVersion)
        .filter_by(assessment_definition_id=definition.id, version_number=definition.active_version)
        .first()
    )
    out = AssessmentDefinitionOut.model_validate(definition)
    if version:
        out.fields = version.fields
        out.interpretation_prompt = version.interpretation_prompt

    if key == "basic_intake" and patient_id and out.fields:
        patient = db.query(Patient).filter_by(id=patient_id).first()
        if patient:
            program_keys = {pp.program.key for pp in patient.programs}
            if program_keys:
                out.fields = _filter_intake_fields_by_program(out.fields, program_keys)

    return out
