from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import get_current_staff, require_staff
from app.auth0_management import Auth0ManagementError, create_auth0_user, find_auth0_user_by_email, set_user_blocked, trigger_password_reset_email, trigger_verification_email, update_auth0_user
from app.database import get_db
from app.models import Patient, PatientStaffAssignment, Staff
from app.permissions import require_role
from app.schemas import PatientStaffAssignmentCreate, PatientStaffAssignmentOut, StaffCreate, StaffInviteCreate, StaffOut, StaffUpdate

router = APIRouter(prefix="/api/staff", tags=["staff"])

VALID_ROLES = {"care_manager", "nurse", "provider", "admin"}


@router.get("/me", response_model=StaffOut | None)
def get_my_staff_record(staff: Staff | None = Depends(get_current_staff)):
    """Returns null (not a 404) for an authenticated Auth0 user with no staff
    record yet — that's a normal, expected state the frontend needs to handle
    explicitly (e.g. showing 'contact an admin to be added'), not an error."""
    return staff


@router.get("", response_model=list[StaffOut])
def list_staff(db: Session = Depends(get_db), actor: Staff = Depends(require_staff)):
    """Returns everyone, active or inactive — filtering to active-only would make
    a deactivated person disappear from this list entirely, with no way to find
    and reactivate them again through the UI. The status field is still on each
    record for the frontend to display and filter by if it wants to."""
    return db.query(Staff).all()


@router.post("", response_model=StaffOut, status_code=201)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    """The manual-link path — for a staff member who already has their own Auth0
    account and you're just registering their known auth0_sub directly. For
    creating a brand new account from scratch, use POST /invite instead."""
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")
    if db.query(Staff).filter_by(auth0_sub=payload.auth0_sub).first():
        raise HTTPException(status_code=409, detail="A staff record for this Auth0 account already exists")
    staff = Staff(auth0_sub=payload.auth0_sub, name=payload.name, email=payload.email, role=payload.role)
    db.add(staff)
    db.commit()
    log_audit(db, "staff", staff.id, "created", actor, details={"name": staff.name, "role": staff.role, "method": "manual_link"})
    return staff


