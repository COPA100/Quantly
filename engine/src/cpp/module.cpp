#include <pybind11/pybind11.h>

#include <string>

namespace py = pybind11;

// smoke binding: proves the pybind11 boundary works end to end before any real
// metric is wired in.
std::string hello() { return "quantly engine"; }

// entry point for the `engine._engine` extension module. individual metrics are
// registered from their own translation units as they are added.
PYBIND11_MODULE(_engine, m) {
    m.doc() = "Quantly C++ analytics engine";
    m.attr("__version__") = "0.1.0";
    m.def("hello", &hello, "return a greeting, used to smoke-test the binding");
}
