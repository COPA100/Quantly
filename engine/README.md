# Quantly C++ engine

Compute-heavy risk metrics implemented in C++ and exposed to Python via
[pybind11](https://pybind11.readthedocs.io/). Imported by the Celery worker; a
pure-Python fallback keeps the worker running if the compiled module is absent.

It targets the operations where C++ genuinely wins over vectorized NumPy —
path-dependent loops that don't vectorize cleanly (rolling drawdown/duration,
Monte Carlo VaR) rather than matrix math that already calls into BLAS. See
`/benchmarks` for the head-to-head numbers.

## Layout

```
engine/
  CMakeLists.txt      cmake build (pybind11_add_module)
  pyproject.toml      scikit-build-core wheel build
  src/cpp/            C++ sources + pybind11 bindings
  src/engine/         Python package that wraps the extension
  tests/              C++ unit tests (Catch2)
```

## Build & install

```sh
pip install ./engine
```

On Linux the stock `gcc`/`clang` toolchain is used. On Windows without MSVC, the
build uses the MSYS2 **ucrt64** GCC and statically links the runtime so the
`.pyd` loads under a stock CPython:

```sh
CC=gcc CXX=g++ CMAKE_GENERATOR=Ninja pip install ./engine --no-build-isolation
```

## Threads, determinism and SIMD

- `monte_carlo_var(..., threads=None)` and `correlation_matrix(data, threads=None)`
  use all hardware threads by default; `0` or `1` runs on the calling thread. The
  GIL is released during compute.
- Monte Carlo paths are split into fixed blocks of 1024. Each block draws from its
  own Philox4x32-10 counter-based stream keyed by `(seed, block)`, so the result is
  bit-identical for any thread count. (A shared sequential RNG like `mt19937_64`
  could not be split across threads reproducibly.)
- `monte_carlo_var_qmc` is a Sobol quasi-Monte Carlo variant (Joe-Kuo direction
  numbers, up to 30 days, seeded random digital shift, Helmert-rotated shocks).
- The correlation kernel standardizes rows once, then runs a tiled, packed
  dot-product pass. On x86-64 an AVX2+FMA micro-kernel is picked at runtime
  (`QUANTLY_DISABLE_AVX2=1` forces the portable path); other targets use the
  portable kernel. The Monte Carlo loop is not hand-vectorized: libm `log`/`sin`/`cos`
  dominate it and an AVX2 path would need its own vector math.
- `cmake` builds default to `Release`.
