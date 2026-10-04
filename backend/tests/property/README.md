# Property tests

Hypothesis tests for invariants that should hold for any input, not just the fixed
fixtures in `tests/`.

```bash
cd backend
pytest tests/property                            # dev profile, 40 examples per test
HYPOTHESIS_PROFILE=ci pytest tests/property      # 150 examples, fixed seed
```

Profiles live in `conftest.py`. CI uses `ci` so a red build reproduces locally with the
same command. A failing example is saved under `.hypothesis/` and replayed first on the
next run.

## What is covered

| File | Properties |
|---|---|
| `test_metrics_properties.py` | correlation bounded, symmetric, unit diagonal (numpy and the C++ kernel); drawdown in [-1, 0] with matching duration; volatility ignores a constant shift and scales linearly; Sharpe scale invariance and shift behaviour; beta of a series against itself is 1; Monte Carlo VaR and CVaR are monotone in confidence |
| `test_pipeline_properties.py` | CSV row order does not change the analytics or the cache digest; dropping a day from one ticker never misaligns the returns; `aligned_prices` keeps exactly the shared dates |

The pipeline tests run on the numpy path (the engine is patched out) so results do not
depend on whether the wheel is installed. Properties that compare numpy and C++ skip
when the wheel is missing.

## Adding properties for a new analyzer

1. Pick invariants a reader can state in a sentence: a bound, a symmetry, a monotone
   relationship, an invariance under a transform of the input. Avoid re-deriving the
   formula, that only tests the copy.
2. Build inputs with `strategies.py` (`return_series`, `return_matrix`). Keep daily
   returns inside the generators' range so equity curves stay positive. Use
   `has_spread` or `assume` to skip flat series, which the metrics return 0 for on
   purpose.
3. For an analyzer, drive it through `build_context` and `run_analyzers` as
   `test_pipeline_properties.py` does, then read `results[key]`. If the output depends
   on holding order, canonicalize before comparing (see `_canonical`).
4. Keep examples small (tens of days, a handful of tickers) and do not add a deadline.
   If a property needs a mean or a quantile, use a fixed seed inside the test.
5. If a property fails because of a real bug, keep a minimal non-random regression test
   next to it.
