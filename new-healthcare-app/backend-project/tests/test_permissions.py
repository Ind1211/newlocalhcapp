"""
Role-based access control — every restriction tested in both directions
(rejected AND allowed), porting the exact scenarios manually verified when
RBAC was first built. A test suite that only checks "nurse gets rejected"
without also checking "admin succeeds" could pass even if the role check were
broken in a way that rejected everyone.
"""

from unittest.mock import patch


def test_nurse_cannot_invite_staff(client, staff_factory, auth_headers):
    _, nurse_token = staff_factory("nurse")
    resp = client.post(
        "/api/staff/invite", headers=auth_headers(nurse_token),
        json={"name": "New Person", "email": "new@example.com", "role": "nurse"},
    )
    assert resp.status_code == 403
    assert "admin" in resp.json()["detail"]


def test_admin_can_invite_staff(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    with patch("app.routers.staff.create_auth0_user", return_value="auth0|newly-created"), \
         patch("app.routers.staff.trigger_password_reset_email"):
        resp = client.post(
            "/api/staff/invite", headers=auth_headers(admin_token),
            json={"name": "New Person", "email": "new@example.com", "role": "nurse"},
        )
    assert resp.status_code == 201
    assert resp.json()["staff"]["name"] == "New Person"
    assert resp.json()["email_sent"] is True


def test_resend_invite_sends_both_password_reset_and_verification_email(client, staff_factory, auth_headers, db):
    from app.models import Staff

    _, admin_token = staff_factory("admin")
    target = Staff(auth0_sub="auth0|resend-target", name="Resend Target", email="resend@example.com", role="nurse")
    db.add(target)
    db.commit()

    with patch("app.routers.staff.trigger_password_reset_email") as mock_reset, \
         patch("app.routers.staff.trigger_verification_email") as mock_verify:
        resp = client.post(f"/api/staff/{target.id}/resend-invite", headers=auth_headers(admin_token))

    assert resp.status_code == 200
    assert resp.json()["email_sent"] is True
    assert resp.json()["verification_email_sent"] is True
    mock_reset.assert_called_once_with("resend@example.com")
    mock_verify.assert_called_once_with("auth0|resend-target")


def test_resend_invite_verification_email_failure_does_not_block_resend(client, staff_factory, auth_headers, db):
    from app.auth0_management import Auth0ManagementError
    from app.models import Staff

    _, admin_token = staff_factory("admin")
    target = Staff(auth0_sub="auth0|resend-target-2", name="Resend Target 2", email="resend2@example.com", role="nurse")
    db.add(target)
    db.commit()

    with patch("app.routers.staff.trigger_password_reset_email"), \
         patch("app.routers.staff.trigger_verification_email", side_effect=Auth0ManagementError("simulated failure")):
        resp = client.post(f"/api/staff/{target.id}/resend-invite", headers=auth_headers(admin_token))

    assert resp.status_code == 200
    assert resp.json()["email_sent"] is True
    assert resp.json()["verification_email_sent"] is False
    assert "simulated failure" in resp.json()["verification_error"]


def test_resend_invite_password_reset_failure_still_blocks_as_before(client, staff_factory, auth_headers, db):
    """Unchanged, critical-path behavior — a password-reset failure must
    still fail the whole request, since without it the person has no way
    to log in at all."""
    from app.auth0_management import Auth0ManagementError
    from app.models import Staff

    _, admin_token = staff_factory("admin")
    target = Staff(auth0_sub="auth0|resend-target-3", name="Resend Target 3", email="resend3@example.com", role="nurse")
    db.add(target)
    db.commit()

    with patch("app.routers.staff.trigger_password_reset_email", side_effect=Auth0ManagementError("reset failed")):
        resp = client.post(f"/api/staff/{target.id}/resend-invite", headers=auth_headers(admin_token))

    assert resp.status_code == 502


def test_nurse_cannot_deactivate_another_staff_member(client, staff_factory, auth_headers):
    nurse, nurse_token = staff_factory("nurse")
    target, _ = staff_factory("care_manager")
    resp = client.post(f"/api/staff/{target.id}/deactivate", headers=auth_headers(nurse_token))
    assert resp.status_code == 403


def test_admin_can_deactivate_a_non_last_admin_staff_member(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    target, _ = staff_factory("nurse")
    with patch("app.routers.staff.set_user_blocked"):
        resp = client.post(f"/api/staff/{target.id}/deactivate", headers=auth_headers(admin_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "inactive"


def test_last_active_admin_cannot_deactivate_themselves(client, staff_factory, auth_headers):
    """The safeguard added specifically because invite/reactivate are
    themselves admin-only — without this check, the last admin deactivating
    themselves would be a permanent, unrecoverable lockout."""
    admin, admin_token = staff_factory("admin")
    resp = client.post(f"/api/staff/{admin.id}/deactivate", headers=auth_headers(admin_token))
    assert resp.status_code == 409
    assert "last active admin" in resp.json()["detail"].lower()


def test_admin_can_deactivate_self_when_another_admin_exists(client, staff_factory, auth_headers):
    admin1, admin1_token = staff_factory("admin", name="Admin One")
    staff_factory("admin", name="Admin Two")
    with patch("app.routers.staff.set_user_blocked"):
        resp = client.post(f"/api/staff/{admin1.id}/deactivate", headers=auth_headers(admin1_token))
    assert resp.status_code == 200


def test_non_author_non_admin_cannot_delete_someone_elses_care_note(client, staff_factory, auth_headers, db):
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="TEST-001")
    db.add(patient)
    db.commit()

    author, author_token = staff_factory("nurse", name="Note Author")
    other, other_token = staff_factory("care_manager", name="Someone Else")

    note_resp = client.post(
        f"/api/patients/{patient.id}/care-notes", headers=auth_headers(author_token), json={"content": "A note"},
    )
    note_id = note_resp.json()["id"]

    resp = client.delete(f"/api/patients/{patient.id}/care-notes/{note_id}", headers=auth_headers(other_token))
    assert resp.status_code == 403
    assert "own care notes" in resp.json()["detail"]


def test_author_can_delete_their_own_care_note(client, staff_factory, auth_headers, db):
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="TEST-002")
    db.add(patient)
    db.commit()

    author, author_token = staff_factory("nurse")
    note_resp = client.post(
        f"/api/patients/{patient.id}/care-notes", headers=auth_headers(author_token), json={"content": "A note"},
    )
    note_id = note_resp.json()["id"]

    resp = client.delete(f"/api/patients/{patient.id}/care-notes/{note_id}", headers=auth_headers(author_token))
    assert resp.status_code == 204


def test_admin_can_delete_someone_elses_care_note(client, staff_factory, auth_headers, db):
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="TEST-003")
    db.add(patient)
    db.commit()

    author, author_token = staff_factory("nurse")
    _, admin_token = staff_factory("admin")
    note_resp = client.post(
        f"/api/patients/{patient.id}/care-notes", headers=auth_headers(author_token), json={"content": "A note"},
    )
    note_id = note_resp.json()["id"]

    resp = client.delete(f"/api/patients/{patient.id}/care-notes/{note_id}", headers=auth_headers(admin_token))
    assert resp.status_code == 204


def test_nurse_cannot_deactivate_a_patient(client, staff_factory, auth_headers, db):
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="TEST-004")
    db.add(patient)
    db.commit()

    _, nurse_token = staff_factory("nurse")
    resp = client.post(f"/api/patients/{patient.id}/deactivate", headers=auth_headers(nurse_token), json={})
    assert resp.status_code == 403


