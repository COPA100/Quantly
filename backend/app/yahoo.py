# api docs
# https://ranaroussi.github.io/yfinance/reference/index.html

import yfinance as yf
from csv_reader import investment_names, investments

data = yf.download(investment_names, period="1d", interval="1d")
dataPrices = data["Close"].iloc[-1].to_dict()
print(dataPrices)

total = 0
for sym, qty in investments:
    total += dataPrices[sym] * qty
    print(sym, qty, dataPrices[sym])
print(total)
