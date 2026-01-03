import pandas as pd

# clean CSV file to the symbol and quantity
def parse_portfolio(file_path):

    df = pd.read_csv(file_path, skiprows=2, skipfooter=2)

    symbols = df["Symbol"].tolist()
    quantity = df["Qty (Quantity)"].tolist()
    cost_basis = df["Cost Basis"].tolist()

    purchase_price = []
    for i in range(len(quantity)):
        cost = float(cost_basis[i].replace("$", "").replace(",", ""))
        price = cost / float(quantity[i])
        purchase_price.append(price)

    # return each stock as an object in a list
    positions = []
    for i in range(len(symbols)):
        stock = {
            "symbol": symbols[i],
            "quantity": quantity[i],
            "purchase_price": round(purchase_price[i], 2),
        }

        positions.append(stock)

    return positions

# returns list of symbols
def get_symbols(file_path):

    df = pd.read_csv(file_path, skiprows=2, skipfooter=2)

    symbols = df["Symbol"].tolist()

    return symbols