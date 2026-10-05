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


def test_a_run_without_kills_does_not_pass():
    statuses = {1: "complete"}
    assert not evaluate(statuses, _rows(1), kills=0, kills_required=1).ok
    assert evaluate(statuses, _rows(1), kills=1, kills_required=1).ok


def test_vary_book_makes_each_upload_a_different_book():
    import io
    from pathlib import Path

    from common.csv_reader import parse_portfolio
    from scripts.chaos import vary_book

    raw = (Path(__file__).resolve().parents[2] / "example_csv" / "ex1.csv").read_bytes()
    books = [parse_portfolio(io.BytesIO(vary_book(raw, i))) for i in range(3)]
    first_qty = [b[0]["quantity"] for b in books]
    assert len(set(first_qty)) == 3
    # everything else is untouched
    assert [p["symbol"] for p in books[0]] == [p["symbol"] for p in books[2]]
    assert [p["quantity"] for p in books[0][1:]] == [p["quantity"] for p in books[2][1:]]
