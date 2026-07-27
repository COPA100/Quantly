#include <pybind11/pybind11.h>

namespace py = pybind11;

// entry point for the `engine._engine` extension module. individual metrics are
// registered from their own translation units as they are added.
PYBIND11_MODULE(_engine, m) {
    m.doc() = "Quantly C++ analytics engine";
    m.attr("__version__") = "0.1.0";
}
