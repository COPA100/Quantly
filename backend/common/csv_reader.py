import pandas as pd

REQUIRED_COLUMNS = ("Symbol", "Qty (Quantity)", "Cost Basis")


class CSVValidationError(ValueError):
    """raised when an uploaded file is not a portfolio export we can read."""


# clean CSV file to the symbol and quantity
def parse_portfolio(file_path):

    try:
        df = pd.read_csv(file_path, skiprows=2, skipfooter=2)
    except (pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        raise CSVValidationError("file is not a readable csv") from exc

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise CSVValidationError(f"missing required columns: {', '.join(missing)}")

    symbols = df["Symbol"].tolist()
    quantity = df["Qty (Quantity)"].tolist()
    cost_basis = df["Cost Basis"].tolist()

    # bad numbers (blank cells, text, zero quantity) mean this isn't a real export
    try:
        purchase_price = []
        for i in range(len(quantity)):
            cost = float(str(cost_basis[i]).replace("$", "").replace(",", ""))
            price = cost / float(quantity[i])
            purchase_price.append(price)
    except (ValueError, ZeroDivisionError) as exc:
        raise CSVValidationError("could not read shares or cost basis values") from exc

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
