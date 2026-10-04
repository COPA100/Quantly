import pytest
import redis
import requests
from sqlalchemy.exc import OperationalError

from common.csv_reader import CSVValidationError
from worker.errors import PermanentError, TransientError, backoff_seconds, is_transient


class YFRateLimitError(Exception):
    __module__ = "yfinance.exceptions"


@pytest.mark.parametrize(
    "exc",
    [
        TransientError("x"),
        ConnectionError("x"),
        TimeoutError("x"),
        redis.ConnectionError("x"),
        redis.TimeoutError("x"),
        OperationalError("select 1", {}, Exception("server closed the connection")),
        requests.ConnectionError("x"),
        requests.Timeout("x"),
        YFRateLimitError("too many requests"),
    ],
)
def test_transient_errors(exc):
    assert is_transient(exc) is True


@pytest.mark.parametrize(
    "exc", [PermanentError("x"), CSVValidationError("x"), ValueError("x"), RuntimeError("x")]
)
def test_permanent_and_unknown_errors_do_not_retry(exc):
    assert is_transient(exc) is False


def test_cause_chain_is_inspected():
    try:
        try:
            raise redis.ConnectionError("down")
        except redis.ConnectionError as inner:
            raise RuntimeError("wrapped") from inner
    except RuntimeError as outer:
        assert is_transient(outer) is True


def test_permanent_wins_over_transient_cause():
    try:
        try:
            raise ConnectionError("net")
        except ConnectionError as inner:
            raise PermanentError("bad input") from inner
    except PermanentError as outer:
        assert is_transient(outer) is False


def test_backoff_grows_is_capped_and_jittered():
    first = [backoff_seconds(0, 2, 60) for _ in range(50)]
    assert all(1 <= d <= 2 for d in first)
    assert len(set(first)) > 1

    third = [backoff_seconds(2, 2, 60) for _ in range(50)]
    assert all(4 <= d <= 8 for d in third)

    capped = [backoff_seconds(10, 2, 60) for _ in range(50)]
    assert all(30 <= d <= 60 for d in capped)
