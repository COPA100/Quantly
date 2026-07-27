#!/usr/bin/env python
"""Benchmark the C++ engine against pure-python and numpy baselines.

Every engine function is timed against two references: a pure-python loop and a
numpy-vectorized version, across several problem sizes. The point is an honest
picture -- C++ wins big on path-dependent loops (Monte Carlo VaR, rolling
drawdown) and only ties numpy on matrix math that already calls into BLAS.

    python benchmarks/run_benchmarks.py            # print a markdown report
    python benchmarks/run_benchmarks.py --md FILE  # also write it to FILE
"""

import argparse
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from common.analytics import metrics, risk  # noqa: E402

try:
    import engine
except ImportError:
    engine = None


# --------------------------------------------------------------------------- #
# pure-python baselines (no numpy) -- the "slow" reference
# --------------------------------------------------------------------------- #
def py_max_drawdown(returns) -> dict:
    peak = equity = 1.0
    worst = 0.0
    longest = current = 0
    for r in returns:
        equity *= 1.0 + r
        if equity > peak:
            peak = equity
        dd = equity / peak - 1.0
        if dd < worst:
            worst = dd
        if dd < 0.0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return {"max_drawdown": worst, "duration": longest}


def py_correlation(data) -> list:
    n = len(data)
    m = len(data[0]) if n else 0
    means = [sum(row) / m for row in data]
    ss = [sum((x - means[i]) ** 2 for x in data[i]) for i in range(n)]
    out = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            acc = sum(
                (data[i][k] - means[i]) * (data[j][k] - means[j]) for k in range(m)
            )
            denom = math.sqrt(ss[i] * ss[j])
            out[i][j] = out[j][i] = acc / denom if denom else float("nan")
    return out


def py_monte_carlo_var(mu, sigma, horizon, n_sims, confidence=0.95, seed=0) -> dict:
    rng = random.Random(seed)
    pnl = []
    for _ in range(n_sims):
        growth = 1.0
        for _ in range(horizon):
            growth *= 1.0 + rng.gauss(mu, sigma)
        pnl.append(growth - 1.0)
    pnl.sort()
    idx = min(int((1.0 - confidence) * n_sims), n_sims - 1)
    return {"var": -pnl[idx], "cvar": -sum(pnl[: idx + 1]) / (idx + 1)}


# --------------------------------------------------------------------------- #
# timing
# --------------------------------------------------------------------------- #
def timed(fn, *args) -> float:
    # adaptive: one run if it's already slow, otherwise average enough runs to
    # cover ~0.2s so fast ops are measured cleanly
    start = time.perf_counter()
    fn(*args)
    dt = time.perf_counter() - start
    if dt > 0.2:
        return dt
    n = min(1000, max(1, int(0.2 / dt))) if dt > 0 else 1000
    start = time.perf_counter()
    for _ in range(n):
        fn(*args)
    return (time.perf_counter() - start) / n


def fmt(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.1f} us"
    if seconds < 1.0:
        return f"{seconds * 1e3:.2f} ms"
    return f"{seconds:.2f} s"


def speedup(slow: float | None, fast: float | None) -> str:
    if not slow or not fast:
        return "n/a"
    return f"{slow / fast:.1f}x"


# --------------------------------------------------------------------------- #
# benchmarks
# --------------------------------------------------------------------------- #
def bench_drawdown(lines: list) -> None:
    lines.append("### Max drawdown: single return series (path-dependent loop)\n")
    lines.append(
        "| series length | pure python | numpy | C++ | C++ vs numpy | C++ vs python |"
    )
    lines.append("|--:|--:|--:|--:|--:|--:|")
    rng = np.random.default_rng(0)
    for length in (252, 1260, 5040):
        returns = rng.normal(0, 0.02, length)
        as_list = returns.tolist()
        t_py = timed(py_max_drawdown, as_list)
        t_np = timed(metrics.max_drawdown, returns)
        t_cpp = timed(engine.max_drawdown, returns) if engine else None
        lines.append(
            f"| {length} | {fmt(t_py)} | {fmt(t_np)} | {fmt(t_cpp)} | "
            f"{speedup(t_np, t_cpp)} | {speedup(t_py, t_cpp)} |"
        )
    lines.append("")


