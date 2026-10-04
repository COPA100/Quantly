#!/usr/bin/env python
"""Compare benchmark speed ratios against the committed baseline.

    python benchmarks/compare_baseline.py run1.json [run2.json ...]
    python benchmarks/compare_baseline.py run1.json --update     # rewrite baseline

Ratios are numpy time / C++ time (higher is better). Every key in baseline.json
is gated: the run fails if its ratio drops more than --tolerance (default 15%)
below the baseline. With several run files the per-key median is compared, which
absorbs one-off noise on shared CI machines. Only single-thread C++ ratios are
gated, so the result does not depend on how many cores the machine has.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

BASELINE = Path(__file__).resolve().parent / "baseline.json"

GATED = (
    "drawdown_5040",
    "correlation_100_1t",
    "correlation_500_1t",
    "mc_var_20k_1t",
    "mc_var_100k_1t",
    "qmc_var_100k_1t",
)


def load_ratios(paths: list[Path]) -> dict[str, float]:
    runs = [json.loads(p.read_text(encoding="utf-8"))["ratios"] for p in paths]
    keys = set().union(*runs)
    return {k: statistics.median(r[k] for r in runs if k in r) for k in sorted(keys)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "current", nargs="+", type=Path, help="run_benchmarks --json output"
    )
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--tolerance", type=float, default=0.15)
    parser.add_argument(
        "--update",
        action="store_true",
        help="write the current ratios as the new baseline",
    )
    args = parser.parse_args()

    current = load_ratios(args.current)

    if args.update:
        env = json.loads(args.current[0].read_text(encoding="utf-8"))["environment"]
        missing = [k for k in GATED if k not in current]
        if missing:
            print(f"cannot update, run is missing {missing}", file=sys.stderr)
            return 2
        payload = {
            "note": "numpy time / C++ time on one machine; regenerate with "
            "compare_baseline.py --update after an intentional change",
            "environment": env,
            "ratios": {k: round(current[k], 2) for k in GATED},
        }
        args.baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.baseline}")
        return 0

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))["ratios"]
    failed = []
    print(f"{'ratio':<22}{'baseline':>10}{'current':>10}{'change':>10}  status")
    for key, base in baseline.items():
        now = current.get(key)
        if now is None:
            failed.append(key)
            print(f"{key:<22}{base:>10.2f}{'missing':>10}{'':>10}  FAIL")
            continue
        change = now / base - 1.0
        bad = change < -args.tolerance
        if bad:
            failed.append(key)
        print(
            f"{key:<22}{base:>10.2f}{now:>10.2f}{change:>+10.1%}  "
            f"{'FAIL' if bad else 'ok'}"
        )
    if failed:
        print(
            f"\n{len(failed)} ratio(s) regressed more than {args.tolerance:.0%}: "
            + ", ".join(failed),
            file=sys.stderr,
        )
        return 1
    print(f"\nall {len(baseline)} ratios within {args.tolerance:.0%} of baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
