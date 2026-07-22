import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import common.models  # noqa: F401  registers every model on the metadata
from api.main import app
from common.db import Base, get_db

CREDS = {"email": "user@example.com", "password": "hunter2pw"}


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

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register_and_login(http):
    http.post("/auth/register", json=CREDS)
    return http.post("/auth/login", json=CREDS).json()


def test_register_returns_user_without_secrets(http):
    resp = http.post("/auth/register", json=CREDS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == CREDS["email"]
    assert "hashed_password" not in body
    assert "password" not in body


def test_duplicate_register_conflicts(http):
    http.post("/auth/register", json=CREDS)
    assert http.post("/auth/register", json=CREDS).status_code == 409


def test_login_returns_token_pair(http):
    http.post("/auth/register", json=CREDS)
    resp = http.post("/auth/login", json=CREDS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_with_wrong_password_rejected(http):
    http.post("/auth/register", json=CREDS)
    resp = http.post("/auth/login", json={"email": CREDS["email"], "password": "wrongpass"})
    assert resp.status_code == 401


def test_refresh_rotates_and_invalidates_old(http):
    tokens = register_and_login(http)
    old = tokens["refresh_token"]

    rotated = http.post("/auth/refresh", json={"refresh_token": old})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != old

    # old token no longer works
    assert http.post("/auth/refresh", json={"refresh_token": old}).status_code == 401


def test_logout_kills_the_refresh_token(http):
    tokens = register_and_login(http)
    rt = tokens["refresh_token"]

    assert http.post("/auth/logout", json={"refresh_token": rt}).status_code == 204
    assert http.post("/auth/refresh", json={"refresh_token": rt}).status_code == 401


def test_logout_all_kills_every_session(http):
    http.post("/auth/register", json=CREDS)
    sessions = [http.post("/auth/login", json=CREDS).json()["refresh_token"] for _ in range(3)]
    assert http.post("/auth/logout-all", json={"refresh_token": sessions[0]}).status_code == 204
    for rt in sessions:
        assert http.post("/auth/refresh", json={"refresh_token": rt}).status_code == 401


def test_reused_token_revokes_the_whole_family(http):
    tokens = register_and_login(http)
    r1 = tokens["refresh_token"]
    r2 = http.post("/auth/refresh", json={"refresh_token": r1}).json()["refresh_token"]

    # replay the already-rotated r1
    replay = http.post("/auth/refresh", json={"refresh_token": r1})
    assert replay.status_code == 401

    # the active r2 is now revoked as well
    assert http.post("/auth/refresh", json={"refresh_token": r2}).status_code == 401
