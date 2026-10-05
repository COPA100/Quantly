from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

from api.main import app


def test_exhausted_db_pool_is_a_503_with_retry_after():
    @app.get("/_pool_exhausted")
    def exhausted():
        raise PoolTimeoutError("QueuePool limit reached")

    try:
        response = TestClient(app).get("/_pool_exhausted")
    finally:
        app.router.routes = [r for r in app.router.routes if r.path != "/_pool_exhausted"]
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
