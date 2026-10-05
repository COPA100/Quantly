"""chaos run: upload portfolios, kill the worker while they process, check the outcome.

needs the compose stack up (postgres, redis, s3, worker, beat) and the api
reachable. standard library only, so it runs anywhere docker does.

    python -m scripts.chaos --count 20 --kills 4

the run passes when every portfolio reaches a terminal state and no portfolio
has duplicated or partial analytics rows.
"""

import argparse
import csv
import io
import json
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TERMINAL = {"complete", "failed"}
REPO_ROOT = Path(__file__).resolve().parents[2]


# ---- pure logic, unit tested ----


@dataclass
class Report:
    total: int
    complete: int = 0
    failed: int = 0
    non_terminal: list[int] = field(default_factory=list)
    duplicates: list[tuple[int, str, int]] = field(default_factory=list)
    incomplete: list[int] = field(default_factory=list)
    kills: int = 0
    seconds: float = 0.0
    # a run that never killed a worker proved nothing, so it does not pass
    kills_required: int = 0

    @property
    def ok(self) -> bool:
        broken = self.non_terminal or self.duplicates or self.incomplete
        return not broken and self.kills >= self.kills_required

    def summary(self) -> str:
        return (
            f"chaos {'PASS' if self.ok else 'FAIL'}: portfolios={self.total} "
            f"complete={self.complete} failed={self.failed} "
            f"non_terminal={len(self.non_terminal)} duplicate_rows={len(self.duplicates)} "
            f"incomplete={len(self.incomplete)} kills={self.kills} seconds={self.seconds:.0f}"
        )


def parse_result_rows(text: str) -> list[tuple[int, str, int]]:
    # psql -At -F'|' output: portfolio_id|metric_name|count
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        portfolio_id, metric, count = line.split("|")
        rows.append((int(portfolio_id), metric, int(count)))
    return rows


def evaluate(
    statuses: dict[int, str],
    rows: list[tuple[int, str, int]],
    kills: int = 0,
    seconds: float = 0,
    kills_required: int = 0,
) -> Report:
    report = Report(
        total=len(statuses), kills=kills, seconds=seconds, kills_required=kills_required
    )
    metrics: dict[int, set[str]] = defaultdict(set)
    for portfolio_id, metric, count in rows:
        metrics[portfolio_id].add(metric)
        if count != 1:
            report.duplicates.append((portfolio_id, metric, count))

    complete_sets = []
    for portfolio_id, status in sorted(statuses.items()):
        if status == "complete":
            report.complete += 1
            complete_sets.append((portfolio_id, metrics[portfolio_id]))
        elif status == "failed":
            report.failed += 1
        else:
            report.non_terminal.append(portfolio_id)

    # every finished run computes the same metric set for the same kind of input,
    # so a complete portfolio missing metrics other completes have is a partial write
    expected = set().union(*(m for _, m in complete_sets)) if complete_sets else set()
    for portfolio_id, got in complete_sets:
        if not got or got != expected:
            report.incomplete.append(portfolio_id)
    return report


def vary_book(csv_bytes: bytes, i: int) -> bytes:
    # nudge the first holding's share count so every upload is a different book.
    # identical books hit the analytics cache and finish before a worker dies.
    lines = csv_bytes.decode().splitlines()
    header = next(n for n, line in enumerate(lines) if "Qty (Quantity)" in line)
    columns = next(csv.reader([lines[header]]))
    qty = columns.index("Qty (Quantity)")
    row = next(csv.reader([lines[header + 1]]))
    row[qty] = f"{float(row[qty]) + i / 1000:g}"
    out = io.StringIO()
    csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="").writerow(row)
    lines[header + 1] = out.getvalue()
    return ("\n".join(lines) + "\n").encode()


def pick_action(rng: random.Random) -> str:
    # kill leaves the container down until restarted, restart bounces it at once
    return rng.choice(["kill", "restart"])


