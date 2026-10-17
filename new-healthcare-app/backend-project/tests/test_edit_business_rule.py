"""
Tests for editing an existing business rule in place — the real gap found
when a user asked how to view/edit an existing rule's DSL, and neither the
API nor the UI supported it at all.
"""

VALID_DSL = '''RULE "Test Editable Rule"
WHEN assessment.completed
IF event.severity == "critical"
THEN
  CREATE_TASK "Original task" ASSIGN "Nurse" DUE "24h"
END'''

UPDATED_DSL = '''RULE "Test Editable Rule Renamed"
WHEN assessment.completed
IF event.severity == "warning"
THEN
  CREATE_TASK "Updated task" ASSIGN "Care Admin" DUE "same_day"
END'''


def _create_rule(client, headers, dsl=VALID_DSL, governance="operational"):
    resp = client.post("/api/business-rules", headers=headers, json={"dsl_text": dsl, "governance": governance})
    assert resp.status_code == 201
    return resp.json()


def test_editing_a_disabled_rule_updates_it_in_place(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    rule = _create_rule(client, headers)
    original_id = rule["id"]

    resp = client.patch(f"/api/business-rules/{original_id}", headers=headers, json={"dsl_text": UPDATED_DSL, "governance": "clinical"})
    assert resp.status_code == 200
    updated = resp.json()

    # The id must stay the same — that's the entire point of a real edit
    # endpoint over the old delete-and-recreate workaround.
    assert updated["id"] == original_id
    assert updated["name"] == "Test Editable Rule Renamed"
    assert updated["governance"] == "clinical"
    assert updated["dsl_text"] == UPDATED_DSL
    assert updated["enabled"] is False


def test_editing_an_enabled_rule_is_refused(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    rule = _create_rule(client, headers)

    enable_resp = client.patch(f"/api/business-rules/{rule['id']}/enable", headers=headers, json={"confirmed": False})
    assert enable_resp.status_code == 200

    resp = client.patch(f"/api/business-rules/{rule['id']}", headers=headers, json={"dsl_text": UPDATED_DSL, "governance": "operational"})
    assert resp.status_code == 409
    assert "disable" in resp.json()["detail"].lower()

    # Confirm it genuinely wasn't changed
    rules_resp = client.get("/api/business-rules", headers=headers)
    still_there = next(r for r in rules_resp.json() if r["id"] == rule["id"])
    assert still_there["dsl_text"] == VALID_DSL


def test_disable_then_edit_then_reenable_works(client, staff_factory, auth_headers):
    """The real, intended workflow end to end."""
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    rule = _create_rule(client, headers)

    client.patch(f"/api/business-rules/{rule['id']}/enable", headers=headers, json={"confirmed": False})
    client.patch(f"/api/business-rules/{rule['id']}/disable", headers=headers)

    edit_resp = client.patch(f"/api/business-rules/{rule['id']}", headers=headers, json={"dsl_text": UPDATED_DSL, "governance": "operational"})
    assert edit_resp.status_code == 200

    reenable_resp = client.patch(f"/api/business-rules/{rule['id']}/enable", headers=headers, json={"confirmed": False})
    assert reenable_resp.status_code == 200
    assert reenable_resp.json()["dsl_text"] == UPDATED_DSL


def test_editing_with_invalid_dsl_is_rejected_and_nothing_changes(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    rule = _create_rule(client, headers)

    resp = client.patch(f"/api/business-rules/{rule['id']}", headers=headers, json={"dsl_text": "not valid dsl at all", "governance": "operational"})
    assert resp.status_code == 400

    rules_resp = client.get("/api/business-rules", headers=headers)
    still_there = next(r for r in rules_resp.json() if r["id"] == rule["id"])
    assert still_there["dsl_text"] == VALID_DSL


def test_editing_a_nonexistent_rule_returns_404(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    headers = auth_headers(admin_token)
    resp = client.patch("/api/business-rules/00000000-0000-0000-0000-000000000000", headers=headers, json={"dsl_text": VALID_DSL, "governance": "operational"})
    assert resp.status_code == 404


def test_editing_requires_admin_role(client, staff_factory, auth_headers):
    _, admin_token = staff_factory("admin")
    _, nurse_token = staff_factory("nurse")
    rule = _create_rule(client, auth_headers(admin_token))

    resp = client.patch(f"/api/business-rules/{rule['id']}", headers=auth_headers(nurse_token), json={"dsl_text": UPDATED_DSL, "governance": "operational"})
    assert resp.status_code == 403
