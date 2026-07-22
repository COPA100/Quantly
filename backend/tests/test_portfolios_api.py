import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import common.models  # noqa: F401  registers every model on the metadata
from api.main import app
from common.db import Base, get_db
from common.storage import get_storage

# minimal valid export: banner + blank (skiprows=2), header, two holdings,
# then cash + total footer rows (skipfooter=2)
VALID_CSV = (
    b'"Positions banner"\n\n'
    b'"Symbol","Qty (Quantity)","Cost Basis"\n'
    b'"AAPL","10","$1,500.00"\n'
    b'"MSFT","2","$500.00"\n'
    b'"Cash & Cash Investments","--","--"\n'
    b'"Account Total","--","--"\n'
)


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def upload_bytes(self, key, data, content_type="text/csv"):
        self.objects[key] = data

    def download_bytes(self, key):
        return self.objects[key]


@pytest.fixture
def client():
    # shared in-memory sqlite so every request in a test sees the same db
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

    storage = FakeStorage()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app), storage
    app.dependency_overrides.clear()


def auth_headers(http, email="owner@example.com"):
    http.post("/auth/register", json={"email": email, "password": "hunter2pw"})
    token = http.post("/auth/login", json={"email": email, "password": "hunter2pw"}).json()
    return {"Authorization": f"Bearer {token['access_token']}"}


def test_upload_then_list_and_detail(client):
    http, storage = client
    headers = auth_headers(http)

    created = http.post(
        "/portfolios", files={"file": ("p.csv", VALID_CSV, "text/csv")}, headers=headers
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "pending"
    pid = body["id"]

    # raw csv actually went to storage
    assert any(key.endswith("raw.csv") for key in storage.objects)

    # it shows up in the list
    listed = http.get("/portfolios", headers=headers)
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [pid]

    # detail carries the parsed holdings
    detail = http.get(f"/portfolios/{pid}", headers=headers)
    assert detail.status_code == 200
    assert [h["ticker"] for h in detail.json()["holdings"]] == ["AAPL", "MSFT"]


def test_missing_portfolio_returns_404(client):
    http, _ = client
    headers = auth_headers(http)
    assert http.get("/portfolios/999999", headers=headers).status_code == 404


def test_malformed_upload_returns_422(client):
    http, _ = client
    headers = auth_headers(http)
    resp = http.post(
        "/portfolios", files={"file": ("x.csv", b"garbage", "text/csv")}, headers=headers
    )
    assert resp.status_code == 422


def test_portfolio_routes_require_auth(client):
    http, _ = client
    assert http.get("/portfolios").status_code == 401


def test_users_only_see_their_own_portfolios(client):
    http, _ = client
    alice = auth_headers(http, email="alice@example.com")
    bob = auth_headers(http, email="bob@example.com")

    created = http.post(
        "/portfolios", files={"file": ("p.csv", VALID_CSV, "text/csv")}, headers=alice
    )
    pid = created.json()["id"]

    # bob cannot see alice's portfolio in his list, nor fetch it by id
    assert http.get("/portfolios", headers=bob).json() == []
    assert http.get(f"/portfolios/{pid}", headers=bob).status_code == 404
    # alice still can
    assert http.get(f"/portfolios/{pid}", headers=alice).status_code == 200
