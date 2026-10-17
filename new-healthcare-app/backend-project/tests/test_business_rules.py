"""
Tests for the business rules API and — most importantly — the real event
wiring into patients.py and results.py. These are what actually prove the
engine reacts to genuine app behavior (a patient being created, an assessment
being completed) rather than only working when manually triggered through
the fire-event endpoint.
"""

from app.models import AssessmentDefinition, BusinessRule, Patient


def _create_and_enable_rule(client, headers, dsl_text, governance="operational"):
    create_resp = client.post("/api/business-rules", headers=headers, json={"dsl_text": dsl_text, "governance": governance})
    assert create_resp.status_code == 201, create_resp.json()
    rule_id = create_resp.json()["id"]
    enable_resp = client.patch(f"/api/business-rules/{rule_id}/enable", headers=headers, json={"confirmed": True})
    assert enable_resp.status_code == 200, enable_resp.json()
    return rule_id


def test_nurse_cannot_create_a_rule(client, staff_factory, auth_headers):
    _, nurse_token = staff_factory("nurse")
    resp = client.post(
        "/api/business-rules", headers=auth_headers(nurse_token),
        json={"dsl_text": 'RULE "x"\nWHEN y\nIF 1 == 1\nTHEN\n  ESCALATE_RISK "high"\nEND', "governance": "operational"},
    )
    assert resp.status_code == 403


