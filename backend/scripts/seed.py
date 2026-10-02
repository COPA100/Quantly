"""seed a freshly stood-up stack with a demo account and an analyzed portfolio.

`terraform destroy` wipes the database, so every demo starts from nothing. this
goes through the public api rather than writing rows directly: it needs no
access to the private database, and it exercises the real path end to end
(upload -> s3 -> celery -> worker -> results).

    python -m scripts.seed --api-url http://localhost:8000
"""

import argparse
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import requests

# the larger sample book: 13 holdings, enough for a meaningful correlation matrix
DEFAULT_CSV = Path(__file__).resolve().parents[2] / "example_csv" / "ex2.csv"
DEFAULT_EMAIL = "demo@example.com"
DEFAULT_PASSWORD = "quantly-demo"


class SeedError(RuntimeError):
    """seeding could not finish, the message says why."""


class Api:
    """the few calls seeding needs, over anything with a requests-style `request`."""

    def __init__(self, base_url: str, session=None):
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()

    def request(self, method: str, path: str, token: str | None = None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self._session.request(method, self._base_url + path, headers=headers, **kwargs)


def _login(api: Api, email: str, password: str) -> str:
    # 201 is a new account, 409 means an earlier run already made it
    registered = api.request("POST", "/auth/register", json={"email": email, "password": password})
    if registered.status_code not in (201, 409):
        raise SeedError(f"register failed ({registered.status_code}): {registered.text}")

    login = api.request("POST", "/auth/login", json={"email": email, "password": password})
    if login.status_code == 401:
        raise SeedError(f"{email} already exists with a different password")
    if login.status_code != 200:
        raise SeedError(f"login failed ({login.status_code}): {login.text}")
    return login.json()["access_token"]


def seed(api: Api, email: str, password: str, csv_path: Path) -> dict:
    """make sure the demo user exists and owns a portfolio. safe to run twice."""
    token = _login(api, email, password)

    existing = api.request("GET", "/portfolios", token=token)
    if existing.status_code != 200:
        raise SeedError(f"listing portfolios failed ({existing.status_code}): {existing.text}")
    if existing.json():
        # newest first, so this is the most recent upload
        return {"token": token, "portfolio_id": existing.json()[0]["id"], "created": False}

    uploaded = api.request(
        "POST",
        "/portfolios",
        token=token,
        files={"file": (csv_path.name, csv_path.read_bytes(), "text/csv")},
    )
    if uploaded.status_code != 202:
        raise SeedError(f"upload failed ({uploaded.status_code}): {uploaded.text}")
    return {"token": token, "portfolio_id": uploaded.json()["id"], "created": True}


def wait_for_analysis(
    api: Api,
    token: str,
    portfolio_id: int,
    timeout: float = 300,
    interval: float = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """block until the worker has finished the portfolio, or raise."""
    waited = 0.0
    while True:
        response = api.request("GET", f"/portfolios/{portfolio_id}", token=token)
        if response.status_code != 200:
            raise SeedError(f"status check failed ({response.status_code}): {response.text}")

        status = response.json()["status"]
        if status == "complete":
            return
        if status == "failed":
            raise SeedError("analysis failed, check the worker logs")
        if waited >= timeout:
            raise SeedError(f"timed out after {timeout:.0f}s with the portfolio still {status}")

        sleep(interval)
        waited += interval


def main() -> int:
    parser = argparse.ArgumentParser(description="seed a quantly stack with demo data")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument(
        "--password",
        default=os.environ.get("QUANTLY_DEMO_PASSWORD", DEFAULT_PASSWORD),
        help="defaults to $QUANTLY_DEMO_PASSWORD, then a well-known demo password",
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--no-wait", action="store_true", help="return once uploaded, without waiting on the worker"
    )
    args = parser.parse_args()

    api = Api(args.api_url)
    try:
        result = seed(api, args.email, args.password, args.csv)
        verb = "uploaded" if result["created"] else "already has"
        print(f"{args.email} {verb} portfolio {result['portfolio_id']}")
        if not args.no_wait:
            print("waiting for the worker to analyze it...")
            wait_for_analysis(api, result["token"], result["portfolio_id"])
            print("analysis complete")
    except (SeedError, requests.RequestException) as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1

    print(f"sign in as {args.email} / {args.password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
