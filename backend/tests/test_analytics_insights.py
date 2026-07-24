from common.analytics import insights


def test_drawdown_insight_states_the_number():
    text = insights.drawdown_insight(-0.34)
    assert "-34%" in text
    assert "34%" in text


def test_sharpe_insight_compares_to_benchmark():
    text = insights.sharpe_insight(0.4, 0.9)
    assert "0.40" in text
    assert "0.90" in text
    assert "less return" in text


def test_sharpe_insight_without_benchmark():
    assert "1.20" in insights.sharpe_insight(1.2)


def test_beta_insight_direction():
    assert "harder" in insights.beta_insight(1.4)
    assert "softer" in insights.beta_insight(0.6)
    assert "40%" in insights.beta_insight(1.4)


def test_correlation_insight_flags_concentration():
    assert "one bet" in insights.correlation_insight(12, 0.8)


def test_concentration_insight_states_share_and_count():
    text = insights.concentration_insight(0.68, 3)
    assert "68%" in text
    assert "3" in text