def test_care_manager_can_deactivate_a_patient(client, staff_factory, auth_headers, db):
    from app.models import Patient
    patient = Patient(name="Test Patient", mrn="TEST-005")
    db.add(patient)
    db.commit()

    _, manager_token = staff_factory("care_manager")
    resp = client.post(
        f"/api/patients/{patient.id}/deactivate", headers=auth_headers(manager_token), json={"reason": "test"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_nurse_cannot_use_auth0_lookup(client, staff_factory, auth_headers):
    _, nurse_token = staff_factory("nurse")
    resp = client.get("/api/staff/auth0-lookup?email=someone@example.com", headers=auth_headers(nurse_token))
    assert resp.status_code == 403


def test_auth0_lookup_finds_an_unlinked_account(client, staff_factory, auth_headers):
    """The actual fix for the reported gap: a real Auth0 account exists, but no
    Staff row does (e.g. the row was removed at some point without the real
    account ever being deleted) — this is what makes re-linking that account
    possible without needing to already know its internal auth0_sub."""
    from unittest.mock import patch
    _, admin_token = staff_factory("admin")

    with patch(
        "app.routers.staff.find_auth0_user_by_email",
        return_value={"auth0_sub": "auth0|foundsub123", "name": "Found Person", "email": "found@example.com"},
    ):
        resp = client.get("/api/staff/auth0-lookup?email=found@example.com", headers=auth_headers(admin_token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["auth0_sub"] == "auth0|foundsub123"
    assert body["already_linked"] is False


def test_auth0_lookup_reports_already_linked(client, staff_factory, auth_headers, db):
    from unittest.mock import patch
    from app.models import Staff
    admin, admin_token = staff_factory("admin")

    already = Staff(auth0_sub="auth0|alreadylinked", name="Already Linked", email="linked@example.com", role="nurse")
    db.add(already)
    db.commit()

    with patch(
        "app.routers.staff.find_auth0_user_by_email",
        return_value={"auth0_sub": "auth0|alreadylinked", "name": "Already Linked", "email": "linked@example.com"},
    ):
        resp = client.get("/api/staff/auth0-lookup?email=linked@example.com", headers=auth_headers(admin_token))

    body = resp.json()
    assert body["found"] is True
    assert body["already_linked"] is True
    assert body["already_linked_status"] == "active"


def test_auth0_lookup_reports_not_found(client, staff_factory, auth_headers):
    from unittest.mock import patch
    _, admin_token = staff_factory("admin")

    with patch("app.routers.staff.find_auth0_user_by_email", return_value=None):
        resp = client.get("/api/staff/auth0-lookup?email=nobody@example.com", headers=auth_headers(admin_token))

    assert resp.json() == {"found": False}
