"""
Notification creation and the check-due scan's idempotency — the single most
important guarantee for that endpoint, since it's meant to be called repeatedly
(on every app load) and must never double-notify anyone for the same event.
"""

from datetime import date, timedelta
from unittest.mock import patch

from app.email_service import EmailError
from app.notifications import create_notification


def test_email_success_records_both_notification_and_email_sent(db, staff_factory):
    staff, _ = staff_factory("nurse", email="real@example.com")
    with patch("app.notifications.send_email") as mock_send:
        notification = create_notification(db, staff, "task_assigned", "Title", "Body")
    assert notification.id is not None
    assert notification.email_sent is True
    assert mock_send.called


def test_email_failure_still_creates_notification_but_marks_email_unsent(db, staff_factory):
    """The in-app notification is the durable, real thing — an email hiccup
    should never cause the whole action to fail or the notification to be lost."""
    staff, _ = staff_factory("nurse", email="real@example.com")
    with patch("app.notifications.send_email", side_effect=EmailError("SMTP down")):
        notification = create_notification(db, staff, "task_assigned", "Title", "Body")
    assert notification.id is not None
    assert notification.email_sent is False


def test_staff_with_no_email_skips_email_attempt_gracefully(db, staff_factory):
    staff, _ = staff_factory("nurse", email=None)
    with patch("app.notifications.send_email") as mock_send:
        notification = create_notification(db, staff, "task_assigned", "Title", "Body")
    assert notification.id is not None
    assert not mock_send.called
    assert notification.email_sent is False


def test_check_due_is_idempotent_for_the_same_overdue_task(client, staff_factory, auth_headers, db):
    """The single most important guarantee for this endpoint — calling it twice
    in a row for the same overdue task must create exactly one notification,
    not two."""
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="NOTIF-001")
    db.add(patient)
    db.commit()

    nurse, nurse_token = staff_factory("nurse")
    admin, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)

    overdue_date = (date.today() - timedelta(days=5)).isoformat()
    client.post(
        f"/api/patients/{patient.id}/tasks", headers=headers,
        json={"title": "Overdue task", "assigned_to_id": str(nurse.id), "due_date": overdue_date},
    )

    first = client.post("/api/notifications/check-due", headers=headers)
    assert first.json()["notifications_created"] >= 1

    second = client.post("/api/notifications/check-due", headers=headers)
    assert second.json()["notifications_created"] == 0

    notifications = client.get("/api/notifications", headers=auth_headers(nurse_token)).json()
    due_soon = [n for n in notifications if n["type"] == "task_due_soon"]
    assert len(due_soon) == 1


def test_task_assignment_notifies_assignee_not_assigner(client, staff_factory, auth_headers, db):
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="NOTIF-002")
    db.add(patient)
    db.commit()

    assigner, assigner_token = staff_factory("care_manager", name="Assigner")
    assignee, assignee_token = staff_factory("nurse", name="Assignee")

    client.post(
        f"/api/patients/{patient.id}/tasks", headers=auth_headers(assigner_token),
        json={"title": "New task", "assigned_to_id": str(assignee.id)},
    )

    assignee_notifications = client.get("/api/notifications", headers=auth_headers(assignee_token)).json()
    assert len(assignee_notifications) == 1
    assert assignee_notifications[0]["type"] == "task_assigned"

    assigner_notifications = client.get("/api/notifications", headers=auth_headers(assigner_token)).json()
    assert len(assigner_notifications) == 0


def test_self_assignment_does_not_notify(client, staff_factory, auth_headers, db):
    """Assigning a task to yourself isn't 'someone telling you about a new
    task' — it's just you creating your own reminder, so no notification
    should be created at all."""
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="NOTIF-003")
    db.add(patient)
    db.commit()

    staff, token = staff_factory("nurse")
    client.post(
        f"/api/patients/{patient.id}/tasks", headers=auth_headers(token),
        json={"title": "Self task", "assigned_to_id": str(staff.id)},
    )

    notifications = client.get("/api/notifications", headers=auth_headers(token)).json()
    assert len(notifications) == 0


def test_task_overdue_fires_exactly_once_across_repeated_checks(client, staff_factory, auth_headers, db):
    """The same idempotency guarantee as task_due_soon notifications, but for
    a genuinely different mechanism — task.overdue is a real rules-engine
    event, not a notification, so it needs its own guard
    (Task.overdue_event_fired_at) rather than reusing the notification
    dedup check. Calling check-due repeatedly for the same overdue task must
    fire the rules-engine event exactly once, ever."""
    from app.models import BusinessRule, Patient, RuleExecutionLog, Task
    from app.rules_engine import parse_rule

    patient = Patient(name="Overdue Rule Test Patient", mrn="NOTIF-OVERDUE-1")
    db.add(patient)
    db.commit()

    nurse, _ = staff_factory("nurse")
    admin, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)

    dsl = '''RULE "Test Overdue Fires Once"
WHEN task.overdue
IF 1 == 1
THEN
  CREATE_TASK "Escalation from overdue rule" ASSIGN "Care Admin" DUE "24h"
END'''
    parsed = parse_rule(dsl)
    rule = BusinessRule(
        name=parsed.name, trigger=parsed.trigger, dsl_text=dsl,
        condition_tree=parsed.condition_tree, actions=parsed.actions,
        governance="operational", enabled=True, created_by=admin.name,
    )
    db.add(rule)
    db.commit()

    overdue_date = (date.today() - timedelta(days=5)).isoformat()
    task_resp = client.post(
        f"/api/patients/{patient.id}/tasks", headers=headers,
        json={"title": "Overdue task", "assigned_to_id": str(nurse.id), "due_date": overdue_date},
    )
    task_id = task_resp.json()["id"]

    client.post("/api/notifications/check-due", headers=headers)
    client.post("/api/notifications/check-due", headers=headers)
    client.post("/api/notifications/check-due", headers=headers)

    task = db.query(Task).filter_by(id=task_id).first()
    assert task.overdue_event_fired_at is not None

    logs = db.query(RuleExecutionLog).filter_by(trigger="task.overdue").all()
    assert len(logs) == 1

    created_tasks = db.query(Task).filter_by(title="Escalation from overdue rule").count()
    assert created_tasks == 1


