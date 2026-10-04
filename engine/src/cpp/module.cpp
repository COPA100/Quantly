#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <cstddef>
#include <optional>
#include <stdexcept>
#include <thread>
#include <string>

#include "correlation.hpp"
#include "drawdown.hpp"
#include "var.hpp"

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

// (n_assets x n_obs) -> (n_assets x n_assets)
static void check_2d(const py::buffer_info& buf, const char* name) {
    if (buf.ndim != 2) {
        throw std::invalid_argument(std::string(name) +
                                    " expects a 2d array (assets x observations)");
    }
}

// threads: None = all hardware threads, 0 or 1 = single thread
static int resolve(std::optional<int> threads) { return threads ? *threads : -1; }

py::array_t<double> correlation_matrix(DoubleArray data, std::optional<int> threads) {
    auto buf = data.request();
    check_2d(buf, "correlation_matrix");
    auto rows = static_cast<std::size_t>(buf.shape[0]);
    auto cols = static_cast<std::size_t>(buf.shape[1]);
    py::array_t<double> out({rows, rows});
    const auto* in = static_cast<const double*>(buf.ptr);
    auto* dst = static_cast<double*>(out.request().ptr);
    int n_threads = resolve(threads);
    {
        py::gil_scoped_release release;  // pure c++ from here, let python threads run
        quantly::correlation_matrix(in, rows, cols, dst, n_threads);
    }
    return out;
}

py::array_t<double> covariance_matrix(DoubleArray data, int ddof) {
    auto buf = data.request();
    check_2d(buf, "covariance_matrix");
    auto rows = static_cast<std::size_t>(buf.shape[0]);
    auto cols = static_cast<std::size_t>(buf.shape[1]);
    py::array_t<double> out({rows, rows});
    quantly::covariance_matrix(static_cast<const double*>(buf.ptr), rows, cols, ddof,
                               static_cast<double*>(out.request().ptr));
    return out;
}

using VarFn = quantly::VaRResult (*)(double, double, int, std::size_t, double,
                                     unsigned long long, int);

static py::dict run_var(VarFn fn, double mu, double sigma, int horizon, std::size_t n_sims,
                        double confidence, unsigned long long seed, std::optional<int> threads) {
    int n_threads = resolve(threads);
    quantly::VaRResult r;
    {
        py::gil_scoped_release release;
        r = fn(mu, sigma, horizon, n_sims, confidence, seed, n_threads);
    }
    py::dict out;
    out["var"] = r.var;
    out["cvar"] = r.cvar;
    return out;
}

py::dict monte_carlo_var(double mu, double sigma, int horizon, std::size_t n_sims,
                         double confidence, unsigned long long seed,
                         std::optional<int> threads) {
    return run_var(&quantly::monte_carlo_var, mu, sigma, horizon, n_sims, confidence, seed,
                   threads);
}

py::dict monte_carlo_var_qmc(double mu, double sigma, int horizon, std::size_t n_sims,
                             double confidence, unsigned long long seed,
                             std::optional<int> threads) {
    return run_var(&quantly::monte_carlo_var_qmc, mu, sigma, horizon, n_sims, confidence, seed,
                   threads);
}

// entry point for the `engine._engine` extension module. the compute lives in
// pybind-free translation units; this file only wires them to python.
PYBIND11_MODULE(_engine, m) {
    m.doc() = "Quantly C++ analytics engine";
    m.attr("__version__") = "0.1.0";
    m.def("hello", &hello, "return a greeting, used to smoke-test the binding");
    m.def("max_drawdown", &max_drawdown, py::arg("returns"),
          "worst peak-to-trough decline and longest underwater duration");
    m.def("hardware_threads", []() { return std::thread::hardware_concurrency(); },
          "number of hardware threads the default (threads=None) runs use");
    m.def("correlation_matrix", &correlation_matrix, py::arg("data"),
          py::arg("threads") = py::none(),
          "pairwise Pearson correlation of the rows (assets x observations)");
    m.def("covariance_matrix", &covariance_matrix, py::arg("data"), py::arg("ddof") = 1,
          "pairwise sample covariance of the rows (assets x observations)");
    m.def("monte_carlo_var", &monte_carlo_var, py::arg("mu"), py::arg("sigma"), py::arg("horizon"),
          py::arg("n_sims"), py::arg("confidence") = 0.95, py::arg("seed") = 0,
          py::arg("threads") = py::none(),
          "Monte Carlo value at risk and expected shortfall over a horizon; the "
          "result does not depend on threads");
    m.def("monte_carlo_var_qmc", &monte_carlo_var_qmc, py::arg("mu"), py::arg("sigma"),
          py::arg("horizon"), py::arg("n_sims"), py::arg("confidence") = 0.95,
          py::arg("seed") = 0, py::arg("threads") = py::none(),
          "Sobol quasi-Monte Carlo VaR (horizon <= 30), randomized by a seeded digital shift");
}
