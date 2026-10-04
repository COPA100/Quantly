import random

from scripts.chaos import encode_multipart, evaluate, parse_result_rows, pick_action

METRICS = ["value", "sharpe"]


def _rows(pid, counts=(1, 1)):
    return [(pid, m, c) for m, c in zip(METRICS, counts, strict=True)]


def test_clean_run_passes():
    statuses = {1: "complete", 2: "complete", 3: "failed"}
    report = evaluate(statuses, _rows(1) + _rows(2), kills=3, seconds=42)
    assert report.ok
    assert (report.complete, report.failed) == (2, 1)
    assert report.summary().startswith("chaos PASS: portfolios=3 complete=2 failed=1")


def test_non_terminal_portfolio_fails_the_run():
    report = evaluate({1: "complete", 2: "processing"}, _rows(1))
    assert not report.ok
    assert report.non_terminal == [2]


def test_duplicate_rows_fail_the_run():
    report = evaluate({1: "complete"}, _rows(1, counts=(2, 1)))
    assert not report.ok
    assert report.duplicates == [(1, "value", 2)]


def test_complete_portfolio_missing_metrics_is_a_partial_write():
    rows = _rows(1) + [(2, "value", 1)]
    report = evaluate({1: "complete", 2: "complete"}, rows)
    assert report.incomplete == [2]
    assert not report.ok


def test_complete_portfolio_without_rows_is_incomplete():
    report = evaluate({1: "complete", 2: "complete"}, _rows(1))
    assert report.incomplete == [2]


def test_failed_portfolios_do_not_need_rows():
    assert evaluate({1: "failed"}, []).ok


def test_parse_psql_output():
    assert parse_result_rows("1|value|1\n1|sharpe|2\n\n") == [(1, "value", 1), (1, "sharpe", 2)]
    assert parse_result_rows("") == []


def test_pick_action_is_seeded_and_bounded():
    picks = {pick_action(random.Random(i)) for i in range(20)}
    assert picks == {"kill", "restart"}
    assert pick_action(random.Random(5)) == pick_action(random.Random(5))


def test_multipart_body_carries_file_and_boundary():
    body, content_type = encode_multipart("a.csv", b"x,y\n1,2\n")
    boundary = content_type.split("boundary=")[1]
    assert body.startswith(f"--{boundary}\r\n".encode())
    assert b'filename="a.csv"' in body and b"x,y\n1,2\n" in body
    assert body.endswith(f"--{boundary}--\r\n".encode())