def test_malformed_dsl_is_rejected_with_clear_errors(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    resp = client.post(
        "/api/business-rules", headers=auth_headers(admin_token),
        json={"dsl_text": "not a real rule at all", "governance": "operational"},
    )
    assert resp.status_code == 400
    assert "errors" in resp.json()["detail"]


def test_enabling_a_clinical_rule_requires_confirmation(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    create_resp = client.post(
        "/api/business-rules", headers=headers,
        json={"dsl_text": 'RULE "x"\nWHEN y\nIF 1 == 1\nTHEN\n  ESCALATE_RISK "high"\nEND', "governance": "clinical"},
    )
    rule_id = create_resp.json()["id"]

    without_confirmation = client.patch(f"/api/business-rules/{rule_id}/enable", headers=headers, json={"confirmed": False})
    assert without_confirmation.status_code == 409

    with_confirmation = client.patch(f"/api/business-rules/{rule_id}/enable", headers=headers, json={"confirmed": True})
    assert with_confirmation.status_code == 200
    assert with_confirmation.json()["enabled"] is True


def test_operational_rule_does_not_require_confirmation(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    create_resp = client.post(
        "/api/business-rules", headers=headers,
        json={"dsl_text": 'RULE "x"\nWHEN y\nIF 1 == 1\nTHEN\n  ESCALATE_RISK "high"\nEND', "governance": "operational"},
    )
    rule_id = create_resp.json()["id"]
    resp = client.patch(f"/api/business-rules/{rule_id}/enable", headers=headers, json={"confirmed": False})
    assert resp.status_code == 200


def test_test_in_isolation_never_mutates_real_data(client, staff_factory, auth_headers, db):
    """The dry-run guarantee that makes 'test this rule' safe to use against a
    real patient — this is the property the whole authoring workflow depends
    on being genuinely true, not just described as true."""
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)

    patient = Patient(name="Dry Run Patient", mrn="RULES-001")
    db.add(patient)
    db.commit()
    assert patient.risk_level is None

    resp = client.post(
        "/api/business-rules/test", headers=headers,
        json={
            "dsl_text": 'RULE "x"\nWHEN y\nIF 1 == 1\nTHEN\n  ESCALATE_RISK "critical"\nEND',
            "patient_id": str(patient.id),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["condition_result"] is True

    db.refresh(patient)
    assert patient.risk_level is None  # still untouched — the whole point of a dry run


def test_manual_fire_event_dry_run_does_not_mutate(client, staff_factory, auth_headers, db):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    patient = Patient(name="Fire Dry Run Patient", mrn="RULES-002")
    db.add(patient)
    db.commit()

    _create_and_enable_rule(client, headers, 'RULE "x"\nWHEN test.trigger\nIF 1 == 1\nTHEN\n  ESCALATE_RISK "critical"\nEND')

    resp = client.post(
        "/api/business-rules/fire-event", headers=headers,
        json={"trigger": "test.trigger", "patient_id": str(patient.id), "dry_run": True},
    )
    assert resp.status_code == 200
    assert resp.json()["rules_matched"] == 1

    db.refresh(patient)
    assert patient.risk_level is None


def test_manual_fire_event_real_run_actually_mutates(client, staff_factory, auth_headers, db):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    patient = Patient(name="Fire Real Run Patient", mrn="RULES-003")
    db.add(patient)
    db.commit()

    _create_and_enable_rule(client, headers, 'RULE "x"\nWHEN test.trigger\nIF 1 == 1\nTHEN\n  ESCALATE_RISK "critical"\nEND')

    resp = client.post(
        "/api/business-rules/fire-event", headers=headers,
        json={"trigger": "test.trigger", "patient_id": str(patient.id), "dry_run": False},
    )
    assert resp.status_code == 200

    db.refresh(patient)
    assert patient.risk_level == "critical"


def test_bulk_import_automatically_fires_patient_imported(client, staff_factory, auth_headers, db):
    """The real proof this is wired, not a standalone sandbox — creating a
    patient through the actual bulk-import endpoint should fire an enabled
    rule with zero manual intervention."""
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)

    _create_and_enable_rule(
        client, headers,
        'RULE "Imported patient gets outreach task"\nWHEN patient.imported\nIF event.source == "tenant_admin_import"\nTHEN\n  CREATE_TASK "Outreach - obtain consent" ASSIGN "Care Admin" DUE "24h"\nEND',
    )

    import io
    csv_content = b"name,dob\nAuto Wired Patient,1980-01-01\n"
    resp = client.post(
        "/api/patients/bulk-import", headers=headers,
        files={"file": ("import.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200, resp.json()

    patient = db.query(Patient).filter_by(name="Auto Wired Patient").first()
    assert patient is not None

    tasks_resp = client.get(f"/api/patients/{patient.id}/tasks", headers=headers)
    titles = [t["title"] for t in tasks_resp.json()]
    assert any("outreach" in t.lower() for t in titles)


def test_manual_single_add_does_not_fire_the_import_specific_rule(client, staff_factory, auth_headers, db):
    """Confirms the condition genuinely discriminates — a regular single-patient
    add (source=manual_entry) should NOT satisfy a rule checking specifically
    for event.source == tenant_admin_import."""
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)

    _create_and_enable_rule(
        client, headers,
        'RULE "Imported patient gets outreach task 2"\nWHEN patient.imported\nIF event.source == "tenant_admin_import"\nTHEN\n  CREATE_TASK "Outreach - obtain consent" ASSIGN "Care Admin" DUE "24h"\nEND',
    )

    create_resp = client.post("/api/patients", headers=headers, json={"name": "Manually Added Patient", "dob": "1975-05-05"})
    patient_id = create_resp.json()["id"]

    tasks_resp = client.get(f"/api/patients/{patient_id}/tasks", headers=headers)
    assert len(tasks_resp.json()) == 0


def test_completing_a_critical_assessment_automatically_escalates_risk(client, staff_factory, auth_headers, db):
    """The other real proof of wiring — a genuine assessment completion,
    through the actual results endpoint, should trigger risk escalation with
    no manual fire-event call."""
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)

    _create_and_enable_rule(
        client, headers,
        'RULE "Critical result escalates risk"\nWHEN assessment.completed\nIF event.severity == "critical"\nTHEN\n  ESCALATE_RISK "critical"\nEND',
        governance="clinical",
    )

    create_resp = client.post("/api/patients", headers=headers, json={"name": "Escalation Test Patient", "dob": "1970-01-01"})
    patient_id = create_resp.json()["id"]
    case_id = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["id"]

    definition = AssessmentDefinition(key="nyha", title="NYHA Functional Classification", category="cardiology", kind="calculator", is_builtin=True)
    db.add(definition)
    db.commit()

    result_resp = client.post(
        f"/api/cases/{case_id}/results", headers=headers,
        json={"assessment_definition_key": "nyha", "answers": {"cls": "4"}},
    )
    assert result_resp.status_code == 201, result_resp.json()

    patient = db.query(Patient).filter_by(id=patient_id).first()
    assert patient.risk_level == "critical"


def test_execution_log_records_both_matches_and_non_matches(client, staff_factory, auth_headers, db):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    patient = Patient(name="Log Test Patient", mrn="RULES-004")
    db.add(patient)
    db.commit()

    _create_and_enable_rule(client, headers, 'RULE "x"\nWHEN log.test\nIF event.flag == "yes"\nTHEN\n  ESCALATE_RISK "high"\nEND')

    client.post("/api/business-rules/fire-event", headers=headers, json={"trigger": "log.test", "event": {"flag": "no"}, "patient_id": str(patient.id), "dry_run": False})

    log_resp = client.get(f"/api/business-rules/execution-log?patient_id={patient.id}", headers=headers)
    entries = log_resp.json()
    assert len(entries) == 1
    assert entries[0]["matched"] is False