def test_send_notification_to_specific_role_only_notifies_that_role(client, staff_factory, auth_headers, db):
    """The real bug this was meant to fix — TO 'nurse' must notify only
    staff assigned in that specific role on this patient's care team, not
    everyone on it regardless of role."""
    from app.models import BusinessRule, Patient, PatientStaffAssignment
    from app.rules_engine import parse_rule

    patient = Patient(name="Role Targeting Test Patient", mrn="NOTIF-ROLE-1")
    db.add(patient)
    db.commit()

    nurse, nurse_token = staff_factory("admin", name="Role-Test Nurse")
    provider, provider_token = staff_factory("admin", name="Role-Test Provider")
    admin, admin_token = staff_factory("admin", name="Role-Test Admin")

    db.add(PatientStaffAssignment(patient_id=patient.id, staff_id=nurse.id, role_on_patient="nurse"))
    db.add(PatientStaffAssignment(patient_id=patient.id, staff_id=provider.id, role_on_patient="provider"))
    db.commit()

    dsl = '''RULE "Test Role Targeting"
WHEN patient.enrolled
IF 1 == 1
THEN
  SEND_NOTIFICATION "role_test_alert" TO "nurse"
END'''
    parsed = parse_rule(dsl)
    rule = BusinessRule(
        name=parsed.name, trigger=parsed.trigger, dsl_text=dsl,
        condition_tree=parsed.condition_tree, actions=parsed.actions,
        governance="operational", enabled=True, created_by=admin.name,
    )
    db.add(rule)
    db.commit()

    headers = auth_headers(admin_token)
    resp = client.patch(f"/api/patients/{patient.id}", headers=headers, json={"clinical_program_keys": ["kidney"]})
    assert resp.status_code == 200

    nurse_notifs = client.get("/api/notifications", headers=auth_headers(nurse_token)).json()
    provider_notifs = client.get("/api/notifications", headers=auth_headers(provider_token)).json()

    business_rule_nurse_notifs = [n for n in nurse_notifs if n["type"] == "business_rule"]
    business_rule_provider_notifs = [n for n in provider_notifs if n["type"] == "business_rule"]

    assert len(business_rule_nurse_notifs) == 1
    assert len(business_rule_provider_notifs) == 0


def test_send_notification_to_generic_care_team_still_notifies_everyone(client, staff_factory, auth_headers, db):
    """The other half of the same fix — the generic target every
    currently-seeded rule actually uses must keep working exactly as
    before, notifying the whole care team regardless of each person's
    specific role."""
    from app.models import BusinessRule, Patient, PatientStaffAssignment
    from app.rules_engine import parse_rule

    patient = Patient(name="Generic Targeting Test Patient", mrn="NOTIF-ROLE-2")
    db.add(patient)
    db.commit()

    nurse, nurse_token = staff_factory("admin", name="Generic-Test Nurse")
    provider, provider_token = staff_factory("admin", name="Generic-Test Provider")
    admin, admin_token = staff_factory("admin", name="Generic-Test Admin")

    db.add(PatientStaffAssignment(patient_id=patient.id, staff_id=nurse.id, role_on_patient="nurse"))
    db.add(PatientStaffAssignment(patient_id=patient.id, staff_id=provider.id, role_on_patient="provider"))
    db.commit()

    dsl = '''RULE "Test Generic Targeting"
WHEN patient.enrolled
IF 1 == 1
THEN
  SEND_NOTIFICATION "generic_test_alert" TO "assigned_care_team"
END'''
    parsed = parse_rule(dsl)
    rule = BusinessRule(
        name=parsed.name, trigger=parsed.trigger, dsl_text=dsl,
        condition_tree=parsed.condition_tree, actions=parsed.actions,
        governance="operational", enabled=True, created_by=admin.name,
    )
    db.add(rule)
    db.commit()

    headers = auth_headers(admin_token)
    client.patch(f"/api/patients/{patient.id}", headers=headers, json={"clinical_program_keys": ["cardiology"]})

    nurse_notifs = [n for n in client.get("/api/notifications", headers=auth_headers(nurse_token)).json() if n["type"] == "business_rule"]
    provider_notifs = [n for n in client.get("/api/notifications", headers=auth_headers(provider_token)).json() if n["type"] == "business_rule"]

    assert len(nurse_notifs) == 1
    assert len(provider_notifs) == 1
