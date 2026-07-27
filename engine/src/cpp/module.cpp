#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <cstddef>
#include <string>

#include "drawdown.hpp"

namespace py = pybind11;

// smoke binding: proves the pybind11 boundary works end to end.
std::string hello() { return "quantly engine"; }

// accept any float-like sequence (list or ndarray) as a contiguous double array
using DoubleArray = py::array_t<double, py::array::c_style | py::array::forcecast>;

py::dict max_drawdown(DoubleArray returns) {
    auto buf = returns.request();
    const double* ptr = static_cast<const double*>(buf.ptr);
    quantly::Drawdown d = quantly::max_drawdown(ptr, static_cast<std::size_t>(buf.size));
    py::dict out;
    out["max_drawdown"] = d.max_drawdown;
    out["duration"] = d.duration;
    return out;
}

// entry point for the `engine._engine` extension module. the compute lives in
// pybind-free translation units; this file only wires them to python.
PYBIND11_MODULE(_engine, m) {
    m.doc() = "Quantly C++ analytics engine";
    m.attr("__version__") = "0.1.0";
    m.def("hello", &hello, "return a greeting, used to smoke-test the binding");
    m.def("max_drawdown", &max_drawdown, py::arg("returns"),
          "worst peak-to-trough decline and longest underwater duration");
}
