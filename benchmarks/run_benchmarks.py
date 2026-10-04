#!/usr/bin/env python
"""Benchmark the C++ engine against pure-python and numpy baselines.

Every engine function is timed against a numpy-vectorized version (and, in the
full run, a pure-python loop) across several problem sizes. The point is an
honest picture: C++ wins big on path-dependent loops (Monte Carlo VaR, rolling
drawdown) and only competes with numpy on matrix math that already calls BLAS.

    python benchmarks/run_benchmarks.py                    # markdown report
    python benchmarks/run_benchmarks.py --md FILE          # also write it
    python benchmarks/run_benchmarks.py --json out.json    # machine-readable
    python benchmarks/run_benchmarks.py --quick --json out.json   # CI mode

Timings are the median of several repeats (each repeat averages enough calls to
cover ~0.1 s). The speed ratios written to JSON are numpy time / C++ time, so
they are comparable across machines far better than absolute times. The gated
ratios use the single-thread C++ path, which does not depend on core count; see
`compare_baseline.py`.
"""

import argparse
import json
import math
import os
import platform
import random
import statistics
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

MC_ARGS = (0.0005, 0.02, 21)  # mu, sigma, horizon


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
def timed(fn, *args, repeats: int = 7, budget: float = 0.1) -> float:
    """Median seconds per call over `repeats` samples.

    Each sample averages enough back-to-back calls to cover `budget` seconds, so
    microsecond kernels are measured cleanly; slow calls are sampled one by one.
    """
    fn(*args)  # warm caches, allocators, thread machinery
    start = time.perf_counter()
    fn(*args)
    dt = time.perf_counter() - start
    inner = 1 if dt >= budget else min(2000, max(1, int(budget / max(dt, 1e-9))))
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(inner):
            fn(*args)
        samples.append((time.perf_counter() - start) / inner)
    return statistics.median(samples)


def fmt(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.1f} us"
    if seconds < 1.0:
        return f"{seconds * 1e3:.2f} ms"
    return f"{seconds:.2f} s"


def ratio(slow: float | None, fast: float | None) -> float | None:
    if not slow or not fast:
        return None
    return slow / fast


def fx(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}x"


# --------------------------------------------------------------------------- #
# benchmarks. each returns (markdown lines, result rows); ratios are
# numpy-time / cpp-time, so higher is better for C++
# --------------------------------------------------------------------------- #
def bench_drawdown(quick: bool, ratios: dict) -> tuple[list, list]:
    lines = ["### Max drawdown: single return series (path-dependent loop)\n"]
    lines.append(
        "| series length | pure python | numpy | C++ | C++ vs numpy | C++ vs python |"
    )
    lines.append("|--:|--:|--:|--:|--:|--:|")
    rows = []
    rng = np.random.default_rng(0)
    for length in (252, 1260, 5040):
        returns = rng.normal(0, 0.02, length)
        t_py = None if quick else timed(py_max_drawdown, returns.tolist(), repeats=3)
        t_np = timed(metrics.max_drawdown, returns)
        t_cpp = timed(engine.max_drawdown, returns) if engine else None
        r_np, r_py = ratio(t_np, t_cpp), ratio(t_py, t_cpp)
        ratios[f"drawdown_{length}"] = r_np
        rows.append(
            {
                "kernel": "drawdown",
                "size": length,
                "seconds": {"python": t_py, "numpy": t_np, "cpp": t_cpp},
            }
        )
        lines.append(
            f"| {length} | {fmt(t_py)} | {fmt(t_np)} | {fmt(t_cpp)} | "
            f"{fx(r_np)} | {fx(r_py)} |"
        )
    lines.append("")
    return lines, rows


def bench_correlation(quick: bool, ratios: dict) -> tuple[list, list]:
    lines = ["### Correlation matrix: N assets x 1260 daily obs (BLAS territory)\n"]
    lines.append(
        "| assets | pure python | numpy (BLAS) | C++ 1 thread | C++ all threads "
        "| 1 thread vs numpy | all threads vs numpy |"
    )
    lines.append("|--:|--:|--:|--:|--:|--:|--:|")
    rows = []
    rng = np.random.default_rng(1)
    for n_assets in (10, 50, 100, 500):
        data = rng.normal(0, 0.02, (n_assets, 1260))
        # pure python explodes past ~100 assets; skip it there
        t_py = None
        if not quick and n_assets <= 100:
            t_py = timed(py_correlation, data.tolist(), repeats=1)
        t_np = timed(np.corrcoef, data)
        t_1 = timed(engine.correlation_matrix, data, 1) if engine else None
        t_n = timed(engine.correlation_matrix, data) if engine else None
        ratios[f"correlation_{n_assets}_1t"] = ratio(t_np, t_1)
        ratios[f"correlation_{n_assets}_auto"] = ratio(t_np, t_n)
        rows.append(
            {
                "kernel": "correlation",
                "size": n_assets,
                "seconds": {
                    "python": t_py,
                    "numpy": t_np,
                    "cpp_1t": t_1,
                    "cpp_auto": t_n,
                },
            }
        )
        lines.append(
            f"| {n_assets} | {fmt(t_py)} | {fmt(t_np)} | {fmt(t_1)} | {fmt(t_n)} | "
            f"{fx(ratio(t_np, t_1))} | {fx(ratio(t_np, t_n))} |"
        )
    lines.append("")
    return lines, rows


