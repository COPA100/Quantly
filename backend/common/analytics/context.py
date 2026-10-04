"""the shared inputs every analyzer reads, built once per analysis run."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from common.models import Price


@dataclass
class AnalysisContext:
    as_of: date
    # parsed csv rows, valued: each has symbol, quantity, purchase_price,
    # current_price and pct_allocation
    positions: list[dict]
    # market value of the whole book
    total: float
    # ticker -> share of total value, duplicates summed. covers every holding,
    # including ones with no price history.
    weights: pd.Series
    # adjusted closes, date index x ticker, inner-joined so every row is a day
    # every priced holding traded. limited to the analysis window.
    prices: pd.DataFrame
    # simple daily returns of `prices`, one row shorter
    returns: pd.DataFrame
    # value-weighted daily return of the book on `returns` dates
    portfolio_returns: pd.Series
    # benchmark daily returns on the same dates (a date the benchmark lacks is dropped)
    benchmark_returns: pd.Series
    # raw bars per ticker inside the analysis window
    history: dict[str, list[Price]]
    # adjusted closes per ticker over everything stored, benchmark included
    # under its own ticker. for analyses that look further back (stress tests).
    full_history: dict[str, pd.Series]
    benchmark_ticker: str
    # db session for analyzers that need extra data, None in pure unit tests
    db: Any = None
    # results of the analyzers that already ran, keyed by result name
    results: dict[str, Any] = field(default_factory=dict)
