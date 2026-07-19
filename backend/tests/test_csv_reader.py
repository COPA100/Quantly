import pytest

from common.csv_reader import parse_portfolio

# mirrors the brokerage export shape: banner line, blank line, header,
# holding rows, then cash + account-total footer rows.
EXPORT = """\
"Positions for account Individual ...123 as of 04:00 PM ET, 2026/07/18"

"Symbol","Description","Qty (Quantity)","Price","Cost Basis","Security Type"
"AAPL","APPLE INC","10","$210.00","$1,500.00","Equity"
"MSFT","MICROSOFT CORP","2.5","$500.00","$1,000.00","Equity"
"TSLA","TESLA INC","0.018","$271.85","$5.30","Equity"
"Cash & Cash Investments","--","--","--","--","Cash and Money Market"
"Account Total","","--","--","$2,505.30","--"
"""


@pytest.fixture
def export_csv(tmp_path):
    path = tmp_path / "positions.csv"
    path.write_text(EXPORT)
    return path


def test_parses_one_position_per_holding_row(export_csv):
    positions = parse_portfolio(export_csv)
    assert [p["symbol"] for p in positions] == ["AAPL", "MSFT", "TSLA"]


def test_skips_banner_and_footer_rows(export_csv):
    symbols = [p["symbol"] for p in parse_portfolio(export_csv)]
    assert "Cash & Cash Investments" not in symbols
    assert "Account Total" not in symbols


def test_quantities_are_numeric(export_csv):
    quantities = [p["quantity"] for p in parse_portfolio(export_csv)]
    assert quantities == [10, 2.5, 0.018]


def test_purchase_price_derived_from_cost_basis(export_csv):
    # dollar signs and thousands separators in Cost Basis are stripped,
    # then cost is divided by quantity and rounded to cents
    positions = parse_portfolio(export_csv)
    assert positions[0]["purchase_price"] == 150.00
    assert positions[1]["purchase_price"] == 400.00
    assert positions[2]["purchase_price"] == round(5.30 / 0.018, 2)
