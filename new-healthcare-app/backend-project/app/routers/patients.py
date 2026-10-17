import csv
import io
from datetime import date, datetime

from pydantic import BaseModel
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import and_, func, or_
from sqlalchemy import case as sql_case
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import get_current_staff
from app.permissions import require_role
from app.ai_integrated_care_plan import IntegratedCarePlanError, generate_integrated_care_plan, suggest_pgi_from_care_plan
from app.database import get_db
from app.models import AssessmentDefinition, AssessmentResult, AssignedAssessment, AuditLog, CareNote, Case, Patient, PatientDocument, PatientProgram, PatientStaffAssignment, Problem, Program, Staff, Task, utcnow
from app.routers.business_rules import fire_event
from app.schemas import AssignAssessmentRequest, AuditLogOut, ConfirmPathwayRequest, OnboardingProgressOut, PaginatedPatientsOut, PatientAssessmentSummary, PatientCreate, PatientListOut, PatientOut, PatientUpdate, SaveDraftRequest

router = APIRouter(prefix="/api/patients", tags=["patients"])

MAX_REASONABLE_AGE_YEARS = 130
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


def _validate_dob(dob: date | None) -> None:
    """A single place this rule lives, called by both patient creation and
    editing, rather than two separate checks that could quietly drift apart. Two
    genuinely different failure modes get caught here: a future date (a real
    patient record was once created with a DOB after the current date, with
    nothing stopping it), and an implausibly-old date (a typo'd year, e.g. 1865
    instead of 1965)."""
    if dob is None:
        return
    if dob > date.today():
        raise HTTPException(status_code=400, detail="Date of birth cannot be in the future")
    if (date.today() - dob).days > MAX_REASONABLE_AGE_YEARS * 365:
        raise HTTPException(status_code=400, detail=f"Date of birth implies an age over {MAX_REASONABLE_AGE_YEARS} years — please double-check it")


def _next_mrn(db: Session) -> str:
    """Matches the wireframe's REN-XXXXX pattern — finds the highest existing
    numeric suffix rather than just counting rows, so it stays correct even if a
    patient in the middle of the sequence was ever deleted."""
    existing = db.query(Patient.mrn).filter(Patient.mrn.like("REN-%")).all()
    max_num = 30510
    for (mrn,) in existing:
        try:
            max_num = max(max_num, int(mrn.split("-")[1]))
        except (IndexError, ValueError):
            continue
    return f"REN-{max_num + 1}"


def get_or_create_primary_case(db: Session, patient: Patient) -> Case:
    """The wireframe has no visible 'case' concept — assessments hang directly off
    the patient. Rather than remove the Case model (other parts of this platform
    depend on it), each patient gets exactly one auto-created primary case that the
    patient-facing screens use transparently."""
    case = db.query(Case).filter_by(patient_id=patient.id).first()
    if not case:
        case = Case(patient_id=patient.id, label=f"{patient.name or patient.internal_label} — primary")
        db.add(case)
        db.commit()
    return case