@router.get("/auth0-lookup")
def lookup_auth0_account_by_email(email: str, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    """The piece that was actually missing: POST /api/staff (manual-link)
    already supported registering someone's EXISTING Auth0 account, but only
    if you already knew their internal auth0_sub — not something anyone would
    have on hand without digging through the Auth0 dashboard directly. This is
    the real fix for 'their account still exists, but their Staff row doesn't':
    look them up by the one thing everyone actually knows, their email, then
    POST /api/staff can register that real, found account directly.

    Also checks whether a Staff row already exists for that account, so the
    frontend can show a clear message rather than a confusing 409 on the next step."""
    try:
        found = find_auth0_user_by_email(email)
    except Auth0ManagementError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not found:
        return {"found": False}

    existing_staff = db.query(Staff).filter_by(auth0_sub=found["auth0_sub"]).first()
    return {
        "found": True,
        "auth0_sub": found["auth0_sub"],
        "name": found["name"],
        "email": found["email"],
        "already_linked": existing_staff is not None,
        "already_linked_status": existing_staff.status if existing_staff else None,
    }


@router.post("/invite", status_code=201)
def invite_staff(payload: StaffInviteCreate, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    """The real end-to-end flow: creates a genuine Auth0 account, registers it as
    staff, and sends the new person a real password-set email — no auth0_sub
    ever needs to be manually copied from the Auth0 dashboard.

    The Staff row is created as soon as the Auth0 account exists, before the
    email is even attempted — a real account should never become an orphaned,
    untracked thing just because the invite email happened to fail to send.
    email_sent in the response tells the frontend whether that email attempt
    itself succeeded, so a failure there can be surfaced and retried
    (via /resend-invite) without needing to redo account creation."""
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")

    try:
        auth0_user_id = create_auth0_user(payload.email, payload.name)
    except Auth0ManagementError as e:
        raise HTTPException(status_code=502, detail=str(e))

    staff = Staff(auth0_sub=auth0_user_id, name=payload.name, email=payload.email, role=payload.role)
    db.add(staff)
    db.commit()
    log_audit(db, "staff", staff.id, "created", actor, details={"name": staff.name, "role": staff.role, "method": "invite"})

    email_sent = True
    email_error = None
    try:
        trigger_password_reset_email(payload.email)
    except Auth0ManagementError as e:
        email_sent = False
        email_error = str(e)

    # Deliberately NOT triggering a verification email here — Auth0 already
    # sends one automatically as part of create_auth0_user, when this
    # connection has "require email verification" enabled. Calling this
    # explicitly too, on top of that, created a real, observed duplicate
    # (two differently-branded "Verify your email" messages for the same
    # invite). resend_invite still calls this explicitly below, since that
    # path never creates a new Auth0 user and so never gets Auth0's
    # automatic one — it's the only way to re-trigger verification for an
    # already-existing, still-unverified account.

    return {
        "staff": StaffOut.model_validate(staff).model_dump(mode="json"),
        "email_sent": email_sent,
        "email_error": email_error,
    }


@router.post("/{staff_id}/resend-invite")
def resend_invite(staff_id: str, db: Session = Depends(get_db), actor: Staff = Depends(require_staff)):
    staff = db.query(Staff).filter_by(id=staff_id).first()
    if not staff or not staff.email:
        raise HTTPException(status_code=404, detail="Staff member not found, or has no email on file")
    try:
        trigger_password_reset_email(staff.email)
    except Auth0ManagementError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Best-effort: setting a password via the reset link above doesn't prove
    # email ownership — email_verified is set False at account creation and
    # nothing else ever flips it. A failure here shouldn't block the resend
    # overall, since the person can still log in via the reset link either
    # way; it's surfaced in the response instead of silently swallowed.
    verification_email_sent = True
    verification_error = None
    try:
        trigger_verification_email(staff.auth0_sub)
    except Auth0ManagementError as e:
        verification_email_sent = False
        verification_error = str(e)

    log_audit(db, "staff", staff.id, "invite_resent", actor)
    return {"email_sent": True, "verification_email_sent": verification_email_sent, "verification_error": verification_error}


@router.patch("/{staff_id}", response_model=StaffOut)
def update_staff(staff_id: str, payload: StaffUpdate, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    staff = db.query(Staff).filter_by(id=staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    if payload.role is not None and payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")

    # Auth0 is the source of truth for name/email, so it's updated first — if
    # this fails, the local record is deliberately left untouched rather than
    # drifting out of sync with the real account.
    if payload.name is not None or payload.email is not None:
        try:
            update_auth0_user(staff.auth0_sub, name=payload.name, email=payload.email)
        except Auth0ManagementError as e:
            raise HTTPException(status_code=502, detail=str(e))

    changed_fields = []
    if payload.name is not None and payload.name != staff.name:
        changed_fields.append("name")
        staff.name = payload.name
    if payload.email is not None and payload.email != staff.email:
        changed_fields.append("email")
        staff.email = payload.email
    if payload.role is not None and payload.role != staff.role:
        changed_fields.append("role")
        staff.role = payload.role
    db.commit()
    if changed_fields:
        log_audit(db, "staff", staff.id, "updated", actor, details={"changed_fields": changed_fields})
    return staff


@router.post("/{staff_id}/deactivate", response_model=StaffOut)
def deactivate_staff(staff_id: str, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    """Blocks the real Auth0 account (they genuinely cannot log in anymore) and
    marks the local record inactive — deliberately not a delete. Their care-note
    authorship, past task assignments, and audit history all stay exactly as
    they were; only future login is affected."""
    staff = db.query(Staff).filter_by(id=staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    # Without this check, deactivating the last remaining admin would be
    # permanent and unrecoverable through the app itself: invite/reactivate are
    # now admin-only actions, so no one left could create a new admin or
    # reactivate this one. This is the one case where "no delete, only
    # deactivate" isn't enough protection on its own.
    if staff.role == "admin" and staff.status == "active":
        other_active_admins = db.query(Staff).filter(
            Staff.role == "admin", Staff.status == "active", Staff.id != staff.id,
        ).count()
        if other_active_admins == 0:
            raise HTTPException(
                status_code=409,
                detail="Cannot deactivate the last active admin — promote another staff member to admin first.",
            )

    try:
        set_user_blocked(staff.auth0_sub, blocked=True)
    except Auth0ManagementError as e:
        raise HTTPException(status_code=502, detail=str(e))
    staff.status = "inactive"
    db.commit()
    log_audit(db, "staff", staff.id, "deactivated", actor)
    return staff


@router.post("/{staff_id}/reactivate", response_model=StaffOut)
def reactivate_staff(staff_id: str, db: Session = Depends(get_db), actor: Staff = Depends(require_role("admin"))):
    staff = db.query(Staff).filter_by(id=staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    try:
        set_user_blocked(staff.auth0_sub, blocked=False)
    except Auth0ManagementError as e:
        raise HTTPException(status_code=502, detail=str(e))
    staff.status = "active"
    db.commit()
    log_audit(db, "staff", staff.id, "reactivated", actor)
    return staff


@router.post("/patients/{patient_id}/assignments", response_model=PatientStaffAssignmentOut, status_code=201)
def assign_staff_to_patient(
    patient_id: str, payload: PatientStaffAssignmentCreate,
    db: Session = Depends(get_db), actor: Staff = Depends(require_staff),
):
    if payload.role_on_patient not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role_on_patient must be one of {sorted(VALID_ROLES)}")
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    staff = db.query(Staff).filter_by(id=str(payload.staff_id)).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    assignment = PatientStaffAssignment(
        patient_id=patient_id, staff_id=str(payload.staff_id), role_on_patient=payload.role_on_patient,
    )
    db.add(assignment)
    db.commit()
    log_audit(db, "patient", patient_id, "staff_assigned", actor, details={"staff_name": staff.name, "role_on_patient": payload.role_on_patient}, related_patient_id=patient_id)
    return assignment


@router.get("/patients/{patient_id}/assignments", response_model=list[PatientStaffAssignmentOut])
def list_patient_staff(patient_id: str, db: Session = Depends(get_db), actor: Staff = Depends(require_staff)):
    return db.query(PatientStaffAssignment).filter_by(patient_id=patient_id).all()


@router.delete("/patients/{patient_id}/assignments/{assignment_id}", status_code=204)
def remove_patient_staff_assignment(
    patient_id: str, assignment_id: str, db: Session = Depends(get_db), actor: Staff = Depends(require_staff),
):
    assignment = db.query(PatientStaffAssignment).filter_by(id=assignment_id, patient_id=patient_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    db.delete(assignment)
    db.commit()
    log_audit(db, "patient", patient_id, "staff_unassigned", actor, related_patient_id=patient_id)
