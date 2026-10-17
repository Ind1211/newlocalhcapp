from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Program, QuestionLibraryItem
from app.schemas import QuestionLibraryItemOut

router = APIRouter(prefix="/api/question-library", tags=["question-library"])


@router.get("", response_model=list[QuestionLibraryItemOut])
def list_question_library(program: str | None = None, db: Session = Depends(get_db)):
    """Matches the JS picker's filter: a specific program shows that program's items
    PLUS general (program_id is NULL) items — never a hard partition."""
    query = db.query(QuestionLibraryItem)
    if program:
        program_row = db.query(Program).filter_by(key=program).first()
        if not program_row:
            raise HTTPException(status_code=404, detail=f"Unknown program '{program}'")
        query = query.filter(
            (QuestionLibraryItem.program_id == program_row.id)
            | (QuestionLibraryItem.program_id.is_(None))
        )
    return query.all()
