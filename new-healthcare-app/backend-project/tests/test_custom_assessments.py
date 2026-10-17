"""
Deletion safety for custom assessments — a real bug found by reproducing a
user's report: deleting a custom assessment that had been assigned to a
patient (but never completed) crashed with an unhandled foreign key
violation (500), since AssignedAssessment rows weren't cleaned up before
deleting the definition. Fixed to distinguish two very different
situations: a merely scheduled/assigned assessment is safe to remove
(no real answer exists yet), while a genuinely completed result is real
clinical data and must still block deletion — with a clear error, not a
crash.
"""


def _create_custom(client, headers, title="Test Custom"):
    resp = client.post(
        "/api/assessments/custom", headers=headers,
        json={
            "title": title, "blurb": "test",
            "sections": [{"title": "S1", "fields": [{"name": "q1", "label": "Q1", "type": "text"}]}],
            "interpretation_prompt": "test prompt", "created_by": "admin@test.com",
        },
    )
    assert resp.status_code == 201
    return resp.json()["key"]


def _create_patient(client, headers, name):
    resp = client.post("/api/patients", headers=headers, json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_deleting_an_assigned_but_uncompleted_custom_assessment_succeeds(client, staff_factory, auth_headers):
    """The exact scenario that used to crash with a 500 — reproduced and
    fixed."""
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    key = _create_custom(client, headers, title="Assigned Only")
    patient_id = _create_patient(client, headers, "Assigned Only Patient")

    assign_resp = client.post(
        f"/api/patients/{patient_id}/assign-assessment", headers=headers,
        json={"assessment_definition_key": key, "source": "custom"},
    )
    assert assign_resp.status_code == 201

    delete_resp = client.delete(f"/api/assessments/custom/{key}", headers=headers)
    assert delete_resp.status_code == 204


def test_deleting_a_custom_assessment_with_a_completed_result_is_refused_cleanly(client, staff_factory, auth_headers, db):
    """Must return a clear 409, not crash with an unhandled database
    exception — and must NOT delete anything."""
    from app.models import AssessmentDefinition, AssessmentResult, Case

    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    key = _create_custom(client, headers, title="Has Real Result")
    patient_id = _create_patient(client, headers, "Has Real Result Patient")

    case = db.query(Case).filter_by(patient_id=patient_id).first()
    definition = db.query(AssessmentDefinition).filter_by(key=key).first()
    db.add(AssessmentResult(
        case_id=case.id, assessment_definition_id=definition.id, version_used=1,
        answers={"q1": "a real answer"},
        result={"headline": "ok", "headlineSeverity": "good", "metrics": [], "flags": [], "notes": ""},
    ))
    db.commit()

    delete_resp = client.delete(f"/api/assessments/custom/{key}", headers=headers)
    assert delete_resp.status_code == 409
    assert "completed result" in delete_resp.json()["detail"]

    still_exists = db.query(AssessmentDefinition).filter_by(key=key).first()
    assert still_exists is not None


def test_deleting_a_never_used_custom_assessment_succeeds(client, staff_factory, auth_headers):
    """The simple, already-working case — confirms the fix didn't
    regress the baseline path."""
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    key = _create_custom(client, headers, title="Never Used")

    delete_resp = client.delete(f"/api/assessments/custom/{key}", headers=headers)
    assert delete_resp.status_code == 204
