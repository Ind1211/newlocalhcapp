"""
A real client for Auth0's Management API — shifts user creation, editing, and
deactivation into this app, rather than requiring someone to go create accounts
directly in the Auth0 dashboard first.

This is genuinely separate from app/auth.py, which only ever VERIFIES a token
someone else already has. This module actively creates and modifies Auth0
accounts, using the M2M application's own client-credentials grant — a
fundamentally different, higher-privilege relationship with Auth0 than anything
else in this app has. The M2M client secret this depends on is exactly as
sensitive as the Anthropic API key: backend-only, never exposed to the frontend.
"""

import os
import secrets
import time

import httpx

_token_cache: dict = {"token": None, "expires_at": 0}


class Auth0ManagementError(Exception):
    pass


def _domain() -> str:
    domain = os.environ.get("AUTH0_DOMAIN")
    if not domain:
        raise Auth0ManagementError("AUTH0_DOMAIN is not set.")
    return domain


def _get_management_token() -> str:
    """Management API tokens are long-lived (Auth0 issues them for 24 hours) —
    cached here so every single staff-management action doesn't re-authenticate
    from scratch. Refreshed 5 minutes before actual expiry, not exactly at it, so
    a token doesn't expire mid-request."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"]

    client_id = os.environ.get("AUTH0_M2M_CLIENT_ID")
    client_secret = os.environ.get("AUTH0_M2M_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise Auth0ManagementError(
            "AUTH0_M2M_CLIENT_ID / AUTH0_M2M_CLIENT_SECRET are not set — required to "
            "manage Auth0 users from this app. See the README for how to create and "
            "authorize the Machine-to-Machine application these come from."
        )

    domain = _domain()
    try:
        response = httpx.post(
            f"https://{domain}/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": f"https://{domain}/api/v2/",
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise Auth0ManagementError(f"Could not authenticate with Auth0's Management API: {e}") from e

    data = response.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 86400)
    return _token_cache["token"]


def find_auth0_user_by_email(email: str) -> dict | None:
    """Auth0's own users-by-email lookup — returns the account's real user_id
    (the same value that account's JWTs carry as 'sub', usable directly as
    Staff.auth0_sub) plus its name, or None if no account exists for this email
    at all. This is what actually closes the real gap: re-inviting someone whose
    Auth0 account already exists (e.g. after their Staff row alone was removed,
    not the account itself) fails with a duplicate-email error from Auth0 — this
    lookup is what makes RE-LINKING that already-real account possible, without
    needing to already know its internal user_id from the Auth0 dashboard."""
    domain = _domain()
    token = _get_management_token()
    try:
        response = httpx.get(
            f"https://{domain}/api/v2/users-by-email",
            headers={"Authorization": f"Bearer {token}"},
            params={"email": email},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise Auth0ManagementError(f"Could not search Auth0 for this email: {e}") from e

    users = response.json()
    if not users:
        return None
    # Multiple accounts for one email is possible across different identity
    # providers (a rare edge case) — the first match is treated as the real
    # one, matching how this app has never needed to support more than a
    # single Username-Password-Authentication account per person anywhere else.
    user = users[0]
    return {"auth0_sub": user["user_id"], "name": user.get("name") or email, "email": user.get("email", email)}


def create_auth0_user(email: str, name: str) -> str:
    """Creates a real Auth0 account and returns its user_id — this IS the same
    value as the JWT 'sub' claim that account's future tokens will carry, so it
    can be used directly as Staff.auth0_sub without the person ever needing to
    log in first. The password set here is a random, effectively unusable
    placeholder — Auth0 requires a password at creation time even though the
    real person will never use it, since trigger_password_reset_email() sends
    them a real link to set their own immediately after."""
    domain = _domain()
    token = _get_management_token()
    temp_password = secrets.token_urlsafe(24) + "aA1!"  # satisfies typical complexity rules, never used

    try:
        response = httpx.post(
            f"https://{domain}/api/v2/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": email,
                "name": name,
                "connection": "Username-Password-Authentication",
                "password": temp_password,
                "email_verified": False,
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("message", str(e)) if e.response.content else str(e)
        raise Auth0ManagementError(f"Could not create the Auth0 account: {detail}") from e
    except httpx.HTTPError as e:
        raise Auth0ManagementError(f"Could not create the Auth0 account: {e}") from e

    return response.json()["user_id"]


def trigger_password_reset_email(email: str) -> None:
    """Uses Auth0's Authentication API (not Management) — this is the same
    endpoint behind a real "Forgot Password" flow, and needs only a client_id,
    not a Management token, since it's a public-facing endpoint by design.
    Reused here to double as an invite email: the new person's very first
    action is setting their own password through a real, secure Auth0 link,
    rather than being told a password by a staff member."""
    domain = _domain()
    client_id = os.environ.get("AUTH0_SPA_CLIENT_ID") or os.environ.get("AUTH0_M2M_CLIENT_ID")
    try:
        response = httpx.post(
            f"https://{domain}/dbconnections/change_password",
            json={"client_id": client_id, "email": email, "connection": "Username-Password-Authentication"},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise Auth0ManagementError(f"Account was created, but the invite email could not be sent: {e}") from e


def trigger_verification_email(user_id: str) -> None:
    """Uses Auth0's Management API jobs endpoint — genuinely separate from
    trigger_password_reset_email above, since the two prove different
    things. Setting a password through the reset link only proves someone
    with access to that email inbox clicked a link at that moment; it does
    not mark the address itself as verified in Auth0 — email_verified is set
    to False at account creation (see create_auth0_user) and nothing else in
    this app ever flips it. This sends Auth0's own dedicated verification
    email, which is what actually can. Needs a Management token, since this
    is an authenticated, account-specific operation, not the public-facing
    password-reset endpoint. client_id is included so the email uses the
    real SPA's branding — without it, Auth0 falls back to a generic,
    tenant-default template that shows the raw tenant domain as the sender
    instead of a real application name."""
    domain = _domain()
    token = _get_management_token()
    client_id = os.environ.get("AUTH0_SPA_CLIENT_ID") or os.environ.get("AUTH0_M2M_CLIENT_ID")
    try:
        response = httpx.post(
            f"https://{domain}/api/v2/jobs/verification-email",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": user_id, "client_id": client_id},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise Auth0ManagementError(f"Could not send the verification email: {e}") from e


def update_auth0_user(user_id: str, name: str | None = None, email: str | None = None) -> None:
    domain = _domain()
    token = _get_management_token()
    payload = {}
    if name is not None:
        payload["name"] = name
    if email is not None:
        payload["email"] = email
    if not payload:
        return
    try:
        response = httpx.patch(
            f"https://{domain}/api/v2/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise Auth0ManagementError(f"Could not update the Auth0 account: {e}") from e


def set_user_blocked(user_id: str, blocked: bool) -> None:
    """Deliberately the only lifecycle-ending action this module exposes — no
    delete_user() exists here at all. Blocking is reversible and preserves the
    account's real history; permanent deletion is irreversible and was
    deliberately scoped out when this feature was planned, precisely because a
    one-click delete button is a very different risk than a one-click block button."""
    domain = _domain()
    token = _get_management_token()
    try:
        response = httpx.patch(
            f"https://{domain}/api/v2/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"blocked": blocked},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise Auth0ManagementError(f"Could not update the Auth0 account's blocked status: {e}") from e
