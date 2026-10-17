"""
Executes a parsed rule's actions against real data — the part that makes this
a genuine runtime engine wired into this app's actual patients, tasks, PGI,
and notifications, rather than the reference prototype's localStorage sandbox.

Kept deliberately separate from rules_engine.py (the pure DSL parser/
evaluator, no DB dependency at all) so the grammar itself stays trivially
testable without a database, while this module owns every real side effect.
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.models import Goal, Patient, PatientStaffAssignment, Problem, Staff, Task, utcnow
from app.notifications import create_notification
from app.rules_engine import WORKFLOWS

# Maps DSL "escalation" workflow states onto this app's real risk_level values
# — a direct, natural correspondence, unlike care_plan (which needed a whole
# new field) or visit (which has no real field to map onto at all).
_ESCALATION_TO_RISK_LEVEL = {
    "Normal": "low",
    "Elevated": "medium",
    "Escalated": "high",
    "Crisis": "critical",
}

_CARE_PLAN_STATE_TO_FIELD = {
    "Draft": "draft",
    "Active": "active",
    "Under Review": "under_review",
    "Recovered": "recovered",
    "Deceased": "deceased",
}


def _resolve_due_date(due: str) -> date | None:
    """A DSL 'due' value is free text ("24h", "same_day", "next_visit", or
    anything else) — this is a best-effort translation into a real date, not
    a guarantee every input maps meaningfully. Unrecognized values fall back
    to a week out rather than leaving due_date unset, since an unset due date
    on a rule-generated task would be easy to overlook entirely."""
    due = (due or "").strip().lower()
    today = utcnow().date()
    if due in ("24h", "1d", "tomorrow"):
        return today + timedelta(days=1)
    if due == "same_day":
        return today
    if due == "next_visit":
        return None  # no real "next scheduled visit" concept exists yet — noted in the task description instead
    if due.endswith("h") and due[:-1].isdigit():
        return today + timedelta(days=max(1, int(due[:-1]) // 24))
    if due.endswith("d") and due[:-1].isdigit():
        return today + timedelta(days=int(due[:-1]))
    return today + timedelta(days=7)


def _resolve_assignee_staff_id(patient: Patient, assignee: str, db: Session) -> str | None:
    """The DSL's assignee is free text — a role name ("Nurse", "Care Admin"),
    a placeholder ("assigned_care_admin"), or occasionally a real name. This
    tries to resolve it to a real staff member via the patient's actual care
    team; if nothing matches, the task is still created (assigned_to_id is
    nullable) with the raw text preserved in its description instead of
    silently dropped."""
    if not assignee:
        return None
    normalized = assignee.strip().lower().replace("_", " ")
    role_guess = None
    if "nurse" in normalized:
        role_guess = "nurse"
    elif "admin" in normalized or "manager" in normalized:
        role_guess = "care_manager"
    elif "provider" in normalized or "physician" in normalized or "nephrologist" in normalized or "doctor" in normalized:
        role_guess = "provider"
    if not role_guess:
        return None
    assignment = (
        db.query(PatientStaffAssignment)
        .filter_by(patient_id=patient.id, role_on_patient=role_guess)
        .first()
    )
    return str(assignment.staff_id) if assignment else None


def _get_or_create_rules_problem(patient: Patient, db: Session) -> Problem:
    """ADD_GOAL actions need a real Problem to attach to — Goal.problem_id
    isn't nullable, and creating a Goal with no real clinical Problem behind
    it would quietly undermine what PGI is actually for. Rather than fake one
    up per goal, every rules-engine-generated goal for a patient shares one
    clearly-labeled Problem, created once and reused."""
    existing = (
        db.query(Problem)
        .filter_by(patient_id=patient.id, description="Auto-generated from business rules")
        .first()
    )
    if existing:
        return existing
    problem = Problem(patient_id=patient.id, description="Auto-generated from business rules", status="active")
    db.add(problem)
    db.commit()
    return problem


_GENERIC_CARE_TEAM_TARGETS = {"assigned_care_team", "care_team", "care_team_alert", ""}


def _resolve_notification_recipients(patient: Patient, to: str, db: Session) -> list[Staff]:
    """'to' is either a generic care-team target (e.g. 'assigned_care_team' —
    what every currently-seeded rule uses) or a specific role
    ('nurse', 'provider', 'care_manager', 'admin', matching
    PatientStaffAssignment.role_on_patient's real values). A generic target
    notifies everyone on the care team, exactly as before. A specific role
    notifies only staff assigned in that role — including correctly
    notifying nobody if no one with that role is on this patient's care
    team, rather than silently falling back to everyone (which would make
    the role filter meaningless). Spaces/hyphens in the DSL are normalized
    to underscores, since a rule author may not know the exact internal
    enum spelling. Falls back to nobody (not an error) if the patient
    genuinely has no care team assigned yet, rather than guessing at a
    recipient."""
    assignments = db.query(PatientStaffAssignment).filter_by(patient_id=patient.id).all()
    if not assignments:
        return []

    to_normalized = (to or "").strip().lower().replace(" ", "_").replace("-", "_")
    if to_normalized in _GENERIC_CARE_TEAM_TARGETS:
        staff_ids = [a.staff_id for a in assignments]
    else:
        staff_ids = [a.staff_id for a in assignments if a.role_on_patient == to_normalized]
        if not staff_ids:
            return []

    return db.query(Staff).filter(Staff.id.in_(staff_ids)).all()


def execute_actions(actions: list[dict], patient: Patient, db: Session, staff: Staff | None, dry_run: bool = False, rule_name: str | None = None) -> list[dict]:
    """Runs every action in order, exactly as the reference's executeActions
    does. Returns a list of {action, summary} dicts describing what happened
    — used both for the execution log and for the "test in isolation" dry-run
    response, so a rule author sees the same shape of result either way.

    dry_run=True describes what WOULD happen without writing anything real —
    this is what backs "test this rule in isolation," since testing a rule
    should never have real side effects on a real patient.

    rule_name is the saved rule's own name, recorded on each created task,
    goal, or notification as source_rule_name — None here just means no real,
    named rule is behind this call (e.g. testing raw, unsaved DSL text),
    which naturally can't create anything real anyway since that path is
    always dry_run=True."""
    results = []
    for action in actions:
        summary = _execute_one(action, patient, db, staff, dry_run, rule_name)
        results.append({"action": action, "summary": summary})
    return results


def _execute_one(action: dict, patient: Patient, db: Session, staff: Staff | None, dry_run: bool, rule_name: str | None = None) -> str:
    action_type = action["type"]

    if action_type == "CREATE_TASK":
        due_date = _resolve_due_date(action.get("due", ""))
        assignee_id = _resolve_assignee_staff_id(patient, action.get("assignee", ""), db)
        description = f"Created by business rule. Requested assignee: {action.get('assignee', '—')}." + (
            " (no scheduled visit date exists yet — treat as due at the next visit)" if action.get("due") == "next_visit" else ""
        )
        if not dry_run:
            task = Task(
                patient_id=patient.id, title=action.get("label", "Untitled task"), description=description,
                assigned_to_id=assignee_id, due_date=due_date, created_by_id=staff.id if staff else None,
                source_rule_name=rule_name,
            )
            db.add(task)
            db.commit()
            log_audit(db, "task", task.id, "created", staff, details={"source": "business_rule", "title": task.title}, related_patient_id=str(patient.id))
        return f'Created task "{action.get("label")}" for {action.get("assignee")}, due {action.get("due")}'

    if action_type == "UPDATE_STATUS":
        # Deliberately free text, not written to any single specific field —
        # the DSL's UPDATE_STATUS is a generic "set the patient's status"
        # concept the reference itself never ties to one particular field
        # either. Recorded in the audit trail so it's visible and traceable,
        # even though nothing in the UI currently displays a dedicated
        # "rules-engine status" field.
        if not dry_run:
            log_audit(db, "patient", patient.id, "status_updated_by_rule", staff, details={"value": action.get("value")}, related_patient_id=str(patient.id))
        return f'Recorded status update: "{action.get("value")}"'

    if action_type == "ADD_GOAL":
        if not dry_run:
            problem = _get_or_create_rules_problem(patient, db)
            goal = Goal(problem_id=problem.id, description=action.get("goal", ""), source_rule_name=rule_name)
            db.add(goal)
            db.commit()
            log_audit(db, "pgi_goal", goal.id, "created", staff, details={"source": "business_rule", "description": goal.description}, related_patient_id=str(patient.id))
        return f'Added PGI goal: "{action.get("goal")}"'

    if action_type == "SEND_NOTIFICATION":
        if not dry_run:
            recipients = _resolve_notification_recipients(patient, action.get("to", ""), db)
            for recipient in recipients:
                create_notification(
                    db, recipient=recipient, notification_type="business_rule",
                    title=action.get("template", "Notification"),
                    body=f"Triggered by business rule for {patient.name}.",
                    related_patient_id=str(patient.id),
                    source_rule_name=rule_name,
                )
        return f'Sent notification "{action.get("template")}" to {action.get("to")}'

    if action_type == "TRANSITION":
        return _execute_transition(action, patient, db, staff, dry_run)

    if action_type == "ESCALATE_RISK":
        level = (action.get("level") or "").strip().lower()
        if not dry_run and level in {"low", "medium", "high", "critical"}:
            old_level = patient.risk_level
            patient.risk_level = level
            db.commit()
            log_audit(db, "patient", patient.id, "risk_escalated_by_rule", staff, details={"from": old_level, "to": level}, related_patient_id=str(patient.id))
        return f'Escalated risk level to "{action.get("level")}"'

    return f"Unrecognized action type: {action_type}"


def _execute_transition(action: dict, patient: Patient, db: Session, staff: Staff | None, dry_run: bool) -> str:
    workflow = action.get("workflow")
    target = action.get("target")
    if workflow not in WORKFLOWS:
        return f'Unknown workflow "{workflow}" — transition ignored.'
    if target not in WORKFLOWS[workflow]["states"]:
        return f'"{target}" is not a valid state for {WORKFLOWS[workflow]["label"]} — transition ignored.'

    if workflow == "care_plan":
        if not dry_run:
            old = patient.care_plan_stage
            patient.care_plan_stage = _CARE_PLAN_STATE_TO_FIELD[target]
            db.commit()
            log_audit(db, "patient", patient.id, "care_plan_stage_changed_by_rule", staff, details={"from": old, "to": patient.care_plan_stage}, related_patient_id=str(patient.id))
        return f'Care plan stage \u2192 "{target}"'

    if workflow == "escalation":
        if not dry_run:
            old = patient.risk_level
            patient.risk_level = _ESCALATION_TO_RISK_LEVEL[target]
            db.commit()
            log_audit(db, "patient", patient.id, "risk_level_changed_by_rule", staff, details={"from": old, "to": patient.risk_level}, related_patient_id=str(patient.id))
        return f'Risk level \u2192 "{target}" (mapped from escalation state)'

    # workflow == "visit" — deliberately not backed by any real field yet.
    # Still validated and reported so it's visible in the execution log and
    # in "test in isolation," not silently swallowed.
    return f'Visit scheduling \u2192 "{target}" (recorded only \u2014 this app has no real visit-scheduling field yet)'
