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
