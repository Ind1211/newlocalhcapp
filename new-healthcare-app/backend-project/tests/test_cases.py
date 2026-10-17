"""
Case context updates — PATCH /api/cases/{id}/context REPLACES the whole context
dict rather than merging it. This was verified by hand during manual testing
(a naive partial update silently wiped out previously-stored fields like
weight/bloodType), and the frontend's Patient Health Details screen was built
specifically around always sending the full, merged dict for exactly this
reason. This test is what makes sure that underlying behavior can't quietly
change to a merge later without a very deliberate, visible test failure.
"""

from app.models import Case, Patient


def test_context_update_replaces_rather_than_merges(client, staff_factory, auth_headers, db):
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)

    patient = Patient(name="Context Test Patient", mrn="CTX-001")
    db.add(patient)
    db.commit()

    case_resp = client.get(f"/api/patients/{patient.id}/case", headers=headers)
    case_id = case_resp.json()["id"]

    client.patch(f"/api/cases/{case_id}/context", json={"context": {"weight": "78kg", "bloodType": "O+"}}, headers=headers)

    # A caller sending only ONE field, as a naive "just add this one thing"
    # implementation might — this should NOT preserve weight/bloodType.
    client.patch(f"/api/cases/{case_id}/context", json={"context": {"height": "180cm"}}, headers=headers)

    final = client.get(f"/api/patients/{patient.id}/case", headers=headers).json()
    assert final["context"] == {"height": "180cm"}
    assert "weight" not in final["context"]
    assert "bloodType" not in final["context"]


def test_context_update_with_full_merged_dict_preserves_everything(client, staff_factory, auth_headers, db):
    """The correct usage pattern — confirms that sending the complete,
    current-plus-changed dict (what the real frontend does) genuinely does
    preserve every field, since the previous test only proves the failure mode
    exists, not that the correct workaround actually works."""
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)

    patient = Patient(name="Context Test Patient 2", mrn="CTX-002")
    db.add(patient)
    db.commit()

    case_id = client.get(f"/api/patients/{patient.id}/case", headers=headers).json()["id"]
    client.patch(f"/api/cases/{case_id}/context", json={"context": {"weight": "78kg"}}, headers=headers)

    current = client.get(f"/api/patients/{patient.id}/case", headers=headers).json()["context"]
    client.patch(f"/api/cases/{case_id}/context", json={"context": {**current, "height": "180cm"}}, headers=headers)

    final = client.get(f"/api/patients/{patient.id}/case", headers=headers).json()
    assert final["context"] == {"weight": "78kg", "height": "180cm"}


def test_completing_an_assessment_extracts_shared_fields_into_context(client, staff_factory, auth_headers, db):
    """The real fix for the reported gap — Patient Health Details claimed to
    auto-populate from completed assessments, but until now nothing actually
    did that for any assessment. This checks the exact registered fields
    (age, sex, egfr) genuinely get promoted, using ckd_staging's real
    egfrValue field name — one of the two verified aliases for the same
    eGFR concept, discovered by testing against the real field name rather
    than assuming a single canonical name existed."""
    from app.models import AssessmentDefinition
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)

    definition = AssessmentDefinition(key="ckd_staging", title="CKD Staging (KDIGO)", category="kidney", kind="calculator", is_builtin=True)
    db.add(definition)
    db.commit()

    create_resp = client.post("/api/patients", json={"name": "Extraction Test Patient", "dob": "1960-01-01"}, headers=headers)
    patient_id = create_resp.json()["id"]
    case_id = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["id"]

    client.post(
        f"/api/cases/{case_id}/results", headers=headers,
        json={"assessment_definition_key": "ckd_staging", "answers": {"age": 65, "sex": "male", "egfrValue": 42, "age65": True}},
    )

    context = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["context"]
    assert context["Age"] == 65
    assert context["Sex"] == "male"
    assert context["eGFR"] == 42
    # age65 is a real, different field (a threshold checkbox on other
    # assessments) — it must NOT be captured just because it contains "age".
    assert "age65" not in context
    assert "Age65" not in context


def test_extraction_merges_rather_than_replaces_existing_context(client, staff_factory, auth_headers, db):
    """The property this whole feature depends on being genuinely true —
    completing one assessment must never silently erase a manually-entered
    field or a value extracted from an earlier, different assessment."""
    from app.models import AssessmentDefinition
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)

    ckd_def = AssessmentDefinition(key="ckd_staging", title="CKD Staging", category="kidney", kind="calculator", is_builtin=True)
    kfre_def = AssessmentDefinition(key="kfre", title="KFRE", category="kidney", kind="calculator", is_builtin=True)
    db.add_all([ckd_def, kfre_def])
    db.commit()

    create_resp = client.post("/api/patients", json={"name": "Merge Test Patient", "dob": "1965-01-01"}, headers=headers)
    patient_id = create_resp.json()["id"]
    case_id = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["id"]

    client.patch(f"/api/cases/{case_id}/context", json={"context": {"Notes": "manually entered"}}, headers=headers)
    client.post(f"/api/cases/{case_id}/results", headers=headers, json={"assessment_definition_key": "ckd_staging", "answers": {"age": 65, "egfrValue": 42}})
    client.post(f"/api/cases/{case_id}/results", headers=headers, json={"assessment_definition_key": "kfre", "answers": {"age": 70, "egfr": 38}})

    context = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["context"]
    assert context["Notes"] == "manually entered"  # survived two assessment completions
    assert context["Age"] == 70  # updated by the later assessment, not duplicated
    assert context["eGFR"] == 38


def test_assessment_with_no_shared_fields_does_not_error_or_alter_context(client, staff_factory, auth_headers, db):
    from app.models import AssessmentDefinition
    staff, token = staff_factory("nurse")
    headers = auth_headers(token)

    definition = AssessmentDefinition(key="nyha", title="NYHA Functional Classification", category="cardiology", kind="calculator", is_builtin=True)
    db.add(definition)
    db.commit()

    create_resp = client.post("/api/patients", json={"name": "No Shared Fields Patient", "dob": "1970-01-01"}, headers=headers)
    patient_id = create_resp.json()["id"]
    case_id = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["id"]

    client.patch(f"/api/cases/{case_id}/context", json={"context": {"Notes": "unchanged"}}, headers=headers)
    resp = client.post(f"/api/cases/{case_id}/results", headers=headers, json={"assessment_definition_key": "nyha", "answers": {"cls": "2"}})
    assert resp.status_code == 201

    context = client.get(f"/api/patients/{patient_id}/case", headers=headers).json()["context"]
    assert context == {"Notes": "unchanged"}
