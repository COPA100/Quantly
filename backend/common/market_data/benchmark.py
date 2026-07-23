from datetime import date

from sqlalchemy.orm import Session

from common.config import get_settings
from common.market_data.history import ensure_history
from common.models import Price


def ensure_benchmark(db: Session, as_of: date | None = None) -> list[Price]:
    # beta needs a market series (spy by default), stored like any other ticker
    return ensure_history(db, get_settings().benchmark_ticker, as_of=as_of)
