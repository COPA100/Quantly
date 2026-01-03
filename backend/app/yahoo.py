# api docs
# https://ranaroussi.github.io/yfinance/reference/index.html

import yfinance as yf
from csv_reader import parse_portfolio, get_symbols

# get the cleaned portfolio and add more important data from yfinance to each stock object in the list
# eventually this needs to be cached to db for historical data (i do this later)
def fetch_current_prices(file_path):

    portfolio = parse_portfolio(file_path)

    symbols = get_symbols(file_path)
    data = yf.download(symbols, period="1d", interval="1d")

    prices = data["Close"].iloc[-1].to_dict()
    
    for position in portfolio:
        symbol = position["symbol"]
        if symbol in prices:
            position["current_price"] = round(prices[symbol], 2)
        else:
            position["current_price"] = None

    print(portfolio)

fetch_current_prices("example_csv/ex1.csv")