def _create_patient_with_setup(db: Session, payload: PatientCreate, staff: Staff | None = None, source: str = "manual_entry") -> Patient:
    """Shared by single-patient creation and bulk import — guarantees the two paths
    behave identically (mandatory intake auto-assigned, programs attached), not
    just similarly, since they call the exact same code rather than two separate
    implementations that could drift apart."""
    _validate_dob(payload.dob)
    if payload.risk_level and payload.risk_level not in VALID_RISK_LEVELS:
        raise HTTPException(status_code=400, detail=f"risk_level must be one of {sorted(VALID_RISK_LEVELS)}")

    mrn = payload.mrn or _next_mrn(db)
    if db.query(Patient).filter_by(mrn=mrn).first():
        raise HTTPException(status_code=409, detail=f"MRN '{mrn}' is already in use")

    # A real name+DOB match is a genuine data-quality signal worth blocking on —
    # not foolproof (two different people can share both), but a false positive
    # here costs someone a moment adding a middle initial to disambiguate, while
    # a missed true positive costs a duplicate clinical record.
    if payload.dob:
        existing = db.query(Patient).filter(
            Patient.name.ilike(payload.name.strip()), Patient.dob == payload.dob, Patient.is_active.is_(True)
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"A patient named '{existing.name}' with this same date of birth already exists (MRN {existing.mrn})",
            )

    patient = Patient(
        internal_label=payload.internal_label,
        name=payload.name,
        dob=payload.dob,
        mrn=mrn,
        care_pathway=payload.care_pathway,
        payor_name=payload.payor_name,
        member_id=payload.member_id,
        group_number=payload.group_number,
        eligibility_status=payload.eligibility_status,
        phone_number=payload.phone_number,
        email=payload.email,
        address_line1=payload.address_line1,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        preferred_contact_method=payload.preferred_contact_method,
        preferred_language=payload.preferred_language,
        risk_level=payload.risk_level,
    )
    db.add(patient)
    db.commit()

    for key in payload.clinical_program_keys:
        program = db.query(Program).filter_by(key=key).first()
        if program:
            db.add(PatientProgram(patient_id=patient.id, program_id=program.id))
    db.commit()

    case = get_or_create_primary_case(db, patient)

    # The basic intake is mandatory — every new patient gets it auto-assigned
    # immediately, rather than waiting for someone to remember to add it manually.
    # This applies identically whether the patient came from the single-add form
    # or a bulk import, since both call this same function.
    intake_def = db.query(AssessmentDefinition).filter_by(key="basic_intake").first()
    if intake_def:
        db.add(AssignedAssessment(
            case_id=case.id, assessment_definition_id=intake_def.id,
            title_override=None, source="template", mandatory=True,
        ))
        db.commit()
    log_audit(db, "patient", patient.id, "created", staff, details={"mrn": patient.mrn, "name": patient.name}, related_patient_id=str(patient.id))
    fire_event(db, "patient.imported", {"source": source}, patient, staff, dry_run=False)
    return patient


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    return _create_patient_with_setup(db, payload, staff)


