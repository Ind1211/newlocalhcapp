from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import get_current_staff
from app.database import get_db
from app.document_autofill import AutoFillError, suggest_autofill
from app.document_extraction import ExtractionError, extract_text
from app.models import AssessmentDefinition, AssessmentVersion, Patient, PatientDocument, Staff, utcnow
from app.schemas import PatientDocumentDetailOut, PatientDocumentOut
from app.storage import delete_document, download_document, upload_document

router = APIRouter(prefix="/api/patients", tags=["documents"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}
MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20MB — generous for a clinical document, not unlimited


@router.post("/{patient_id}/documents", response_model=PatientDocumentOut, status_code=201)
async def upload_patient_document(patient_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_SIZE_BYTES // (1024*1024)}MB limit")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES and not file.filename.lower().endswith((".pdf", ".docx", ".txt")):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}' — upload a PDF, DOCX, or plain text file.",
        )

    storage_key = upload_document(patient_id, file.filename, content, content_type)

    doc = PatientDocument(
        patient_id=patient_id, filename=file.filename, content_type=content_type,
        storage_key=storage_key, size_bytes=len(content), extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    # Extraction runs synchronously, in this same request — documents here are a
    # handful of pages, not hundreds, so this stays fast enough not to need a
    # background job queue. A genuinely large or slow-to-parse file would be the
    # signal to revisit that, not something to build speculatively now.
    try:
        text = extract_text(content, content_type, file.filename)
        doc.extracted_text = text
        doc.extraction_status = "ok"
    except ExtractionError as e:
        doc.extraction_status = "failed"
        doc.extraction_error = str(e)
    db.commit()

    log_audit(db, "document", doc.id, "uploaded", staff, details={"filename": doc.filename, "extraction_status": doc.extraction_status}, related_patient_id=patient_id)
    return doc


@router.get("/{patient_id}/documents", response_model=list[PatientDocumentOut])
def list_patient_documents(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return (
        db.query(PatientDocument)
        .filter_by(patient_id=patient_id)
        .order_by(PatientDocument.uploaded_at.desc())
        .all()
    )


@router.get("/{patient_id}/documents/{document_id}", response_model=PatientDocumentDetailOut)
def get_patient_document(patient_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.query(PatientDocument).filter_by(id=document_id, patient_id=patient_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{patient_id}/documents/{document_id}/file")
def download_patient_document(patient_id: str, document_id: str, db: Session = Depends(get_db)):
    doc = db.query(PatientDocument).filter_by(id=document_id, patient_id=patient_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    content = download_document(doc.storage_key)
    return Response(
        content=content, media_type=doc.content_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.filename}"'},
    )


@router.delete("/{patient_id}/documents/{document_id}", status_code=204)
def delete_patient_document(patient_id: str, document_id: str, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    doc = db.query(PatientDocument).filter_by(id=document_id, patient_id=patient_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    filename = doc.filename
    delete_document(doc.storage_key)
    db.delete(doc)
    db.commit()
    log_audit(db, "document", document_id, "deleted", staff, details={"filename": filename}, related_patient_id=patient_id)


@router.post("/{patient_id}/documents/{document_id}/retry-extraction", response_model=PatientDocumentDetailOut)
def retry_extraction(patient_id: str, document_id: str, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    """Re-downloads the already-stored file and re-runs extraction — no re-upload
    needed. Useful both for a transient failure (a storage-backend hiccup, say) and for a
    genuinely permanent one (a scanned image with no real text layer) where
    retrying won't help, but at least gives a fresh, current error message
    rather than leaving someone staring at an old one from whenever it first failed."""
    doc = db.query(PatientDocument).filter_by(id=document_id, patient_id=patient_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    content = download_document(doc.storage_key)
    try:
        text = extract_text(content, doc.content_type, doc.filename)
        doc.extracted_text = text
        doc.extraction_status = "ok"
        doc.extraction_error = None
    except ExtractionError as e:
        doc.extraction_status = "failed"
        doc.extraction_error = str(e)
    db.commit()

    log_audit(db, "document", doc.id, "extraction_retried", staff, details={"extraction_status": doc.extraction_status}, related_patient_id=patient_id)
    return doc


class VoiceNoteCreate(BaseModel):
    text: str


@router.post("/{patient_id}/voice-notes", response_model=PatientDocumentDetailOut, status_code=201)
def create_voice_note(
    patient_id: str, payload: VoiceNoteCreate,
    db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff),
):
    """The transcription itself already happened client-side (the browser's own
    Web Speech API) — this endpoint just persists the result. A voice note is
    stored as a genuine text file through the exact same storage path a regular
    upload uses, and becomes a real PatientDocument row from that point on —
    which is what makes it participate in auto-fill and integrated-care-plan
    grounding automatically, with zero changes to either of those, since both
    already read extracted_text off of every one of a patient's documents
    without caring where that text originally came from."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Voice note text cannot be empty")

    timestamp = utcnow().strftime("%Y-%m-%d %H:%M")
    filename = f"Voice Note - {timestamp}.txt"
    content = payload.text.strip().encode("utf-8")
    storage_key = upload_document(patient_id, filename, content, "text/plain")

    doc = PatientDocument(
        patient_id=patient_id, filename=filename, content_type="text/plain",
        storage_key=storage_key, size_bytes=len(content),
        extraction_status="ok", extracted_text=payload.text.strip(),
        source="voice_note", uploaded_by=staff.name if staff else None,
    )
    db.add(doc)
    db.commit()

    log_audit(db, "document", doc.id, "voice_note_created", staff, details={"filename": filename}, related_patient_id=patient_id)
    return doc


@router.patch("/{patient_id}/voice-notes/{document_id}", response_model=PatientDocumentDetailOut)
def update_voice_note(
    patient_id: str, document_id: str, payload: VoiceNoteCreate,
    db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff),
):
    """Restricted to voice notes specifically — a regular uploaded document's
    extracted_text is derived FROM the original file, so editing it directly
    would create a real, confusing mismatch (retry-extraction would silently
    overwrite the edit with whatever the original file re-extracts to). A voice
    note has no such original source beyond its own transcript, so editing it
    is completely safe — as long as the stored text file is re-uploaded to
    match, which is exactly what this does, so retry-extraction later can't
    revert this edit either."""
    doc = db.query(PatientDocument).filter_by(id=document_id, patient_id=patient_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Voice note not found")
    if doc.source != "voice_note":
        raise HTTPException(status_code=400, detail="Only voice notes can be edited this way — use document upload/retry for regular documents.")

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Voice note text cannot be empty")

    new_text = payload.text.strip()
    old_storage_key = doc.storage_key
    content = new_text.encode("utf-8")
    doc.storage_key = upload_document(patient_id, doc.filename, content, "text/plain")
    doc.size_bytes = len(content)
    doc.extracted_text = new_text
    db.commit()

    # Only removed after the new upload succeeds — if upload_document raised,
    # the old file (and the row pointing at it) would still be intact rather
    # than left in a half-updated state with neither a valid old nor new file.
    try:
        delete_document(old_storage_key)
    except Exception:
        pass  # the orphaned old object is harmless clutter, not worth failing this whole request over

    log_audit(db, "document", doc.id, "voice_note_edited", staff, details={"filename": doc.filename}, related_patient_id=patient_id)
    return doc


@router.post("/{patient_id}/documents/auto-fill")
def autofill_from_documents(patient_id: str, assessment_definition_key: str, db: Session = Depends(get_db)):
    """Returns suggested answers only — never writes anything to the patient or
    the assessment. The frontend is responsible for showing these as a reviewable
    offer, the same pattern already used for prefilling from a patient's last
    submission of the same assessment."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    definition = db.query(AssessmentDefinition).filter_by(key=assessment_definition_key).first()
    if not definition:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_definition_key}' not found")
    version = (
        db.query(AssessmentVersion)
        .filter_by(assessment_definition_id=definition.id, version_number=definition.active_version)
        .first()
    )
    if not version or not version.fields:
        raise HTTPException(status_code=400, detail="This assessment has no field definitions to fill.")

    docs = (
        db.query(PatientDocument)
        .filter_by(patient_id=patient_id, extraction_status="ok")
        .all()
    )
    documents = [{"filename": d.filename, "extracted_text": d.extracted_text} for d in docs]

    try:
        return suggest_autofill(definition.title, version.fields, documents)
    except AutoFillError as e:
        raise HTTPException(status_code=422, detail=str(e))
