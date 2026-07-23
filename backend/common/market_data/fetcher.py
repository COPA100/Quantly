# yfinance api docs: https://ranaroussi.github.io/yfinance/reference/index.html

import yfinance as yf


def fetch_current_price(ticker: str) -> float | None:
    # latest daily close from yahoo, None when the ticker returns nothing
    hist = yf.Ticker(ticker).history(period="1d", auto_adjust=False)
    if hist.empty:
        return None
    return round(float(hist["Close"].iloc[-1]), 2)
