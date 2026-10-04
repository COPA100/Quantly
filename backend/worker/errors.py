import random

import redis
import requests
from sqlalchemy.exc import OperationalError

from common.csv_reader import CSVValidationError

try:  # boto is only a runtime dep of storage, import defensively for the api image
    from botocore.exceptions import ConnectionError as BotoConnectionError
    from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError
except ImportError:  # pragma: no cover
    BotoConnectionError = ConnectTimeoutError = ReadTimeoutError = ()  # type: ignore[assignment]


class TransientError(Exception):
    """a failure that is likely to clear up on its own, so the task retries."""


class PermanentError(Exception):
    """a failure retrying cannot fix, so the task fails fast."""


_TRANSIENT_TYPES: tuple[type[BaseException], ...] = (
    TransientError,
    ConnectionError,
    TimeoutError,
    redis.ConnectionError,
    redis.TimeoutError,
    OperationalError,
    requests.ConnectionError,
    requests.Timeout,
)
if isinstance(BotoConnectionError, type):
    _TRANSIENT_TYPES += (BotoConnectionError, ConnectTimeoutError, ReadTimeoutError)

_PERMANENT_TYPES: tuple[type[BaseException], ...] = (PermanentError, CSVValidationError)

# yfinance has no stable exception base, match by name
_TRANSIENT_YFINANCE = {"YFRateLimitError"}


def is_transient(exc: BaseException) -> bool:
    # walk the cause chain, since sqlalchemy and our own code wrap lower-level errors
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, _PERMANENT_TYPES):
            return False
        if isinstance(current, _TRANSIENT_TYPES):
            return True
        module = type(current).__module__
        if module.startswith("yfinance") and type(current).__name__ in _TRANSIENT_YFINANCE:
            return True
        current = current.__cause__ or current.__context__
    # unknown errors are bugs or bad data until proven otherwise, so no blind retries
    return False


def backoff_seconds(retries: int, base: float, cap: float) -> float:
    # exponential with equal jitter: half the delay is fixed, half random, which
    # keeps a floor but still spreads out a herd of retrying workers
    delay = min(cap, base * 2**retries)
    return delay / 2 + random.uniform(0, delay / 2)