def bench_var(quick: bool, ratios: dict) -> tuple[list, list]:
    lines = ["### Monte Carlo VaR: 21-day horizon (path-dependent loop)\n"]
    lines.append(
        "| simulations | pure python | numpy | C++ 1 thread | C++ all threads "
        "| QMC 1 thread | 1 thread vs numpy | all threads vs numpy |"
    )
    lines.append("|--:|--:|--:|--:|--:|--:|--:|--:|")
    rows = []
    for n_sims in (20_000, 100_000):
        args = (*MC_ARGS, n_sims, 0.95, 7)
        t_py = None if quick else timed(py_monte_carlo_var, *args, repeats=1)
        t_np = timed(risk.monte_carlo_var, *args)
        t_1 = timed(engine.monte_carlo_var, *args, 1) if engine else None
        t_n = timed(engine.monte_carlo_var, *args) if engine else None
        t_q = timed(engine.monte_carlo_var_qmc, *args, 1) if engine else None
        key = f"{n_sims // 1000}k"
        ratios[f"mc_var_{key}_1t"] = ratio(t_np, t_1)
        ratios[f"mc_var_{key}_auto"] = ratio(t_np, t_n)
        ratios[f"qmc_var_{key}_1t"] = ratio(t_np, t_q)
        rows.append(
            {
                "kernel": "monte_carlo_var",
                "size": n_sims,
                "seconds": {
                    "python": t_py,
                    "numpy": t_np,
                    "cpp_1t": t_1,
                    "cpp_auto": t_n,
                    "qmc_1t": t_q,
                },
            }
        )
        lines.append(
            f"| {n_sims:,} | {fmt(t_py)} | {fmt(t_np)} | {fmt(t_1)} | {fmt(t_n)} | "
            f"{fmt(t_q)} | {fx(ratio(t_np, t_1))} | {fx(ratio(t_np, t_n))} |"
        )
    lines.append("")
    return lines, rows