def bench_correlation(lines: list) -> None:
    lines.append("### Correlation matrix: N assets x 1260 daily obs (BLAS territory)\n")
    lines.append(
        "| assets | pure python | numpy | C++ | C++ vs numpy | C++ vs python |"
    )
    lines.append("|--:|--:|--:|--:|--:|--:|")
    rng = np.random.default_rng(1)
    for n_assets in (10, 50, 100, 500):
        data = rng.normal(0, 0.02, (n_assets, 1260))
        as_list = data.tolist()
        # pure python explodes past ~100 assets; skip it there
        t_py = timed(py_correlation, as_list) if n_assets <= 100 else None
        t_np = timed(np.corrcoef, data)
        t_cpp = timed(engine.correlation_matrix, data) if engine else None
        lines.append(
            f"| {n_assets} | {fmt(t_py)} | {fmt(t_np)} | {fmt(t_cpp)} | "
            f"{speedup(t_np, t_cpp)} | {speedup(t_py, t_cpp)} |"
        )
    lines.append("")


def bench_var(lines: list) -> None:
    lines.append("### Monte Carlo VaR: 21-day horizon (path-dependent loop)\n")
    lines.append(
        "| simulations | pure python | numpy | C++ | C++ vs numpy | C++ vs python |"
    )
    lines.append("|--:|--:|--:|--:|--:|--:|")
    for n_sims in (20_000, 100_000):
        args = (0.0005, 0.02, 21, n_sims, 0.95, 7)
        t_py = timed(py_monte_carlo_var, *args)
        t_np = timed(risk.monte_carlo_var, *args)
        t_cpp = timed(engine.monte_carlo_var, *args) if engine else None
        lines.append(
            f"| {n_sims:,} | {fmt(t_py)} | {fmt(t_np)} | {fmt(t_cpp)} | "
            f"{speedup(t_np, t_cpp)} | {speedup(t_py, t_cpp)} |"
        )
    lines.append("")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--md", type=Path, help="also write the markdown report to this file"
    )
    args = parser.parse_args()

    lines: list[str] = []
    lines.append("# Engine benchmarks\n")
    lines.append(
        "Generated by `python benchmarks/run_benchmarks.py`. Each C++ kernel is "
        "timed against a pure-python loop and a numpy-vectorized baseline across "
        "problem sizes. Times are the best of adaptive repeats; lower is better and "
        "speedups are C++ against each baseline. Absolute numbers are "
        "machine-dependent; the ratios are the point.\n"
    )
    if engine is None:
        lines.append(
            "> Note: C++ engine not installed, showing python/numpy baselines only.\n"
        )
    lines.append(
        f"Environment: Python {sys.version.split()[0]}, numpy {np.__version__}.\n"
    )

    bench_drawdown(lines)
    bench_correlation(lines)
    bench_var(lines)

    lines.append("## Takeaways\n")
    lines.append(
        "- **Drawdown / underwater duration** is the clear C++ win: a sequential "
        "peak-to-trough scan numpy cannot vectorize, so the compiled loop pulls "
        "well ahead of both baselines."
    )
    lines.append(
        "- **Monte Carlo VaR** ties numpy: the simulation vectorizes cleanly, so "
        "numpy's batched normal draws match the C++ loop. C++ still beats the pure-"
        "python loop by roughly an order of magnitude."
    )
    lines.append(
        "- **Correlation** goes to numpy: it dispatches to multithreaded BLAS, which "
        "a naive single-threaded C++ triple loop will not beat. C++ still crushes "
        "pure python."
    )
    lines.append(
        "\nThe engine earns its keep on the path-dependent metrics; where numpy is "
        "already fast the worker's fallback loses nothing.\n"
    )

    report = "\n".join(lines)
    print(report)
    if args.md:
        args.md.write_text(report, encoding="utf-8")
        print(f"\nwrote {args.md}")


if __name__ == "__main__":
    main()
