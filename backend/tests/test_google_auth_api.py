import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import common.models  # noqa: F401  registers every model on the metadata
from api.deps import get_google_verifier
from api.main import app
from api.security.google import GoogleAuthError
from api.security.tokens import decode_access_token
from common.db import Base, get_db


@pytest.fixture
def http():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    # the box lets each test control what the fake verifier returns (or raise)
    default_claims = {"sub": "sub-1", "email": "g@example.com", "email_verified": True}
    box = {"claims": default_claims, "fail": False}

    def override_verifier():
        def verify(_token):
            if box["fail"]:
                raise GoogleAuthError("bad token")
            return box["claims"]

        return verify

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_google_verifier] = override_verifier
    yield TestClient(app), box
    app.dependency_overrides.clear()


def test_new_google_user_gets_token_pair(http):
    client, _ = http
    resp = client.post("/auth/google", json={"id_token": "x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_google_token_works_on_protected_route(http):
    client, _ = http
    access = client.post("/auth/google", json={"id_token": "x"}).json()["access_token"]
    resp = client.get("/portfolios", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200


def test_returning_google_user_is_not_duplicated(http):
    client, _ = http
    first = client.post("/auth/google", json={"id_token": "x"}).json()
    second = client.post("/auth/google", json={"id_token": "x"}).json()
    # same subject id means the same user, not a new account
    sub1 = decode_access_token(first["access_token"])["sub"]
    sub2 = decode_access_token(second["access_token"])["sub"]
    assert sub1 == sub2


def test_google_links_to_existing_email_account(http):
    client, box = http
    box["claims"] = {"sub": "sub-9", "email": "colin@example.com", "email_verified": True}

    # a password account already exists for this email
    client.post("/auth/register", json={"email": "colin@example.com", "password": "hunter2pw"})

    google = client.post("/auth/google", json={"id_token": "x"})
    assert google.status_code == 200

    # password login still works after linking
    pw = client.post("/auth/login", json={"email": "colin@example.com", "password": "hunter2pw"})
    assert pw.status_code == 200


def test_invalid_google_token_rejected(http):
    client, box = http
    box["fail"] = True
    resp = client.post("/auth/google", json={"id_token": "x"})
    assert resp.status_code == 401
