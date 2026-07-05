# run all calculations in this file
def calculate_portfolio_total(portfolio):

    total = 0
    for p in portfolio:
        total += p["quantity"] * p["current_price"]

    return total


def calculate_portfolio_gainloss(portfolio):

    total_cost = 0
    total_value = 0

    for p in portfolio:
        cost = p["quantity"] * p["purchase_price"]
        value = p["quantity"] * p["current_price"]
        total_cost += cost
        total_value += value

    gain_loss = total_value - total_cost
    gain_loss_pct = (gain_loss / total_cost * 100) if total_cost > 0 else 0

    return {
        "gain_loss": round(gain_loss, 2),
        "gain_loss_pct": round(gain_loss_pct, 2),
    }


def calculate_position_gains(portfolio):

    for p in portfolio:
        cost = p["quantity"] * p["purchase_price"]
        value = p["quantity"] * p["current_price"]
        p["gain_loss"] = round(value - cost, 2)
        p["gain_loss_pct"] = round((value - cost) / cost * 100, 2)

    return portfolio


def calculate_position_allocation(portfolio):

    total = calculate_portfolio_total(portfolio)

    if total == 0:
        return portfolio

    for p in portfolio:
        value = p["quantity"] * p["current_price"]

        percentage = value / total
        p["pct_allocation"] = percentage

    return portfolio
