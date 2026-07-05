# api docs
# https://ranaroussi.github.io/yfinance/reference/index.html

import yfinance as yf


# add current prices from yfinance to each stock in the portfolio
def fetch_current_prices(portfolio):

    symbols = [p["symbol"] for p in portfolio]
    data = yf.download(symbols, period="1d", interval="1d")

    prices = data["Close"].iloc[-1].to_dict()

    for position in portfolio:
        symbol = position["symbol"]
        if symbol in prices:
            position["current_price"] = round(prices[symbol], 2)
        else:
            position["current_price"] = None

    return portfolio
