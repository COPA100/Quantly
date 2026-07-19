import pytest

from common.analytics.basic import (
    calculate_portfolio_gainloss,
    calculate_portfolio_total,
    calculate_position_allocation,
    calculate_position_gains,
)


def make_portfolio():
    # cost 1200 (1000 + 200), value 1250 (1100 + 150)
    return [
        {"symbol": "AAA", "quantity": 10, "purchase_price": 100.0, "current_price": 110.0},
        {"symbol": "BBB", "quantity": 5, "purchase_price": 40.0, "current_price": 30.0},
    ]


def test_portfolio_total_sums_position_values():
    assert calculate_portfolio_total(make_portfolio()) == pytest.approx(1250.0)


def test_portfolio_gainloss_absolute_and_percent():
    result = calculate_portfolio_gainloss(make_portfolio())
    assert result["gain_loss"] == pytest.approx(50.0)
    assert result["gain_loss_pct"] == pytest.approx(4.17)  # 50 / 1200, rounded to 2 dp


def test_portfolio_gainloss_zero_cost_reports_zero_percent():
    free_shares = [{"symbol": "AAA", "quantity": 3, "purchase_price": 0.0, "current_price": 10.0}]
    result = calculate_portfolio_gainloss(free_shares)
    assert result["gain_loss"] == pytest.approx(30.0)
    assert result["gain_loss_pct"] == 0


def test_position_gains_added_per_position():
    positions = calculate_position_gains(make_portfolio())
    assert positions[0]["gain_loss"] == pytest.approx(100.0)
    assert positions[0]["gain_loss_pct"] == pytest.approx(10.0)
    assert positions[1]["gain_loss"] == pytest.approx(-50.0)
    assert positions[1]["gain_loss_pct"] == pytest.approx(-25.0)


def test_position_allocation_fractions_sum_to_one():
    positions = calculate_position_allocation(make_portfolio())
    assert positions[0]["pct_allocation"] == pytest.approx(1100 / 1250)
    assert positions[1]["pct_allocation"] == pytest.approx(150 / 1250)
    assert sum(p["pct_allocation"] for p in positions) == pytest.approx(1.0)


def test_position_allocation_zero_total_leaves_positions_unchanged():
    worthless = [{"symbol": "AAA", "quantity": 4, "purchase_price": 5.0, "current_price": 0.0}]
    positions = calculate_position_allocation(worthless)
    assert "pct_allocation" not in positions[0]
