from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssessmentDefinition, AssessmentResult, AssessmentVersion, AssignedAssessment, AuditLogEntry, Staff
from app.permissions import require_role
from app.schemas import CustomAssessmentCreate, CustomAssessmentEdit, CustomAssessmentVersionOut

router = APIRouter(tags=["custom-assessments"])


def _sections_to_fields_json(sections) -> dict:
    steps = [{"id": f"section-{i}", "title": s.title, "fields": [f.model_dump() for f in s.fields]} for i, s in enumerate(sections)]
    if len(steps) > 1:
        return {"steps": steps, "fields": None}
    return {"steps": None, "fields": steps[0]["fields"] if steps else []}


@router.post("/api/assessments/custom", status_code=201)
def create_custom_assessment(payload: CustomAssessmentCreate, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    key = "custom_" + "".join(c if c.isalnum() else "_" for c in payload.title.lower()).strip("_")
    base_key, suffix = key, 1
    while db.query(AssessmentDefinition).filter_by(key=key).first():
        suffix += 1
        key = f"{base_key}_{suffix}"

    is_wizard = len(payload.sections) > 1
    definition = AssessmentDefinition(
        key=key, title=payload.title, category="Custom",
        program_id=None,
        kind="structured", interaction="wizard" if is_wizard else "flat",
        blurb=payload.blurb, is_builtin=False, active_version=1,
    )
    db.add(definition)
    db.commit()

    version = AssessmentVersion(
        assessment_definition_id=definition.id, version_number=1,
        title=payload.title, blurb=payload.blurb,
        fields=_sections_to_fields_json(payload.sections),
        interpretation_prompt=payload.interpretation_prompt,
        created_by=payload.created_by,
    )
    db.add(version)
    db.add(AuditLogEntry(
        assessment_definition_id=definition.id, action="created",
        version_number=1, performed_by=payload.created_by,
    ))
    db.commit()

    return {"key": key, "id": str(definition.id)}


@router.put("/api/assessments/custom/{key}")
def edit_custom_assessment(key: str, payload: CustomAssessmentEdit, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    definition = db.query(AssessmentDefinition).filter_by(key=key).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Custom assessment not found")
    if definition.is_builtin:
        raise HTTPException(status_code=403, detail="Built-in assessments cannot be edited")

    new_version_number = definition.active_version + 1
    version = AssessmentVersion(
        assessment_definition_id=definition.id, version_number=new_version_number,
        title=payload.title, blurb=payload.blurb,
        fields=_sections_to_fields_json(payload.sections),
        interpretation_prompt=payload.interpretation_prompt,
        created_by=payload.created_by,
    )
    db.add(version)
    definition.title = payload.title
    definition.blurb = payload.blurb
    definition.interaction = "wizard" if len(payload.sections) > 1 else "flat"
    definition.active_version = new_version_number
    db.add(AuditLogEntry(
        assessment_definition_id=definition.id, action="edited",
        version_number=new_version_number, performed_by=payload.created_by,
    ))
    db.commit()

    return {"key": key, "active_version": new_version_number}


@router.get("/api/assessments/custom/{key}/versions", response_model=list[CustomAssessmentVersionOut])
def list_custom_versions(key: str, db: Session = Depends(get_db)):
    definition = db.query(AssessmentDefinition).filter_by(key=key).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Custom assessment not found")
    versions = (
        db.query(AssessmentVersion)
        .filter_by(assessment_definition_id=definition.id)
        .order_by(AssessmentVersion.version_number.desc())
        .all()
    )
    return versions


@router.delete("/api/assessments/custom/{key}", status_code=204)
def delete_custom_assessment(key: str, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    definition = db.query(AssessmentDefinition).filter_by(key=key).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Custom assessment not found")
    if definition.is_builtin:
        raise HTTPException(status_code=403, detail="Built-in assessments cannot be deleted")

    n_results = db.query(AssessmentResult).filter_by(assessment_definition_id=definition.id).count()
    if n_results > 0:
        raise HTTPException(
            status_code=409,
            detail=f"This assessment has {n_results} completed result(s) from real patient use and can't be "
                   f"deleted — that would destroy real clinical data. Review those results first.",
        )

    # Any assignment at this point is only ever scheduled/in-progress, never
    # completed (a completed one would have a matching AssessmentResult,
    # already checked above) — safe to remove, since no real patient answer
    # is lost, just a pending task.
    db.query(AssignedAssessment).filter_by(assessment_definition_id=definition.id).delete()
    db.query(AssessmentVersion).filter_by(assessment_definition_id=definition.id).delete()
    db.query(AuditLogEntry).filter_by(assessment_definition_id=definition.id).delete()
    db.delete(definition)
    db.commit()
