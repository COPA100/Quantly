import pytest

# the compiled engine is an optional dependency: skip rather than fail when the
# wheel has not been built (e.g. a lint-only checkout).
engine = pytest.importorskip("engine")


def test_engine_version_is_exposed():
    assert engine.__version__ == "0.1.0"


def test_hello_binding_crosses_the_boundary():
    assert engine.hello() == "quantly engine"
