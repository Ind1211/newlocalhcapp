from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AssessmentDefinition, ClinicalReview
from app.schemas import ClinicalReviewCreate, ClinicalReviewOut

router = APIRouter(tags=["clinical-reviews"])


@router.post("/api/assessments/{key}/reviews", response_model=ClinicalReviewOut, status_code=201)
def add_clinical_review(key: str, payload: ClinicalReviewCreate, db: Session = Depends(get_db)):
    """A real, durable version of the review-tracking feature — previously stored only
    in browser localStorage in the original JS build, meaning it vanished if the
    browser cache was ever cleared."""
    definition = db.query(AssessmentDefinition).filter_by(key=key).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Assessment not found")

    review = ClinicalReview(
        assessment_definition_id=definition.id,
        reviewer_name=payload.reviewer_name,
        notes=payload.notes,
    )
    db.add(review)
    db.commit()
    return review


@router.get("/api/assessments/{key}/reviews", response_model=list[ClinicalReviewOut])
def list_clinical_reviews(key: str, db: Session = Depends(get_db)):
    definition = db.query(AssessmentDefinition).filter_by(key=key).first()
    if not definition:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return db.query(ClinicalReview).filter_by(assessment_definition_id=definition.id).all()
