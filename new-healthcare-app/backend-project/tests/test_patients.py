"""
Patient validation, pagination, sorting, filtering, and optimistic locking.
Several of these port scenarios that were originally caught as REAL bugs during
manual testing (the open_tasks SQL-level sort in particular needed a real
subquery, not a naive Python sort after pagination) — this suite exists so
those specific regressions can never silently come back.
"""


def _create_patient(client, headers, name, dob=None, **extra):
    payload = {"name": name}
    if dob:
        payload["dob"] = dob
    payload.update(extra)
    return client.post("/api/patients", headers=headers, json=payload)


def test_future_dob_is_rejected(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    resp = _create_patient(client, auth_headers(token), "Future Baby", dob="2099-01-01")
    assert resp.status_code == 400
    assert "future" in resp.json()["detail"].lower()


def test_implausibly_old_dob_is_rejected(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    resp = _create_patient(client, auth_headers(token), "Ancient Person", dob="1800-01-01")
    assert resp.status_code == 400
    assert "130 years" in resp.json()["detail"]


def test_valid_dob_is_accepted(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    resp = _create_patient(client, auth_headers(token), "Valid Patient", dob="1980-05-15")
    assert resp.status_code == 201


def test_duplicate_name_and_dob_is_rejected(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    first = _create_patient(client, headers, "Duplicate Test", dob="1970-01-01")
    assert first.status_code == 201
    second = _create_patient(client, headers, "Duplicate Test", dob="1970-01-01")
    assert second.status_code == 409
    assert first.json()["mrn"] in second.json()["detail"]


def test_pagination_math_is_correct(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    for i in range(7):
        _create_patient(client, headers, f"Patient {i}", dob="1970-01-01" if i == 0 else None)

    resp = client.get("/api/patients?page=1&page_size=3", headers=headers)
    data = resp.json()
    assert len(data["items"]) == 3
    assert data["total"] == 7
    assert data["total_pages"] == 3

    resp_page2 = client.get("/api/patients?page=2&page_size=3", headers=headers)
    assert len(resp_page2.json()["items"]) == 3
    # Different items on different pages, not the same 3 repeated
    assert {p["name"] for p in resp_page2.json()["items"]} != {p["name"] for p in data["items"]}


def test_sort_by_name_ascending(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    for name in ["Charlie", "Alice", "Bob"]:
        _create_patient(client, headers, name)

    resp = client.get("/api/patients?sort_by=name&sort_order=asc", headers=headers)
    names = [p["name"] for p in resp.json()["items"]]
    assert names == sorted(names)


def test_sort_by_open_tasks_uses_real_counts_not_a_naive_post_pagination_sort(client, staff_factory, auth_headers):
    """This is the one that actually broke during manual testing — open task
    count is a computed aggregate, not a real column, so sorting by it has to
    happen via a real SQL subquery BEFORE pagination, not a Python sort after."""
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    p1 = _create_patient(client, headers, "Has Two Tasks").json()
    p2 = _create_patient(client, headers, "Has Zero Tasks").json()

    for i in range(2):
        client.post(f"/api/patients/{p1['id']}/tasks", headers=headers, json={"title": f"Task {i}"})

    resp = client.get("/api/patients?sort_by=open_tasks&sort_order=desc", headers=headers)
    items = resp.json()["items"]
    assert items[0]["name"] == "Has Two Tasks"
    assert items[0]["open_tasks_count"] == 2
    assert items[-1]["open_tasks_count"] == 0


def test_filter_by_program_status(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    p1 = _create_patient(client, headers, "Completed Program Patient").json()
    _create_patient(client, headers, "Active Program Patient")

    client.post(f"/api/patients/{p1['id']}/complete-program", headers=headers)

    resp = client.get("/api/patients?program_status=completed", headers=headers)
    names = [p["name"] for p in resp.json()["items"]]
    assert names == ["Completed Program Patient"]


def test_deactivated_patient_hidden_by_default_but_findable_with_flag(client, staff_factory, auth_headers):
    _, token = staff_factory("care_manager")
    headers = auth_headers(token)
    patient = _create_patient(client, headers, "Will Be Deactivated").json()

    client.post(f"/api/patients/{patient['id']}/deactivate", headers=headers, json={})

    default_resp = client.get("/api/patients?search=Will Be Deactivated", headers=headers)
    assert len(default_resp.json()["items"]) == 0

    inactive_resp = client.get("/api/patients?search=Will Be Deactivated&include_inactive=true", headers=headers)
    assert len(inactive_resp.json()["items"]) == 1


def test_optimistic_lock_rejects_a_stale_version_token(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    patient = _create_patient(client, headers, "Lock Test Patient").json()
    stale_updated_at = patient["updated_at"]

    # A first, real edit — this bumps updated_at
    first_edit = client.patch(
        f"/api/patients/{patient['id']}", headers=headers,
        json={"payor_name": "Aetna", "expected_updated_at": stale_updated_at},
    )
    assert first_edit.status_code == 200

    # A second edit using the NOW-STALE token from before the first edit
    second_edit = client.patch(
        f"/api/patients/{patient['id']}", headers=headers,
        json={"payor_name": "Cigna", "expected_updated_at": stale_updated_at},
    )
    assert second_edit.status_code == 409


def test_optimistic_lock_is_opt_in_not_required(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    patient = _create_patient(client, headers, "No Lock Test Patient").json()

    resp = client.patch(f"/api/patients/{patient['id']}", headers=headers, json={"payor_name": "Blue Cross"})
    assert resp.status_code == 200


def test_editing_clinical_programs_replaces_not_merges(client, staff_factory, auth_headers, db):
    """The one place in the app a clinical program can genuinely be removed —
    unlike intake completion (additive-only) or bulk import."""
    from app.models import Program

    if not db.query(Program).filter_by(key="kidney").first():
        db.add(Program(key="kidney", label="Kidney", icon="🫘"))
    if not db.query(Program).filter_by(key="cardiology").first():
        db.add(Program(key="cardiology", label="Cardiology", icon="❤️"))
    db.commit()

    _, token = staff_factory("admin")
    headers = auth_headers(token)
    patient = _create_patient(
        client, headers, "Program Test Patient", clinical_program_keys=["kidney", "cardiology"],
    ).json()
    assert {p["key"] for p in patient["clinical_programs"]} == {"kidney", "cardiology"}

    resp = client.patch(
        f"/api/patients/{patient['id']}", headers=headers, json={"clinical_program_keys": ["kidney"]},
    )
    assert {p["key"] for p in resp.json()["clinical_programs"]} == {"kidney"}


def test_patient_can_be_created_with_contact_info(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    resp = _create_patient(
        client, auth_headers(token), "Contact Info Patient",
        phone_number="555-0100", email="patient@example.com", address_line1="123 Main St",
        city="Springfield", state="IL", zip_code="62701",
        preferred_contact_method="phone", preferred_language="Spanish",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["phone_number"] == "555-0100"
    assert body["email"] == "patient@example.com"
    assert body["city"] == "Springfield"
    assert body["preferred_language"] == "Spanish"


def test_invalid_risk_level_is_rejected(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    resp = _create_patient(client, auth_headers(token), "Bad Risk Patient", risk_level="super-urgent")
    assert resp.status_code == 400
    assert "risk_level" in resp.json()["detail"]


def test_valid_risk_level_is_accepted_and_editable(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    patient = _create_patient(client, headers, "Risk Level Patient", risk_level="low").json()
    assert patient["risk_level"] == "low"

    resp = client.patch(f"/api/patients/{patient['id']}", headers=headers, json={"risk_level": "critical"})
    assert resp.json()["risk_level"] == "critical"


def test_filtering_patients_by_risk_level(client, staff_factory, auth_headers):
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    _create_patient(client, headers, "Low Risk Patient", risk_level="low")
    _create_patient(client, headers, "Critical Risk Patient", risk_level="critical")

    resp = client.get("/api/patients?risk_level=critical", headers=headers)
    names = [p["name"] for p in resp.json()["items"]]
    assert "Critical Risk Patient" in names
    assert "Low Risk Patient" not in names


def test_sorting_patients_by_risk_level_uses_real_severity_order_not_alphabetical(client, staff_factory, auth_headers):
    """The one that actually broke — case() (SQLAlchemy's, for a real severity
    rank) collided with the 'case' local variable this same list_patients
    function already uses everywhere for Case model instances, since Python
    scopes a name as local to the WHOLE function the moment it's assigned
    anywhere inside it, regardless of line order. This test exists specifically
    so that regression can't silently return: alphabetically, 'critical' sorts
    before 'high' sorts before 'low' — nothing about that order is clinically
    meaningful, so this checks the REAL severity order explicitly, not just
    that the endpoint doesn't crash."""
    _, token = staff_factory("admin")
    headers = auth_headers(token)
    _create_patient(client, headers, "Zzz Low Risk", risk_level="low")
    _create_patient(client, headers, "Aaa Critical Risk", risk_level="critical")
    _create_patient(client, headers, "Mmm Medium Risk", risk_level="medium")
    _create_patient(client, headers, "Bbb High Risk", risk_level="high")

    resp = client.get("/api/patients?sort_by=risk_level&sort_order=desc&page_size=10", headers=headers)
    names_in_order = [p["name"] for p in resp.json()["items"]]

    # Real severity order (critical first) — alphabetical descending would put
    # "Zzz Low Risk" first instead, which is exactly the bug this protects against.
    assert names_in_order.index("Aaa Critical Risk") < names_in_order.index("Bbb High Risk")
    assert names_in_order.index("Bbb High Risk") < names_in_order.index("Mmm Medium Risk")
    assert names_in_order.index("Mmm Medium Risk") < names_in_order.index("Zzz Low Risk")


def test_logging_contact_sets_last_contact_date(client, staff_factory, auth_headers):
    _, token = staff_factory("nurse")
    headers = auth_headers(token)
    patient = _create_patient(client, headers, "Log Contact Patient").json()
    assert patient["last_contact_date"] is None

    resp = client.post(f"/api/patients/{patient['id']}/log-contact", headers=headers, json={})
    assert resp.status_code == 200
    assert resp.json()["last_contact_date"] is not None
