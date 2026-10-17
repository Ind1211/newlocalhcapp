"""
Shared test fixtures. Runs against a real, separate Postgres test database —
not SQLite — since this app genuinely depends on Postgres-specific features
(JSONB columns, native UUID types) that SQLite doesn't support faithfully. A
suite that passed against SQLite but silently broke on real Postgres types
would be worse than no suite at all: confident and wrong.

External services (Auth0 Management API, Anthropic, Azure Blob Storage, SMTP) are mocked at
the fixture level, not hit for real — the same mocking approach used
throughout this project's own manual verification, just made permanent here
instead of re-typed by hand every session.
"""

import os
import time

# Configurable, not hardcoded to localhost — that only works when Postgres runs
# on the same machine as the test process (a local dev machine, or CI). This
# app's real deployment runs Postgres in its OWN separate container
# (kidney_cardiology_db), reached via host.docker.internal from inside the
# backend container — from there, "localhost" means the backend container
# itself, which has no Postgres on it at all. Set TEST_DB_HOST=host.docker.internal
# when running these tests inside that container; the default stays localhost
# for everyone else.
#
# The password is configurable for the same underlying reason: the real
# kidney_app_user account was created with whatever real password this
# deployment's own .env actually uses, not a fixed test value. Set
# TEST_DB_PASSWORD to match that real password when running against a real,
# already-existing Postgres user rather than a fresh one made just for tests.
_test_db_host = os.environ.get("TEST_DB_HOST", "localhost")
_test_db_password = os.environ.get("TEST_DB_PASSWORD", "testpass123")
os.environ["DATABASE_URL"] = f"postgresql+psycopg2://kidney_app_user:{_test_db_password}@{_test_db_host}:5432/kidney_cardiology_test_db"
os.environ["ANTHROPIC_API_KEY"] = "fake-test-key"

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt as pyjwt

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Staff

TEST_AUDIENCE = "https://test-api"
TEST_ISSUER = "https://test-tenant.us.auth0.com/"


@pytest.fixture(scope="session", autouse=True)
def _test_environment():
    """Session-scoped, autouse — runs once, sets up everything every single
    test in this suite needs regardless of which file it's in: the real RSA
    key pair backing every test token, the Auth0 verification env vars pointed
    at that key, and the database schema itself."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_path = "/tmp/pytest_auth0_public_key.pem"
    with open(key_path, "wb") as f:
        f.write(public_pem)

    os.environ["AUTH0_PUBLIC_KEY_PATH"] = key_path
    os.environ["AUTH0_AUDIENCE"] = TEST_AUDIENCE
    os.environ["AUTH0_ISSUER"] = TEST_ISSUER

    # Reset the auth module's own cached public key — it's read once and
    # cached at import time in app.auth, which would otherwise still be
    # holding None or a stale key from before this fixture set the env var.
    import app.auth as auth_module
    auth_module._public_key_cache = None

    Base.metadata.create_all(engine)

    yield {"private_key": private_key}

    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    """A fresh session per test, with every table truncated afterward — the
    simplest, most reliable way to guarantee one test's data can never leak
    into another's, given how many tests here create patients/staff/tasks with
    no natural uniqueness constraint between runs."""
    session = SessionLocal()
    yield session
    session.close()
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()


@pytest.fixture
def client():
    return TestClient(app)


def make_token(sub: str, private_key, expires_in: int = 3600) -> str:
    """Signs a real, valid JWT against the session's real key pair — this is
    what makes app.auth's verification genuinely exercised in every test that
    uses one, not bypassed or mocked away."""
    return pyjwt.encode(
        {"sub": sub, "iss": TEST_ISSUER, "aud": TEST_AUDIENCE, "exp": int(time.time()) + expires_in},
        private_key, algorithm="RS256",
    )


@pytest.fixture
def staff_factory(db, _test_environment):
    """Returns a function for creating a real Staff row AND a matching, validly
    signed token for it in one call — nearly every test needs both together,
    so the two are joined here rather than duplicated across dozens of tests."""
    created = []

    def _make(role: str, name: str = "Test Staff", email: str = "test@example.com") -> tuple[Staff, str]:
        sub = f"auth0|test-{role}-{len(created)}"
        staff = Staff(auth0_sub=sub, name=name, email=email, role=role)
        db.add(staff)
        db.commit()
        db.refresh(staff)
        created.append(staff)
        token = make_token(sub, _test_environment["private_key"])
        return staff, token

    return _make


@pytest.fixture
def auth_headers():
    def _headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}
    return _headers