def encode_multipart(filename: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode()
    return (
        head + data + f"\r\n--{boundary}--\r\n".encode(),
        f"multipart/form-data; boundary={boundary}",
    )


# ---- orchestration, needs docker ----


def _request(url: str, method: str = "GET", body=None, headers=None, retry_429: bool = True):
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    while True:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and retry_429:
                time.sleep(float(exc.headers.get("Retry-After", "1")))
                continue
            raise


def _json_post(url: str, payload: dict, headers=None):
    all_headers = {"Content-Type": "application/json", **(headers or {})}
    return _request(url, "POST", json.dumps(payload).encode(), all_headers)


def _compose(args: argparse.Namespace, *cmd: str, check: bool = True) -> str:
    full = ["docker", "compose", "-f", str(args.compose_file), *cmd]
    out = subprocess.run(full, capture_output=True, text=True, check=check)
    return out.stdout


def _wait_for_api(base: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _request(f"{base}/health", retry_429=False)
            return
        except OSError:
            time.sleep(2)
    raise SystemExit(f"api at {base} did not come up")


def _statuses(base: str, headers: dict, ids: set[int]) -> dict[int, str]:
    listed = _request(f"{base}/portfolios", headers=headers)
    return {p["id"]: p["status"] for p in listed if p["id"] in ids}


def _kill_worker_loop(args, rng, stop: threading.Event, counter: list[int]) -> None:
    while not stop.is_set() and counter[0] < args.kills:
        if stop.wait(rng.uniform(args.min_gap, args.max_gap)):
            return
        action = pick_action(rng)
        print(f"chaos: worker {action}", flush=True)
        try:
            if action == "kill":
                _compose(args, "kill", "worker")
                stop.wait(rng.uniform(1, 5))
                _compose(args, "up", "-d", "worker")
            else:
                _compose(args, "restart", "--timeout", "0", "worker")
        except subprocess.CalledProcessError as exc:
            print(f"chaos: docker command failed: {exc.stderr}", file=sys.stderr, flush=True)
            continue
        counter[0] += 1


def _query_rows(args: argparse.Namespace, ids: list[int]) -> list[tuple[int, str, int]]:
    sql = (
        "select portfolio_id, metric_name, count(*) from analytics_results "
        f"where portfolio_id in ({','.join(str(i) for i in ids)}) group by 1, 2"
    )
    out = _compose(
        args, "exec", "-T", "postgres", "psql", "-U", "quantly", "-d", "quantly",
        "-At", "-F", "|", "-c", sql,
    )  # fmt: skip
    return parse_result_rows(out)


def run(args: argparse.Namespace) -> Report:
    rng = random.Random(args.seed)
    base = args.api_url.rstrip("/")
    _wait_for_api(base)

    creds = {"email": f"chaos-{uuid.uuid4().hex[:8]}@example.com", "password": "chaos-pass-123"}
    _json_post(f"{base}/auth/register", creds)
    token = _json_post(f"{base}/auth/login", creds)["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # the killer starts first, so workers die while jobs are in flight
    started = time.monotonic()
    stop = threading.Event()
    kills = [0]
    killer = threading.Thread(target=_kill_worker_loop, args=(args, rng, stop, kills))
    killer.start()

    csv_bytes = Path(args.csv).read_bytes()
    ids: list[int] = []
    for i in range(args.count):
        body, content_type = encode_multipart(f"chaos-{i}.csv", vary_book(csv_bytes, i))
        accepted = _request(
            f"{base}/portfolios", "POST", body, {**auth, "Content-Type": content_type}
        )
        ids.append(accepted["id"])
    print(f"chaos: uploaded {len(ids)} portfolios", flush=True)

    statuses: dict[int, str] = {}
    deadline = started + args.timeout
    try:
        while time.monotonic() < deadline:
            statuses = _statuses(base, auth, set(ids))
            if len(statuses) == len(ids) and all(s in TERMINAL for s in statuses.values()):
                break
            time.sleep(3)
    finally:
        stop.set()
        killer.join()
        # leave the stack running, whatever the last chaos action was
        _compose(args, "up", "-d", "worker", check=False)

    seconds = time.monotonic() - started
    return evaluate(
        statuses,
        _query_rows(args, ids),
        kills=kills[0],
        seconds=seconds,
        kills_required=1 if args.kills > 0 else 0,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=20, help="portfolios to upload")
    parser.add_argument("--kills", type=int, default=4, help="worker kills or restarts")
    parser.add_argument("--timeout", type=float, default=600, help="seconds to wait for terminal")
    parser.add_argument("--min-gap", type=float, default=3)
    parser.add_argument("--max-gap", type=float, default=10)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--csv", default=str(REPO_ROOT / "example_csv" / "ex1.csv"))
    parser.add_argument("--compose-file", default=str(REPO_ROOT / "docker-compose.yml"))
    args = parser.parse_args(argv)

    report = run(args)
    print(report.summary())
    for pid in report.non_terminal:
        print(f"  not terminal: portfolio {pid}")
    for pid, metric, count in report.duplicates:
        print(f"  duplicate rows: portfolio {pid} metric {metric} x{count}")
    for pid in report.incomplete:
        print(f"  incomplete metrics: portfolio {pid}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
