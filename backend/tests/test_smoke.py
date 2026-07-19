from common.analytics import basic


def test_analytics_helpers_are_importable():
    # smoke test: the analytics module loads and exposes its public helpers.
    # substantive numeric assertions land with the Phase 1 analytics tests.
    for name in (
        "calculate_portfolio_total",
        "calculate_portfolio_gainloss",
        "calculate_position_gains",
        "calculate_position_allocation",
    ):
        assert callable(getattr(basic, name))
