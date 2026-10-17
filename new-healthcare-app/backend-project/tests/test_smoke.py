def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_staff_factory_creates_real_staff_and_valid_token(client, staff_factory, auth_headers):
    staff, token = staff_factory("admin", name="Test Admin")
    resp = client.get("/api/staff/me", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Admin"
    assert resp.json()["role"] == "admin"


def test_db_fixture_isolates_between_tests(client, staff_factory, auth_headers):
    """If this ever sees staff from a previous test, the truncation in the db
    fixture is broken — this is the test that would catch that regression."""
    resp = client.get("/api/staff", headers=auth_headers(staff_factory("admin")[1]))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
