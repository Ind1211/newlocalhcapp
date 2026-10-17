from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai_custom_interpretation import InterpretationError, generate_interpretation
from app.audit import log_audit
from app.auth import get_current_staff
from app.calculators.intake import derive_clinical_programs
from app.calculators.registry import get_calculator
from app.database import get_db
from app.models import AssessmentDefinition, AssessmentResult, AssessmentVersion, AssignedAssessment, Case, PatientProgram, Program, Staff
from app.routers.business_rules import fire_event
from app.schemas import AssessmentResultCreate, AssessmentResultOut

router = APIRouter(tags=["results"])


def _process_intake_completion(db: Session, case: Case, answers: dict) -> None:
    """Runs only when the just-submitted assessment is basic_intake. Deliberately
    does NOT auto-assign the suggested pathway anymore — that now requires explicit
    review and confirmation (see confirm_pathway below), since blindly scheduling
    everything a rules engine suggests without a human looking at it first isn't
    the right default for clinical work. Clinical program derivation stays
    automatic: it's informational tagging, not new scheduled work, so there's
    nothing to confirm before it takes effect.

    Additive, never overwriting — a patient already established in the kidney
    program who has a new intake mentioning only cardiac symptoms gains the
    cardiology program too, rather than losing kidney. A single free-text field
    couldn't represent "both"; this can, which is the entire point of it existing."""
    if not case.patient:
        return
    derived_keys = derive_clinical_programs(answers)
    if not derived_keys:
        return
    existing_program_ids = {pp.program_id for pp in case.patient.programs}
    for key in derived_keys:
        program = db.query(Program).filter_by(key=key).first()
        if program and program.id not in existing_program_ids:
            db.add(PatientProgram(patient_id=case.patient.id, program_id=program.id))
            existing_program_ids.add(program.id)
    db.commit()


# The registry Patient Health Details actually depends on. Deliberately an
# EXACT, case-insensitive field-name match, not a substring/"contains" check —
# checked directly against real field names across all 134 assessments before
# building this: fields like age65, donorAge, hr100, and postWeight all contain
# these words but mean something else entirely (a threshold checkbox, a
# different person's value, a different timepoint), not the patient's own
# current value. An exact match against a curated, verified list is the only
# safe way to do this without silently recording the wrong thing.
SHARED_CONTEXT_FIELDS: dict[str, str] = {
    "age": "Age",
    "sex": "Sex",
    "egfr": "eGFR",
    "egfrvalue": "eGFR",  # ckd_staging names its own current-eGFR field this way, distinct from the plain "egfr" name 7 other assessments use for the same concept
    "sbp": "Systolic BP",
    "dbp": "Diastolic BP",
    "potassium": "Potassium",
    "hemoglobin": "Hemoglobin",
    "heightcm": "Height (cm)",
    "creatinine": "Creatinine",
    "bmi": "BMI",
    "sodium": "Sodium",
    "hba1c": "HbA1c",
}


def _extract_shared_context_fields(db: Session, case: Case, answers: dict) -> None:
    """Promotes any of this app's small, curated set of genuinely reusable
    clinical fields (see SHARED_CONTEXT_FIELDS) from a just-completed
    assessment's answers into this patient's Patient Health Details — the
    real implementation of what that tab's own description has always
    claimed happens automatically, which until now was never actually built.

    Merges into the existing context rather than replacing it — case.context
    is a plain JSONB dict with no built-in merge semantics, so this reads the
    current value, updates only the matched keys, and writes the whole thing
    back. Skipping this merge step would silently wipe out every other
    field already recorded (manually entered, or extracted from an earlier
    assessment) the next time any assessment completes — the same class of
    bug already found and fixed on the manual-edit path."""
    if not answers:
        return
    updates = {}
    for field_name, value in answers.items():
        if value is None or value == "":
            continue
        friendly_key = SHARED_CONTEXT_FIELDS.get(field_name.strip().lower())
        if friendly_key:
            updates[friendly_key] = value
    if not updates:
        return
    case.context = {**(case.context or {}), **updates}
    db.commit()