@router.post("/bulk-import")
async def bulk_import_patients(file: UploadFile = File(...), db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    """Expects a CSV with columns: name, dob (YYYY-MM-DD), mrn (optional — auto-
    generated if blank), clinical_programs (semicolon-separated program keys, e.g.
    "kidney;cardiology"), payor_name, member_id, group_number, eligibility_status,
    phone_number, email, address_line1, city, state, zip_code,
    preferred_contact_method, preferred_language, risk_level. Every column
    beyond name is optional.

    Each row is processed independently through the exact same
    _create_patient_with_setup() single-patient creation uses — same mandatory
    intake auto-assignment, same program attachment, same MRN handling. One bad
    row (a duplicate MRN, a missing name) doesn't abort the rest of the batch;
    it's reported back per-row instead."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file")

    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))

    created: list[dict] = []
    errors: list[dict] = []
    for i, row in enumerate(reader, start=2):  # start=2: row 1 is the header
        try:
            name = (row.get("name") or "").strip()
            if not name:
                raise ValueError("Missing required 'name'")
            dob_str = (row.get("dob") or "").strip()
            program_keys = [p.strip() for p in (row.get("clinical_programs") or "").split(";") if p.strip()]
            payload = PatientCreate(
                name=name,
                dob=date.fromisoformat(dob_str) if dob_str else None,
                mrn=(row.get("mrn") or "").strip() or None,
                clinical_program_keys=program_keys,
                payor_name=(row.get("payor_name") or "").strip() or None,
                member_id=(row.get("member_id") or "").strip() or None,
                group_number=(row.get("group_number") or "").strip() or None,
                eligibility_status=(row.get("eligibility_status") or "").strip() or None,
                phone_number=(row.get("phone_number") or "").strip() or None,
                email=(row.get("email") or "").strip() or None,
                address_line1=(row.get("address_line1") or "").strip() or None,
                city=(row.get("city") or "").strip() or None,
                state=(row.get("state") or "").strip() or None,
                zip_code=(row.get("zip_code") or "").strip() or None,
                preferred_contact_method=(row.get("preferred_contact_method") or "").strip() or None,
                preferred_language=(row.get("preferred_language") or "").strip() or None,
                risk_level=(row.get("risk_level") or "").strip() or None,
            )
            patient = _create_patient_with_setup(db, payload, staff, source="tenant_admin_import")
            created.append({"row": i, "name": patient.name, "mrn": patient.mrn})
        except HTTPException as e:
            errors.append({"row": i, "name": row.get("name"), "error": e.detail})
        except Exception as e:
            errors.append({"row": i, "name": row.get("name"), "error": str(e)})

    return {"created": created, "errors": errors, "created_count": len(created), "error_count": len(errors)}


@router.get("", response_model=PaginatedPatientsOut)
def list_patients(
    search: str | None = None,
    include_inactive: bool = False,
    eligibility_status: str | None = None,
    care_team_staff_id: str | None = None,
    program_status: str | None = None,
    risk_level: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    # Filters out any patient with no name — name has been required for new patient
    # creation since this schema was extended, so a nameless row can only be
    # leftover data from before that (this is exactly what caused blank "?" tiles
    # in the patient list — fixed at the source in seed.py, but this guards against
    # any pre-existing orphaned rows in a database seeded before that fix).
    query = db.query(Patient).filter(Patient.name.isnot(None))
    if not include_inactive:
        query = query.filter(Patient.is_active.is_(True))
    if eligibility_status:
        query = query.filter(Patient.eligibility_status == eligibility_status)
    if program_status:
        query = query.filter(Patient.program_status == program_status)
    if risk_level:
        query = query.filter(Patient.risk_level == risk_level)
    if care_team_staff_id:
        care_team_patient_ids = db.query(PatientStaffAssignment.patient_id).filter(
            PatientStaffAssignment.staff_id == care_team_staff_id
        )
        query = query.filter(Patient.id.in_(care_team_patient_ids))
    if search:
        q = f"%{search}%"
        # Matches a patient's real clinical program (e.g. searching "Kidney" or
        # "Cardiology" finds everyone in that program) via a subquery — not just
        # the legacy care_pathway string, which only ever existed as a free-text
        # label on patients created before real program associations did.
        program_match_patient_ids = (
            db.query(PatientProgram.patient_id)
            .join(Program, PatientProgram.program_id == Program.id)
            .filter(Program.label.ilike(q))
        )
        query = query.filter(
            or_(
                Patient.name.ilike(q),
                Patient.mrn.ilike(q),
                Patient.care_pathway.ilike(q),
                Patient.id.in_(program_match_patient_ids),
            )
        )

    # Total count against the full filtered set, BEFORE pagination is applied —
    # this is what makes "page 3 of 8" possible on the frontend at all.
    total = query.count()
    page = max(page, 1)
    page_size = max(1, min(page_size, 200))  # a hard ceiling — no page_size=100000 accidentally fetching everyone anyway
    ascending = sort_order.lower() != "desc"

    if sort_by == "open_tasks":
        # open_tasks_count is otherwise computed in Python, per-page, AFTER
        # pagination — that's fine for display, but sorting by it needs the real
        # count for EVERY matching patient before pagination can even decide who
        # belongs on which page. A correlated subquery makes that possible at the
        # SQL level, rather than fetching everyone into Python just to sort.
        open_tasks_subquery = (
            db.query(Task.patient_id, func.count(Task.id).label("open_count"))
            .filter(Task.status != "completed")
            .group_by(Task.patient_id)
            .subquery()
        )
        query = query.outerjoin(open_tasks_subquery, Patient.id == open_tasks_subquery.c.patient_id)
        sort_column = func.coalesce(open_tasks_subquery.c.open_count, 0)
    elif sort_by == "name":
        sort_column = Patient.name
    elif sort_by == "dob":
        sort_column = Patient.dob
    elif sort_by == "risk_level":
        # Alphabetical order on the raw string would be clinically meaningless
        # ("critical" sorts before "high" sorts before "low" — not the actual
        # severity order at all) — this maps each level to a real severity
        # rank first, so ascending/descending actually means "least to most
        # urgent" or vice versa. NULL (never triaged) sorts as least urgent,
        # not as an error or a false "highest priority."
        sort_column = sql_case(
            (Patient.risk_level == "critical", 4),
            (Patient.risk_level == "high", 3),
            (Patient.risk_level == "medium", 2),
            (Patient.risk_level == "low", 1),
            else_=0,
        )
    else:
        sort_column = Patient.created_at

    query = query.order_by(sort_column.asc() if ascending else sort_column.desc())
    patients = query.offset((page - 1) * page_size).limit(page_size).all()

    if not patients:
        return {"items": [], "total": total, "page": page, "page_size": page_size, "total_pages": max(1, -(-total // page_size))}
    patient_ids = [p.id for p in patients]

    # Everything below is a small, fixed number of batch queries across ALL
    # matched patients ON THIS PAGE at once — not one query per patient in a
    # loop, and not across the entire filtered set either now that pagination
    # exists. That distinction matters a lot at real volume; a per-patient query
    # here would be exactly the kind of N+1 pattern that looks fine with a
    # handful of seeded patients and degrades badly with hundreds.

    cases = db.query(Case).filter(Case.patient_id.in_(patient_ids)).all()
    case_id_to_patient_id = {c.id: c.patient_id for c in cases}
    case_ids = list(case_id_to_patient_id.keys())

    assigned_by_case: dict = {}
    if case_ids:
        for a in db.query(AssignedAssessment).filter(AssignedAssessment.case_id.in_(case_ids)).all():
            assigned_by_case.setdefault(a.case_id, []).append(a)

    # A set of (case_id, assessment_definition_id) pairs that have a real
    # completed result — the exact same definition of "completed" used by
    # list_patient_assessments above, so this count can never quietly disagree
    # with what a patient's own assessment list shows.
    completed_pairs = set()
    if case_ids:
        for r in db.query(AssessmentResult.case_id, AssessmentResult.assessment_definition_id).filter(AssessmentResult.case_id.in_(case_ids)).all():
            completed_pairs.add((r.case_id, r.assessment_definition_id))

    open_tasks_by_patient: dict = {}
    for t in db.query(Task.patient_id, func.count(Task.id)).filter(
        Task.patient_id.in_(patient_ids), Task.status != "completed"
    ).group_by(Task.patient_id).all():
        open_tasks_by_patient[t.patient_id] = t[1]

    care_team_by_patient: dict = {}
    for assignment in (
        db.query(PatientStaffAssignment)
        .filter(PatientStaffAssignment.patient_id.in_(patient_ids))
        .all()
    ):
        care_team_by_patient.setdefault(assignment.patient_id, []).append(assignment.staff)

    results = []
    for p in patients:
        case = next((c for c in cases if c.patient_id == p.id), None)
        assigned = assigned_by_case.get(case.id, []) if case else []
        completed_count = sum(1 for a in assigned if (case.id, a.assessment_definition_id) in completed_pairs) if case else 0

        base = PatientOut.model_validate(p).model_dump()
        results.append(PatientListOut(
            **base,
            care_team=care_team_by_patient.get(p.id, []),
            assessments_completed=completed_count,
            assessments_total=len(assigned),
            open_tasks_count=open_tasks_by_patient.get(p.id, 0),
        ))
    return {
        "items": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: str, payload: PatientUpdate,
    db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff),
):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Optimistic locking — if the frontend sent a version token and it doesn't
    # match the patient's CURRENT updated_at, someone else changed this record
    # in between the frontend loading it and this request arriving. Checked
    # before anything else runs, so a stale edit can't partially apply before
    # being rejected.
    if payload.expected_updated_at is not None and payload.expected_updated_at != patient.updated_at:
        raise HTTPException(
            status_code=409,
            detail="This patient was changed by someone else since you opened this form. Refresh and try again.",
        )

    _validate_dob(payload.dob)
    if payload.risk_level and payload.risk_level not in VALID_RISK_LEVELS:
        raise HTTPException(status_code=400, detail=f"risk_level must be one of {sorted(VALID_RISK_LEVELS)}")

    changed_fields = []
    if payload.name is not None:
        if not payload.name.strip():
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        if patient.name != payload.name.strip():
            changed_fields.append("name")
        patient.name = payload.name.strip()
    if payload.dob is not None:
        if patient.dob != payload.dob:
            changed_fields.append("dob")
        patient.dob = payload.dob
    if payload.payor_name is not None:
        if patient.payor_name != (payload.payor_name or None):
            changed_fields.append("payor_name")
        patient.payor_name = payload.payor_name or None
    if payload.member_id is not None:
        if patient.member_id != (payload.member_id or None):
            changed_fields.append("member_id")
        patient.member_id = payload.member_id or None
    if payload.group_number is not None:
        if patient.group_number != (payload.group_number or None):
            changed_fields.append("group_number")
        patient.group_number = payload.group_number or None
    if payload.eligibility_status is not None:
        if patient.eligibility_status != (payload.eligibility_status or None):
            changed_fields.append("eligibility_status")
        patient.eligibility_status = payload.eligibility_status or None
    if payload.phone_number is not None:
        if patient.phone_number != (payload.phone_number or None):
            changed_fields.append("phone_number")
        patient.phone_number = payload.phone_number or None
    if payload.email is not None:
        if patient.email != (payload.email or None):
            changed_fields.append("email")
        patient.email = payload.email or None
    if payload.address_line1 is not None:
        if patient.address_line1 != (payload.address_line1 or None):
            changed_fields.append("address_line1")
        patient.address_line1 = payload.address_line1 or None
    if payload.city is not None:
        if patient.city != (payload.city or None):
            changed_fields.append("city")
        patient.city = payload.city or None
    if payload.state is not None:
        if patient.state != (payload.state or None):
            changed_fields.append("state")
        patient.state = payload.state or None
    if payload.zip_code is not None:
        if patient.zip_code != (payload.zip_code or None):
            changed_fields.append("zip_code")
        patient.zip_code = payload.zip_code or None
    if payload.preferred_contact_method is not None:
        if patient.preferred_contact_method != (payload.preferred_contact_method or None):
            changed_fields.append("preferred_contact_method")
        patient.preferred_contact_method = payload.preferred_contact_method or None
    if payload.preferred_language is not None:
        if patient.preferred_language != (payload.preferred_language or None):
            changed_fields.append("preferred_language")
        patient.preferred_language = payload.preferred_language or None
    if payload.risk_level is not None:
        if patient.risk_level != (payload.risk_level or None):
            changed_fields.append("risk_level")
        patient.risk_level = payload.risk_level or None

    # Full replacement, not additive — this is the one place in the app where a
    # clinical program can genuinely be REMOVED, unlike intake completion (which
    # only ever adds one) or bulk import (which only ever sets the initial set).
    # An explicit edit through a form is exactly the right place for "undo a
    # program that was added in error" to live.
    if payload.clinical_program_keys is not None:
        current_keys = {pp.program.key for pp in patient.programs}
        new_keys = set(payload.clinical_program_keys)
        if current_keys != new_keys:
            changed_fields.append("clinical_programs")
        newly_enrolled = not current_keys and new_keys
        db.query(PatientProgram).filter_by(patient_id=patient_id).delete()
        for key in payload.clinical_program_keys:
            program = db.query(Program).filter_by(key=key).first()
            if program:
                db.add(PatientProgram(patient_id=patient_id, program_id=program.id))
        if newly_enrolled:
            db.commit()
            fire_event(db, "patient.enrolled", {"program_keys": sorted(new_keys)}, patient, staff, dry_run=False)

    db.commit()
    db.refresh(patient)
    if changed_fields:
        log_audit(db, "patient", patient_id, "updated", staff, details={"changed_fields": changed_fields}, related_patient_id=patient_id)
    return patient


@router.get("/{patient_id}/case")
def get_patient_primary_case(patient_id: str, db: Session = Depends(get_db)):
    """Returns the patient's auto-created primary case — lets the frontend reuse
    every existing case-scoped endpoint (result submission, snapshot context)
    without a separate patient-scoped copy of that logic."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    case = get_or_create_primary_case(db, patient)
    return {"id": str(case.id), "context": case.context}


def _has_real_answer(answers: dict | None) -> bool:
    """A draft with every field still empty/unset shouldn't read as 'In Progress' —
    only actually-entered content should."""
    if not answers:
        return False
    return any(v not in (None, "", []) for v in answers.values())


@router.get("/{patient_id}/assessments", response_model=list[PatientAssessmentSummary])
def list_patient_assessments(patient_id: str, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    case = get_or_create_primary_case(db, patient)

    assigned = db.query(AssignedAssessment).filter_by(case_id=case.id).all()
    summaries = []
    for a in assigned:
        definition = db.query(AssessmentDefinition).filter_by(id=a.assessment_definition_id).first()
        result = (
            db.query(AssessmentResult)
            .filter_by(case_id=case.id, assessment_definition_id=a.assessment_definition_id)
            .order_by(AssessmentResult.completed_at.desc())
            .first()
        )
        if result:
            status = "Completed"
        elif _has_real_answer(a.draft_answers):
            status = "In Progress"
        else:
            status = "Scheduled"
        summaries.append(PatientAssessmentSummary(
            assigned_assessment_id=a.id,
            assessment_definition_key=definition.key,
            title=a.title_override or definition.title,
            source=a.source,
            mandatory=a.mandatory,
            scheduled_date=a.scheduled_date,
            status=status,
            draft_answers=a.draft_answers,
            result_id=result.id if result else None,
            result_headline=result.result.get("headline") if result else None,
            result_severity=result.result.get("headlineSeverity") if result else None,
        ))
    # Mandatory-and-incomplete first, matching the original's own ordering — then
    # by scheduled date within each group.
    return sorted(
        summaries,
        key=lambda s: (0 if (s.mandatory and s.status != "Completed") else 1, s.scheduled_date or date.min),
    )


@router.post("/{patient_id}/confirm-pathway")
def confirm_pathway(patient_id: str, payload: ConfirmPathwayRequest, db: Session = Depends(get_db)):
    """Creates AssignedAssessment rows only for what was explicitly confirmed after
    review — the intake's own suggestion is never auto-applied. Silently skips
    anything already assigned, so confirming the same pathway twice (or confirming
    after some items were already added another way) doesn't duplicate."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    case = get_or_create_primary_case(db, patient)

    already_assigned = {
        a.assessment_definition_id
        for a in db.query(AssignedAssessment).filter_by(case_id=case.id).all()
    }
    created = 0
    for item in payload.items:
        definition = db.query(AssessmentDefinition).filter_by(key=item.module_id).first()
        if not definition or definition.id in already_assigned:
            continue
        db.add(AssignedAssessment(
            case_id=case.id, assessment_definition_id=definition.id,
            title_override=None, source="template", mandatory=item.mandatory,
        ))
        already_assigned.add(definition.id)
        created += 1
    db.commit()
    return {"assigned": created}


@router.patch("/{patient_id}/assigned-assessments/{assigned_id}/draft")
def save_draft(patient_id: str, assigned_id: str, payload: SaveDraftRequest, db: Session = Depends(get_db)):
    """Saves whatever's currently answered without computing or storing a result —
    this is what makes 'Save Progress' distinct from 'Mark Complete'. Never touches
    AssessmentResult, so a saved draft can't accidentally look like a real,
    clinician-reviewed result."""
    assigned = db.query(AssignedAssessment).filter_by(id=assigned_id).first()
    if not assigned:
        raise HTTPException(status_code=404, detail="Assigned assessment not found")
    assigned.draft_answers = payload.answers
    db.commit()
    return {"saved": True}


@router.post("/{patient_id}/integrated-care-plan")
def integrated_care_plan(patient_id: str, db: Session = Depends(get_db)):
    """Synthesizes across every completed assessment AND every successfully
    extracted document for this patient — recomputes nothing from either source
    (each assessment's own result is trusted as-is, documents are read as
    supporting context), just asks the AI to find patterns and nuance a single
    assessment result or a document sitting unread wouldn't otherwise surface.

    Deliberately does NOT also generate PGI suggestions anymore — that used to
    happen automatically in this same call, which meant regenerating the care
    plan (e.g. because only the PGI suggestions felt off) wasted a full
    re-synthesis every time, and there was no natural point to review or edit the
    plan before PGI got built from it. See suggest_pgi_from_plan below, a
    separate, explicit action a person takes only once they're satisfied with
    the plan shown here."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    case = get_or_create_primary_case(db, patient)

    results = db.query(AssessmentResult).filter_by(case_id=case.id).all()
    completed = []
    for r in results:
        definition = db.query(AssessmentDefinition).filter_by(id=r.assessment_definition_id).first()
        completed.append({
            "title": definition.title if definition else "Unknown assessment",
            "headline": r.result.get("headline"),
            "severity": r.result.get("headlineSeverity"),
            "flags": [f.get("text") for f in r.result.get("flags", [])],
            "notes": r.result.get("notes", ""),
        })

    docs = db.query(PatientDocument).filter_by(patient_id=patient_id, extraction_status="ok").all()
    document_texts = [{"filename": d.filename, "extracted_text": d.extracted_text} for d in docs]

    try:
        plan = generate_integrated_care_plan(patient.name or "This patient", completed, document_texts)
    except IntegratedCarePlanError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Only set the first time — this answers "has a care plan ever existed for
    # this patient," not "when was the most recent one," since the plan itself
    # is generated fresh each time and was never persisted before this field existed.
    if not patient.care_plan_created_at:
        patient.care_plan_created_at = utcnow()
        db.commit()

    return {
        "completedCount": len(completed),
        "documentCount": len(document_texts),
        "carePlan": plan,
    }


class SuggestPgiFromPlanRequest(BaseModel):
    summary: str
    keyFindings: list[str] = []
    actionItems: list[dict] = []


@router.post("/{patient_id}/suggest-pgi-from-plan")
def suggest_pgi_from_plan(patient_id: str, payload: SuggestPgiFromPlanRequest, db: Session = Depends(get_db)):
    """A separate, explicit action — deliberately not automatic alongside
    generating the care plan above. Takes the plan AS GIVEN in the request body,
    which is exactly what makes this genuinely reviewable: since the plan is
    never persisted, whatever the frontend sends here is authoritative — a person
    can edit the summary or key findings in the UI before calling this, and PGI
    gets suggested from their edited version, not silently regenerated from
    scratch. Regenerating the care plan and regenerating PGI are two separate
    actions now, not one coupled to the other."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    try:
        suggested_pgi = suggest_pgi_from_care_plan(patient.name or "This patient", payload.model_dump())
    except IntegratedCarePlanError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"suggestedPgi": suggested_pgi}


@router.get("/{patient_id}/onboarding-progress", response_model=OnboardingProgressOut)
def get_onboarding_progress(patient_id: str, db: Session = Depends(get_db)):
    """Mostly computed from state that already exists elsewhere — this endpoint
    doesn't introduce a separate 'onboarding' concept to keep in sync by hand,
    it just answers real questions about real data. program_status is the one
    genuine exception: only a person can meaningfully decide a patient's program
    is actually finished, so that one field is a direct, explicit flag rather
    than inferred from anything."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    case = get_or_create_primary_case(db, patient)

    has_completed_assessment = db.query(AssessmentResult).filter_by(case_id=case.id).first() is not None
    has_pgi_problem = db.query(Problem).filter_by(patient_id=patient_id).first() is not None

    steps = [
        {"key": "patient_created", "label": "Patient Created", "complete": True},
        {"key": "program_enrolled", "label": "Program Enrolled", "complete": len(patient.programs) > 0},
        {"key": "assessment_completed", "label": "Assessment Completed", "complete": has_completed_assessment},
        {"key": "care_plan_created", "label": "Care Plan Created", "complete": patient.care_plan_created_at is not None},
        # "Activated" is interpreted here as "translated into actionable PGI
        # items" — a care plan that's only ever been generated and read isn't
        # yet driving any real, tracked work.
        {"key": "care_plan_activated", "label": "Care Plan Activated", "complete": has_pgi_problem},
        {"key": "program_completed", "label": "Program Completed", "complete": patient.program_status == "completed"},
    ]
    return {"steps": steps, "program_status": patient.program_status}


class ProgramCompleteRequest(BaseModel):
    outcome: str | None = None  # e.g. "Recovered"|"Not recovered"|"Deceased" — optional, drives care_plan.review_due if given


@router.post("/{patient_id}/complete-program", response_model=PatientOut)
def complete_program(patient_id: str, payload: ProgramCompleteRequest | None = None, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    """The action that was missing entirely — program_status was only ever READ
    by the onboarding stepper, never written anywhere, so 'Program Completed'
    could never actually become true for any patient. This doesn't touch
    is_active — a patient can complete their program and still be an active
    patient (e.g. moving to a maintenance phase), or be reopened later if their
    program resumes."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.program_status = "completed"
    db.commit()
    log_audit(db, "patient", patient_id, "program_completed", staff, related_patient_id=patient_id)

    outcome = payload.outcome if payload else None
    if outcome:
        fire_event(db, "care_plan.review_due", {"outcome": outcome}, patient, staff, dry_run=False)
    return patient


@router.post("/{patient_id}/reopen-program", response_model=PatientOut)
def reopen_program(patient_id: str, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.program_status = "active"
    db.commit()
    log_audit(db, "patient", patient_id, "program_reopened", staff, related_patient_id=patient_id)
    return patient


class PatientDeactivateRequest(BaseModel):
    reason: str | None = None


@router.post("/{patient_id}/deactivate", response_model=PatientOut)
def deactivate_patient(
    patient_id: str, payload: PatientDeactivateRequest,
    db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin", "care_manager")),
):
    """A soft delete — the patient record and every piece of history attached to
    it (assessments, documents, notes, tasks, PGI) stay completely intact.
    is_active=False just removes them from the default roster view; nothing is
    actually destroyed, matching exactly the same philosophy already used for
    Staff (block, never delete). Restricted to admin/care_manager — deactivating
    a patient (discharge, transfer, duplicate cleanup) is a care-coordination
    decision, not something every registered staff member should be able to do
    unilaterally."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.is_active = False
    patient.deactivated_reason = payload.reason
    db.commit()
    log_audit(db, "patient", patient_id, "deactivated", staff, details={"reason": payload.reason}, related_patient_id=patient_id)
    return patient


@router.post("/{patient_id}/reactivate", response_model=PatientOut)
def reactivate_patient(patient_id: str, db: Session = Depends(get_db), staff: Staff = Depends(require_role("admin", "care_manager"))):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.is_active = True
    patient.deactivated_reason = None
    db.commit()
    log_audit(db, "patient", patient_id, "reactivated", staff, related_patient_id=patient_id)
    return patient


class LogContactRequest(BaseModel):
    contact_date: datetime | None = None  # defaults to now if not provided — lets someone backdate a call they forgot to log immediately


@router.post("/{patient_id}/log-contact", response_model=PatientOut)
def log_contact(patient_id: str, payload: LogContactRequest, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    """Deliberately open to any registered staff member, not restricted like
    deactivate/reactivate — recording 'I just reached this patient' is normal,
    frequent clinical coordination, not an administrative action. Deliberately
    distinct from any assessment-completion or task-activity timestamp: this
    specifically answers 'when did a person last actually reach this patient,'
    which nothing else in this app tracks."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.last_contact_date = payload.contact_date or utcnow()
    db.commit()
    log_audit(db, "patient", patient_id, "contact_logged", staff, details={"contact_date": str(patient.last_contact_date)}, related_patient_id=patient_id)
    return patient


@router.get("/{patient_id}/audit-log", response_model=list[AuditLogOut])
def get_patient_audit_log(patient_id: str, db: Session = Depends(get_db)):
    """Shows this patient's own audit trail directly, plus everything logged
    against entities that belong to them (tasks, care notes, PGI items,
    documents) — a single, real view of everything that's happened to this
    patient's record, not just edits to the Patient row itself.

    Queries related_patient_id directly rather than looking up which tasks/
    notes/etc. currently exist for this patient — that lookup approach used to
    silently miss any event for an entity that's since been deleted (a task
    created then deleted would vanish from the trail entirely), which is
    exactly the moment an audit trail matters most."""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    return (
        db.query(AuditLog)
        .filter(AuditLog.related_patient_id == patient_id)
        .order_by(AuditLog.performed_at.desc())
        .all()
    )


@router.post("/{patient_id}/assign-assessment", status_code=201)
def assign_assessment(patient_id: str, payload: AssignAssessmentRequest, db: Session = Depends(get_db), staff: Staff | None = Depends(get_current_staff)):
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    definition = db.query(AssessmentDefinition).filter_by(key=payload.assessment_definition_key).first()
    if not definition:
        raise HTTPException(status_code=404, detail=f"Assessment '{payload.assessment_definition_key}' not found")
    case = get_or_create_primary_case(db, patient)

    assigned = AssignedAssessment(
        case_id=case.id,
        assessment_definition_id=definition.id,
        title_override=payload.title_override,
        source=payload.source,
        scheduled_date=payload.scheduled_date,
        mandatory=payload.mandatory,
    )
    db.add(assigned)
    db.commit()
    log_audit(
        db, "assigned_assessment", assigned.id, "assigned", staff,
        details={"assessment_key": definition.key, "assessment_title": payload.title_override or definition.title, "scheduled_date": str(payload.scheduled_date) if payload.scheduled_date else None, "mandatory": payload.mandatory},
        related_patient_id=patient_id,
    )
    return {"id": str(assigned.id), "case_id": str(case.id)}
