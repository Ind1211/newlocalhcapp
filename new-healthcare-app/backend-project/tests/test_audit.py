"""
The generic AuditLog table and the shared log_audit() helper — deliberately
separate from the older, narrower AuditLogEntry (scoped to
assessment_definition_id only, built for custom assessment versioning
specifically, and unable to represent a patient or task event at all).

test_patient_audit_log_includes_child_entity_events is the one that matters
most here: the patient-scoped audit view is supposed to show everything that
happened to a patient's record AND everything attached to it (tasks, notes,
etc.), not just direct edits to the Patient row — that's a real design
decision, not an accident, and worth protecting explicitly.
"""

from app.audit import log_audit
from app.models import AssessmentDefinition, AuditLog, Patient


def test_log_audit_records_actor_name_and_details(db, staff_factory):
    staff, _ = staff_factory("admin", name="Ana Admin")
    patient = Patient(name="Test Patient", mrn="AUDIT-001")
    db.add(patient)
    db.commit()

    log_audit(db, "patient", str(patient.id), "updated", staff, details={"changed_fields": ["name"]})

    entry = db.query(AuditLog).filter_by(entity_id=str(patient.id)).first()
    assert entry is not None
    assert entry.performed_by == "Ana Admin"
    assert entry.action == "updated"
    assert entry.details == {"changed_fields": ["name"]}


def test_log_audit_with_no_staff_records_system_not_none(db):
    """staff=None is a real, expected case (an unauthenticated context, or a
    background action) — the record should say 'system', not silently omit who
    performed the action or store a bare None that a UI would have to guess how
    to render."""
    patient = Patient(name="System Action Patient", mrn="AUDIT-002")
    db.add(patient)
    db.commit()
    log_audit(db, "patient", str(patient.id), "created", staff=None)
    entry = db.query(AuditLog).filter_by(entity_id=str(patient.id)).first()
    assert entry.performed_by == "system"


def test_patient_audit_log_includes_child_entity_events(client, staff_factory, auth_headers, db):
    """The real, important behavior: a patient's audit log should show tasks
    created/deleted against them too, not just direct edits to the Patient row
    itself — confirmed with a real task lifecycle, not just a direct DB check."""
    staff, token = staff_factory("care_manager")
    headers = auth_headers(token)

    create_resp = client.post("/api/patients", json={"name": "Audit Child Test", "dob": "1980-01-01"}, headers=headers)
    patient_id = create_resp.json()["id"]

    task_resp = client.post(f"/api/patients/{patient_id}/tasks", json={"title": "Check labs"}, headers=headers)
    task_id = task_resp.json()["id"]
    client.delete(f"/api/patients/{patient_id}/tasks/{task_id}", headers=headers)

    log_resp = client.get(f"/api/patients/{patient_id}/audit-log", headers=headers)
    actions = [entry["action"] for entry in log_resp.json()]

    assert "created" in actions  # the patient itself being created
    assert "created" in [e["action"] for e in log_resp.json() if e["entity_type"] == "task"]
    assert "deleted" in [e["action"] for e in log_resp.json() if e["entity_type"] == "task"]


def test_assigning_an_assessment_is_audit_logged(client, staff_factory, auth_headers, db):
    """A real, previously-missing gap: assessment-related events were never
    logged at all, not because of a query bug but because neither endpoint
    ever called log_audit in the first place."""
    staff, token = staff_factory("care_manager")
    headers = auth_headers(token)

    # The test DB starts empty — no app.seed run against it — so a real
    # AssessmentDefinition has to be created directly rather than assuming
    # basic_intake already exists the way it would in a seeded deployment.
    definition = AssessmentDefinition(key="basic_intake", title="Basic Patient Intake", category="intake", kind="calculator", is_builtin=True)
    db.add(definition)
    db.commit()

    create_resp = client.post("/api/patients", json={"name": "Assessment Audit Patient", "dob": "1975-03-01"}, headers=headers)
    patient_id = create_resp.json()["id"]

    assign_resp = client.post(
        f"/api/patients/{patient_id}/assign-assessment",
        json={"assessment_definition_key": "basic_intake", "source": "template"},
        headers=headers,
    )
    assert assign_resp.status_code == 201

    log_resp = client.get(f"/api/patients/{patient_id}/audit-log", headers=headers)
    assigned_entries = [e for e in log_resp.json() if e["entity_type"] == "assigned_assessment"]
    assert len(assigned_entries) == 1
    assert assigned_entries[0]["action"] == "assigned"
    assert assigned_entries[0]["performed_by"] == staff.name


def test_completing_an_assessment_is_audit_logged(client, staff_factory, auth_headers, db):
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)

    definition = AssessmentDefinition(key="basic_intake", title="Basic Patient Intake", category="intake", kind="calculator", is_builtin=True)
    db.add(definition)
    db.commit()

    create_resp = client.post("/api/patients", json={"name": "Completion Audit Patient", "dob": "1968-11-20"}, headers=headers)
    patient_id = create_resp.json()["id"]
    case_id = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["id"]

    result_resp = client.post(
        f"/api/cases/{case_id}/results",
        json={"assessment_definition_key": "basic_intake", "answers": {"age": 70, "sex": "female"}},
        headers=headers,
    )
    assert result_resp.status_code == 201

    log_resp = client.get(f"/api/patients/{patient_id}/audit-log", headers=headers)
    completed_entries = [e for e in log_resp.json() if e["entity_type"] == "assessment_result"]
    assert len(completed_entries) == 1
    assert completed_entries[0]["action"] == "completed"
    assert completed_entries[0]["performed_by"] == staff.name
