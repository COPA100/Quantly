"""fama-french daily factors from ken french's data library, kept in factor_returns."""

import io
import logging
import zipfile
from datetime import UTC, date, datetime, timedelta

import requests
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from common.db import insert_ignore
from common.models import FactorFetch, FactorReturn

logger = logging.getLogger(__name__)

BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = (
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "F-F_Momentum_Factor_daily_CSV.zip",
)
COLUMNS = ("mkt_rf", "smb", "hml", "rmw", "cma", "mom", "rf")

# a successful refresh is good for a week, a failed one is retried sooner
REFRESH_AFTER = timedelta(days=7)
RETRY_AFTER = timedelta(hours=1)
SOURCE = "french"
REQUEST_TIMEOUT = 30
# french marks a missing observation with -99.99 (percent)
MISSING = -99.0


def _column_name(raw: str) -> str:
    return raw.strip().lower().replace("-", "_")


def _is_number(raw: str) -> bool:
    try:
        float(raw)
    except ValueError:
        return False
    return True


def _parse_day(raw: str) -> date | None:
    raw = raw.strip()
    # the annual sections use 4 digit years, only daily rows have 8 digits
    if len(raw) != 8 or not raw.isdigit():
        return None
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
    except ValueError:
        return None


def parse_factor_csv(text: str) -> dict[date, dict[str, float]]:
    # tolerant of the preamble, copyright footer and annual tables around the
    # daily block. values are percent in the file and fractions here.
    rows: dict[date, dict[str, float]] = {}
    columns: list[str] = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        day = _parse_day(parts[0])
        if day is None:
            # a header is a blank first cell followed by names
            if parts[0] == "" and all(p and not _is_number(p) for p in parts[1:]):
                columns = [_column_name(p) for p in parts[1:]]
            continue
        if not columns or len(parts) - 1 != len(columns):
            continue
        try:
            values = [float(p) for p in parts[1:]]
        except ValueError:
            continue
        if any(v <= MISSING for v in values):
            continue
        rows[day] = {c: v / 100.0 for c, v in zip(columns, values, strict=False)}
    return rows


def _unzip_text(payload: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
        return archive.read(name).decode("latin-1")


def merge_factors(*parsed: dict[date, dict[str, float]]) -> list[dict]:
    # days present in every file, as one flat row per day
    if not parsed:
        return []
    days = set(parsed[0]).intersection(*parsed[1:])
    out = []
    for day in sorted(days):
        row: dict = {"date": day}
        for part in parsed:
            row.update(part[day])
        if all(c in row for c in COLUMNS):
            out.append({k: row[k] for k in ("date", *COLUMNS)})
    return out


def fetch_factors() -> list[dict]:
    # raises on network or format errors, ensure_factors is the one that swallows
    parsed = []
    for name in FILES:
        resp = requests.get(BASE_URL + name, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        parsed.append(parse_factor_csv(_unzip_text(resp.content)))
    return merge_factors(*parsed)


def latest_factor_date(db: Session) -> date | None:
    return db.scalar(select(func.max(FactorReturn.date)))


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ensure_factors(db: Session, now: datetime | None = None) -> None:
    # refresh when the last attempt is old enough. never raises: with no network
    # the stored factors stay as they are and the analyzer reports what it has.
    now = now or _utcnow()
    state = db.get(FactorFetch, SOURCE)
    if state is not None:
        wait = REFRESH_AFTER if state.succeeded else RETRY_AFTER
        if now - state.attempted_at < wait:
            return

    try:
        rows = fetch_factors()
        last = latest_factor_date(db)
        # insert only days we do not have yet. another worker may be refreshing
        # at the same moment, so duplicates are skipped rather than fatal.
        insert_ignore(db, FactorReturn, [r for r in rows if last is None or r["date"] > last])
        ok = bool(rows)
    except Exception:
        logger.warning("factor refresh failed, keeping stored data", exc_info=True)
        ok = False

    insert_ignore(db, FactorFetch, [{"source": SOURCE, "attempted_at": now, "succeeded": ok}])
    db.execute(
        update(FactorFetch)
        .where(FactorFetch.source == SOURCE)
        .values(attempted_at=now, succeeded=ok)
    )
    db.flush()