@router.post("/api/cases/{case_id}/results", response_model=AssessmentResultOut, status_code=201)
def submit_assessment_result(case_id: str, payload: AssessmentResultCreate, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    case = db.query(Case).filter_by(id=case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    definition = db.query(AssessmentDefinition).filter_by(key=payload.assessment_definition_key).first()
    if not definition:
        raise HTTPException(status_code=404, detail=f"Assessment '{payload.assessment_definition_key}' not found")

    if definition.is_builtin:
        calculator = get_calculator(definition.key)
        if not calculator:
            raise HTTPException(
                status_code=501,
                detail=f"No calculator implementation registered yet for '{definition.key}'",
            )
        computed_result = calculator.compute(payload.answers)
    else:
        # Custom assessments have no Python calculator — the "logic" is whatever
        # interpretation instructions the person who built it wrote, applied by AI.
        version = (
            db.query(AssessmentVersion)
            .filter_by(assessment_definition_id=definition.id, version_number=definition.active_version)
            .first()
        )
        if not version or not version.interpretation_prompt:
            raise HTTPException(status_code=500, detail="This custom assessment has no interpretation instructions")
        sections = (version.fields.get("steps") or [{"fields": version.fields.get("fields") or []}])
        try:
            computed_result = generate_interpretation(
                definition.title, sections, payload.answers, version.interpretation_prompt
            )
        except InterpretationError as e:
            raise HTTPException(status_code=502, detail=str(e))

    result = AssessmentResult(
        case_id=case.id,
        assessment_definition_id=definition.id,
        version_used=definition.active_version,
        answers=payload.answers,
        result=computed_result,
    )
    db.add(result)
    db.commit()

    log_audit(
        db, "assessment_result", result.id, "completed", staff,
        details={"assessment_key": definition.key, "assessment_title": definition.title, "headline": computed_result.get("headline") if isinstance(computed_result, dict) else None},
        related_patient_id=str(case.patient_id),
    )

    severity = computed_result.get("headlineSeverity") if isinstance(computed_result, dict) else None
    fire_event(
        db, "assessment.completed",
        {
            "mode": "manual_intake" if definition.key == "basic_intake" else "standard",
            "assessment_key": definition.key,
            "severity": severity,
        },
        case.patient, staff, dry_run=False,
    )

    if definition.key == "basic_intake":
        _process_intake_completion(db, case, payload.answers)

    _extract_shared_context_fields(db, case, payload.answers)

    return result


@router.get("/api/cases/{case_id}/results/latest")
def get_latest_result_for_assessment(case_id: str, assessment_definition_key: str, db: Session = Depends(get_db)):
    """Returns the most recent prior completed result for this case+assessment, if
    any — used to OFFER prefilling a repeat check-in from last time, never to
    apply it automatically. Returns null (not a 404) when there's no prior
    result, since 'nothing to offer yet' is an expected, normal case here, not an
    error."""
    definition = db.query(AssessmentDefinition).filter_by(key=assessment_definition_key).first()
    if not definition:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_definition_key}' not found")
    result = (
        db.query(AssessmentResult)
        .filter_by(case_id=case_id, assessment_definition_id=definition.id)
        .order_by(AssessmentResult.completed_at.desc())
        .first()
    )
    if not result:
        return None
    return {"answers": result.answers, "completed_at": result.completed_at}


@router.get("/api/cases/{case_id}/results", response_model=list[AssessmentResultOut])
def list_case_results(case_id: str, db: Session = Depends(get_db)):
    return db.query(AssessmentResult).filter_by(case_id=case_id).all()


@router.get("/api/results/{result_id}", response_model=AssessmentResultOut)
def get_result(result_id: str, db: Session = Depends(get_db)):
    result = db.query(AssessmentResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