def bench_scaling(ratios: dict) -> tuple[list, list]:
    """MC VaR time against thread count, to show scaling and its limits."""
    lines = ["### Monte Carlo VaR thread scaling: 1,000,000 paths x 21 days\n"]
    lines.append("| threads | time | speedup vs 1 thread |")
    lines.append("|--:|--:|--:|")
    rows = []
    hw = engine.hardware_threads()
    counts = sorted({1, 2, 4, 8, hw // 2, hw} - {0})
    base = None
    args = (*MC_ARGS, 1_000_000, 0.95, 7)
    for t in counts:
        secs = timed(engine.monte_carlo_var, *args, t, repeats=3, budget=0.05)
        base = base or secs
        rows.append({"threads": t, "seconds": secs, "speedup": base / secs})
        lines.append(f"| {t} | {fmt(secs)} | {base / secs:.1f}x |")
    lines.append("")
    return lines, rows


def mc_error_study(quick: bool) -> tuple[list, dict]:
    """RMS error of the 95% VaR estimate against a high-n reference, MC vs QMC."""
    n_ref = 1 << 22
    reps = 8 if quick else 16
    ref = statistics.fmean(
        engine.monte_carlo_var_qmc(*MC_ARGS, n_ref, 0.95, 1000 + s)["var"]
        for s in range(4)
    )
    sizes = [1 << k for k in range(10, 19, 2)]
    out = {"reference_var": ref, "reference_n": n_ref, "replicates": reps, "points": []}
    lines = [
        "### Convergence: 95% VaR error vs simulations (21-day horizon)\n",
        f"RMS error over {reps} independent seeds against a reference VaR of "
        f"{ref:.6f} (QMC, {n_ref:,} paths, mean of 4 shifts). Lower is better.\n",
        "| simulations | MC rms error | QMC rms error | QMC advantage |",
        "|--:|--:|--:|--:|",
    ]
    for n in sizes:
        e_mc = math.sqrt(
            statistics.fmean(
                (engine.monte_carlo_var(*MC_ARGS, n, 0.95, s)["var"] - ref) ** 2
                for s in range(reps)
            )
        )
        e_q = math.sqrt(
            statistics.fmean(
                (engine.monte_carlo_var_qmc(*MC_ARGS, n, 0.95, s)["var"] - ref) ** 2
                for s in range(reps)
            )
        )
        out["points"].append({"n": n, "mc_rmse": e_mc, "qmc_rmse": e_q})
        lines.append(f"| {n:,} | {e_mc:.2e} | {e_q:.2e} | {e_mc / e_q:.1f}x |")

    def slope(key):
        xs = [math.log(p["n"]) for p in out["points"]]
        ys = [math.log(p[key]) for p in out["points"]]
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum(
            (x - mx) ** 2 for x in xs
        )

    out["mc_slope"], out["qmc_slope"] = slope("mc_rmse"), slope("qmc_rmse")
    lines.append(
        f"\nFitted log-log slope: MC {out['mc_slope']:.2f} (theory -0.50), "
        f"QMC {out['qmc_slope']:.2f}.\n"
    )
    return lines, out


def cpu_name() -> str:
    name = platform.processor()
    if sys.platform.startswith("win"):
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    elif os.path.exists("/proc/cpuinfo"):
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                    break
    return name or "unknown cpu"


def environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "platform": platform.platform(),
        "cpu": cpu_name(),
        "logical_cpus": os.cpu_count(),
        "engine_threads": engine.hardware_threads() if engine else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--md", type=Path, help="also write the markdown report to this file"
    )
    parser.add_argument("--json", type=Path, help="write machine-readable results here")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="skip the pure-python baselines and the slow studies (CI mode)",
    )
    args = parser.parse_args()

    env = environment()
    ratios: dict[str, float | None] = {}
    results: dict = {}
    lines: list[str] = ["# Engine benchmarks\n"]
    lines.append(
        "Generated by `python benchmarks/run_benchmarks.py`. Each C++ kernel is "
        "timed against a numpy-vectorized baseline (and a pure-python loop) across "
        "problem sizes. Times are medians of repeated runs; lower is better. "
        "Ratios are numpy time divided by C++ time, so above 1x means C++ is "
        "faster. Absolute numbers are machine-dependent; the ratios are the "
        "point.\n"
    )
    if engine is None:
        lines.append(
            "> Note: C++ engine not installed, showing python/numpy baselines only.\n"
        )
    lines.append(
        f"Environment: {env['cpu']}, {env['logical_cpus']} logical CPUs "
        f"({env['engine_threads']} engine threads), {env['platform']}, "
        f"Python {env['python']}, numpy {env['numpy']}.\n"
    )

    for name, fn in (
        ("drawdown", bench_drawdown),
        ("correlation", bench_correlation),
        ("monte_carlo_var", bench_var),
    ):
        block, rows = fn(args.quick, ratios)
        lines += block
        results[name] = rows

    if engine and not args.quick:
        block, rows = bench_scaling(ratios)
        lines += block
        results["var_thread_scaling"] = rows
        block, study = mc_error_study(args.quick)
        lines += block
        results["convergence"] = study

    lines.append("## Takeaways\n")
    lines += TAKEAWAYS

    report = "\n".join(lines)
    print(report)
    if args.md:
        args.md.write_text(report, encoding="utf-8")
        print(f"\nwrote {args.md}")
    if args.json:
        payload = {
            "environment": env,
            "quick": args.quick,
            "ratios": {k: v for k, v in ratios.items() if v is not None},
            "results": results,
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")


TAKEAWAYS: list[str] = [
    "- **Drawdown / underwater duration** is the clear C++ win: a sequential "
    "peak-to-trough scan numpy cannot vectorize, so the compiled loop pulls "
    "well ahead of both baselines (20x to 45x over numpy).",
    "- **Monte Carlo VaR** on a single thread is a tie with numpy at best: "
    "numpy's batched ziggurat normals are as fast per draw as the C++ "
    "Philox + Box-Muller loop. The win is parallelism: paths are split into "
    "fixed blocks with one counter-based stream each, so all cores help and the "
    "answer is bit-identical for any thread count. Scaling is sublinear "
    "(hybrid cores, shared memory bandwidth, the serial quantile step).",
    "- **QMC** reaches the same VaR error with roughly an order of magnitude "
    "fewer paths on this smooth 21-day problem (Sobol points on a Helmert "
    "rotation of the shocks). Plain MC follows the expected n^-1/2 rate.",
    "- **Correlation** still goes to numpy. One thread of the tiled kernel loses "
    "to multithreaded BLAS (0.1x to 0.5x for 50+ assets) even with the AVX2 "
    "micro-kernel; threads close most of the gap at 500 assets. It is still much "
    "faster than the old naive loop and far ahead of pure python, but it is not "
    "a reason to prefer C++ over BLAS.",
    "\nSingle-thread ratios are what CI gates (`compare_baseline.py`), since they "
    "do not depend on core count. Treat any one run on a busy machine with "
    "suspicion: numpy and C++ timings move together but not perfectly.\n",
]

if __name__ == "__main__":
    main()
