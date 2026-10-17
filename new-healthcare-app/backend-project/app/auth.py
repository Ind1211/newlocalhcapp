"""
Real, independent JWT verification on the backend — not just decoding.

Kong already validates every request's JWT signature before it reaches this
container at all; a request with a bad or missing token never gets here. But
"Kong let it through" and "the backend independently confirmed who this is" are
two different guarantees, and until this module existed, only the first one was
ever actually checked here. This re-verifies the signature (using the same
Auth0 public key Kong itself uses) rather than trusting the token's contents on
faith — genuine defense-in-depth, not just identity extraction dressed up as one.
"""

import os

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Staff

_public_key_cache: str | None = None


def _load_public_key() -> str:
    """Loads the Auth0 RSA public key used to verify JWT signatures.

    Checked in this order:
    - AUTH0_PUBLIC_KEY: the full PEM contents as an env var / secret — used on
      Azure Container Apps, which has no docker-compose-style file mount.
    - AUTH0_PUBLIC_KEY_PATH: a file path — used by docker-compose, which mounts
      auth0-public-key.pem into the container as a real file.
    """
    global _public_key_cache
    if _public_key_cache is None:
        env_key = os.environ.get("AUTH0_PUBLIC_KEY")
        if env_key:
            _public_key_cache = env_key
        else:
            path = os.environ.get("AUTH0_PUBLIC_KEY_PATH", "/app/auth0-public-key.pem")
            try:
                with open(path) as f:
                    _public_key_cache = f.read()
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"Auth0 public key not found — set AUTH0_PUBLIC_KEY (PEM contents) as an "
                    f"env var, or mount a file at {path} (AUTH0_PUBLIC_KEY_PATH), so tokens can "
                    "be independently verified."
                ) from e
    return _public_key_cache


def get_auth0_sub(request: Request) -> str:
    """Verifies the request's own JWT and returns its 'sub' claim — the stable,
    permanent Auth0 user identifier. Raises 401 if the token is missing, expired,
    or fails signature verification, even though Kong already checked this once —
    this backend never simply trusts that upstream check happened."""
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = auth_header[len("Bearer "):]

    audience = os.environ.get("AUTH0_AUDIENCE")
    issuer = os.environ.get("AUTH0_ISSUER")
    try:
        payload = jwt.decode(
            token,
            _load_public_key(),
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    return payload["sub"]


def get_current_staff(request: Request, db: Session = Depends(get_db)) -> Staff | None:
    """Returns the Staff record for whoever made this request, or None if this is
    a genuinely authenticated Auth0 user who simply hasn't been registered as
    staff yet — that's a real, expected state (someone just added to Auth0 before
    an admin created their staff record), not an error condition by itself.
    Endpoints that require a real staff identity check for None explicitly and
    raise their own 403, rather than this function deciding that for every caller."""
    sub = get_auth0_sub(request)
    return db.query(Staff).filter_by(auth0_sub=sub).first()


def require_staff(staff: Staff | None = Depends(get_current_staff)) -> Staff:
    """For endpoints that genuinely require a registered staff identity to do
    anything meaningful — e.g. writing a care note as a specific author."""
    if not staff:
        raise HTTPException(
            status_code=403,
            detail="Your account is authenticated but not yet registered as staff. Contact an admin.",
        )
    return staff
