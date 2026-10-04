"""pins the full analytics output on a fixed book and fixed synthetic prices.

refactors of the analysis pipeline must leave this snapshot unchanged. to
regenerate after an intended change: `python -m tests.test_analytics_golden`.
"""

import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

import common.analytics.accelerated as accelerated
import worker.analysis as analysis
from common.models import Portfolio, Price

ROOT = Path(__file__).resolve().parents[2]
CSV = (ROOT / "example_csv" / "ex2.csv").read_bytes()
SNAPSHOT = Path(__file__).parent / "fixtures" / "analytics_golden.json"

AS_OF = date(2026, 6, 30)
DAYS = 300
TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "V", "JNJ"]
TICKERS += ["VOO", "VTI", "QQQ", "SPY"]


def _business_days(end: date, n: int) -> list[date]:
    days: list[date] = []
    d = end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days[::-1]


DATES = _business_days(AS_OF, DAYS)


def _closes(ticker: str) -> np.ndarray:
    # deterministic gbm per ticker, every ticker on the same calendar
    seed = sum(ord(c) * 31**i for i, c in enumerate(ticker)) % (2**32)
    rng = np.random.default_rng(seed)
    shocks = rng.normal(0.0004, 0.015, DAYS)
    return 100.0 * np.cumprod(1.0 + shocks)


SERIES = {t: _closes(t) for t in TICKERS}


def _history(ticker: str) -> list[Price]:
    return [
        Price(ticker=ticker, date=d, close=float(c), adj_close=float(c))
        for d, c in zip(DATES, SERIES[ticker], strict=True)
    ]


class _Storage:
    def download_bytes(self, key):
        return CSV


def _patch(monkeypatch):
    # numpy path only, so the snapshot holds with or without the c++ engine
    monkeypatch.setattr(accelerated, "_engine", None)
    monkeypatch.setattr(analysis, "get_storage", lambda: _Storage())
    monkeypatch.setattr(
        analysis,
        "get_current_prices",
        lambda tickers: {t: round(float(SERIES[t][-1]), 2) for t in tickers},
    )
    monkeypatch.setattr(analysis, "ensure_history", lambda db, t, as_of=None: _history(t))
    monkeypatch.setattr(analysis, "ensure_benchmark", lambda db, as_of=None: _history("SPY"))
    monkeypatch.setattr(analysis, "get_cached", lambda digest: None)
    monkeypatch.setattr(analysis, "set_cached", lambda digest, results: None)


def compute(monkeypatch) -> dict:
    _patch(monkeypatch)
    portfolio = Portfolio(id=1, user_id=1, original_filename="ex2.csv", s3_key="k")
    return analysis.compute_analytics(None, portfolio, as_of=AS_OF)


def _assert_close(actual, expected, path="$"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert set(actual) == set(expected), f"{path}: keys differ"
        for key in expected:
            _assert_close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            _assert_close(a, e, f"{path}[{i}]")
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12), path
    else:
        assert actual == expected, path


def test_analytics_output_matches_snapshot(monkeypatch):
    if not SNAPSHOT.exists():
        pytest.fail("missing snapshot, generate it with python -m tests.test_analytics_golden")
    expected = json.loads(SNAPSHOT.read_text())
    # round-trip through json so tuples, ints vs floats etc. compare like stored results
    actual = json.loads(json.dumps(compute(monkeypatch)))
    # new analyzers add keys; the ones pinned here must not change
    assert set(expected) <= set(actual)
    _assert_close({k: actual[k] for k in expected}, expected)


if __name__ == "__main__":
    mp = pytest.MonkeyPatch()
    try:
        out = compute(mp)
    finally:
        mp.undo()
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"wrote {SNAPSHOT}")
