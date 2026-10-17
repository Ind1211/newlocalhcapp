"""
The real, shared logic behind both the on-demand /api/notifications/check-due
endpoint and the new real background scheduler (see app.scheduler). Kept in
one place deliberately, so the two callers can never quietly drift apart —
whichever one runs, the exact same checks execute the exact same way.

Two things happen here:
1. The pre-existing due-soon/overdue notification scans (moved here unchanged
   from app.routers.notifications, where they used to live directly on the
   endpoint).
2. A new check: any incomplete task whose due date has passed fires the real
   task.overdue event through the rules engine — but only once per task,
   ever, tracked via Task.overdue_event_fired_at, so a scheduler running
   every few minutes doesn't re-fire the same rule (and whatever task/
   notification it creates) over and over for a task that's been overdue
   for days.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import (
    AssessmentDefinition, AssessmentResult, AssignedAssessment, Case,
    Notification, Patient, PatientStaffAssignment, Staff, Task, utcnow,
)
from app.notifications import create_notification

TASK_DUE_SOON_WINDOW_DAYS = 2


def run_due_checks(db: Session) -> dict:
    """Genuinely idempotent, safe to call repeatedly (on-demand from the
    frontend, or from the real scheduler on a fixed interval): every
    notification check below explicitly looks for an already-existing
    notification for the exact same (type, entity) pair before creating a
    new one, so calling this any number of times never double-notifies
    anyone for the same underlying event. The task.overdue firing has its
    own, separate once-ever guard (overdue_event_fired_at), since that's a
    different kind of duplicate to prevent — not a duplicate notification,
    but a duplicate rule execution."""
    from app.routers.business_rules import fire_event  # deferred import — avoids a circular import with business_rules importing from here indirectly via patients/results

    notifications_created = 0
    overdue_events_fired = 0

    # --- Tasks approaching (or past) their due date ---
    cutoff = date.today() + timedelta(days=TASK_DUE_SOON_WINDOW_DAYS)
    due_soon_tasks = (
        db.query(Task)
        .filter(Task.status != "completed", Task.due_date.isnot(None), Task.due_date <= cutoff, Task.assigned_to_id.isnot(None))
        .all()
    )
    for task in due_soon_tasks:
        already_notified = db.query(Notification).filter_by(
            type="task_due_soon", related_entity_id=str(task.id), recipient_staff_id=task.assigned_to_id,
        ).first()
        if not already_notified:
            assignee = db.query(Staff).filter_by(id=task.assigned_to_id).first()
            if assignee:
                patient = db.query(Patient).filter_by(id=task.patient_id).first()
                overdue = task.due_date < date.today()
                create_notification(
                    db, assignee,
                    "task_due_soon",
                    f"Task {'overdue' if overdue else 'due soon'}: {task.title}",
                    f"\"{task.title}\" for {patient.name if patient else 'a patient'} was due {task.due_date}.",
                    related_patient_id=str(task.patient_id), related_entity_id=str(task.id),
                )
                notifications_created += 1

    # --- Mandatory assessments past their scheduled date with no completed result ---
    overdue_assigned = (
        db.query(AssignedAssessment)
        .filter(AssignedAssessment.mandatory.is_(True), AssignedAssessment.scheduled_date.isnot(None), AssignedAssessment.scheduled_date < date.today())
        .all()
    )
    for assigned in overdue_assigned:
        has_result = db.query(AssessmentResult).filter_by(
            case_id=assigned.case_id, assessment_definition_id=assigned.assessment_definition_id,
        ).first()
        if has_result:
            continue

        case = db.query(Case).filter_by(id=assigned.case_id).first()
        if not case or not case.patient_id:
            continue
        care_team = db.query(PatientStaffAssignment).filter_by(patient_id=case.patient_id).all()
        if not care_team:
            continue

        definition = db.query(AssessmentDefinition).filter_by(id=assigned.assessment_definition_id).first()
        patient = db.query(Patient).filter_by(id=case.patient_id).first()

        for assignment in care_team:
            already_notified = db.query(Notification).filter_by(
                type="assessment_overdue", related_entity_id=str(assigned.id), recipient_staff_id=assignment.staff_id,
            ).first()
            if already_notified:
                continue
            create_notification(
                db, assignment.staff,
                "assessment_overdue",
                f"Overdue: {definition.title if definition else 'assessment'} for {patient.name if patient else 'a patient'}",
                f"A mandatory assessment scheduled for {assigned.scheduled_date} has not been completed.",
                related_patient_id=str(case.patient_id), related_entity_id=str(assigned.id),
            )
            notifications_created += 1

    # --- task.overdue: fires the real rules-engine event, once ever per task ---
    newly_overdue_tasks = (
        db.query(Task)
        .filter(Task.status != "completed", Task.due_date.isnot(None), Task.due_date < date.today(), Task.overdue_event_fired_at.is_(None))
        .all()
    )
    for task in newly_overdue_tasks:
        patient = db.query(Patient).filter_by(id=task.patient_id).first()
        if not patient:
            continue
        overdue_days = (date.today() - task.due_date).days
        fire_event(
            db, "task.overdue",
            {"task_id": str(task.id), "task_title": task.title, "overdue_days": overdue_days},
            patient, staff=None, dry_run=False,
        )
        task.overdue_event_fired_at = utcnow()
        db.commit()
        overdue_events_fired += 1

    return {"notifications_created": notifications_created, "overdue_events_fired": overdue_events_fired}
