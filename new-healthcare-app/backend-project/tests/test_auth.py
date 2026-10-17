"""
JWT verification — tested against a real endpoint (/api/staff/me), not by
calling app.auth's internals directly. This exercises the actual dependency
injection chain a real request goes through, the same way these exact
scenarios were originally verified by hand when the staff system was built.
"""

from cryptography.hazmat.primitives.asymmetric import rsa

from tests.conftest import make_token


def test_valid_token_is_accepted(client, staff_factory, auth_headers):
    _, token = staff_factory("nurse")
    resp = client.get("/api/staff/me", headers=auth_headers(token))
    assert resp.status_code == 200


def test_tampered_token_is_rejected(client, staff_factory, auth_headers):
    _, token = staff_factory("nurse")
    tampered = token[:-5] + "XXXXX"
    resp = client.get("/api/staff/me", headers=auth_headers(tampered))
    assert resp.status_code == 401


def test_forged_token_signed_by_different_key_is_rejected(client, _test_environment, auth_headers):
    """The single most important case here — a token that's otherwise
    perfectly well-formed, just signed by a key that isn't the real one. If
    this ever passes, someone could impersonate any staff member by signing
    their own tokens."""
    forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged_token = make_token("auth0|attacker", forged_key)
    resp = client.get("/api/staff/me", headers=auth_headers(forged_token))
    assert resp.status_code == 401


def test_expired_token_is_rejected(client, _test_environment, auth_headers):
    expired_token = make_token("auth0|someone", _test_environment["private_key"], expires_in=-100)
    resp = client.get("/api/staff/me", headers=auth_headers(expired_token))
    assert resp.status_code == 401


def test_missing_authorization_header_is_rejected(client):
    resp = client.get("/api/staff/me")
    assert resp.status_code == 401


def test_malformed_authorization_header_is_rejected(client):
    resp = client.get("/api/staff/me", headers={"Authorization": "sometoken123"})
    assert resp.status_code == 401


def test_authenticated_but_unregistered_user_gets_null_not_error(client, _test_environment):
    """A genuinely different, non-error case from all the rejections above — a
    real, validly-signed token for someone who simply hasn't been added as
    staff yet. /me should return null, not 401 or 403."""
    token = make_token("auth0|never-registered", _test_environment["private_key"])
    resp = client.get("/api/staff/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() is None
