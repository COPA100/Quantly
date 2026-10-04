// libFuzzer harness for the engine kernels. the first byte picks the kernel, the
// rest is raw bytes reinterpreted as doubles, so NaN, inf, denormals and huge
// magnitudes all show up without a custom generator. build with
// -fsanitize=fuzzer,address,undefined (see .github/workflows/fuzz.yml).
//
// it calls only the public functions in src/cpp/*.hpp, so a later optional
// trailing `threads` argument on those does not need a change here.
//
// depends on:
//   Drawdown max_drawdown(const double*, size_t n)
//   void correlation_matrix(const double*, size_t n_assets, size_t n_obs, double* out)
//   void covariance_matrix(const double*, size_t n_assets, size_t n_obs, int ddof, double* out)
//   VaRResult monte_carlo_var(double mu, double sigma, int horizon, size_t n_sims,
//                             double confidence, unsigned long long seed)

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "correlation.hpp"
#include "drawdown.hpp"
#include "var.hpp"

namespace {

// keeps a single input fast. real portfolios are far below these.
constexpr std::size_t kMaxAssets = 16;
constexpr std::size_t kMaxSims = 2048;
constexpr int kMaxHorizon = 64;

struct Reader {
    const uint8_t* p;
    std::size_t left;

    template <typename T>
    T take() {
        T v{};
        if (left >= sizeof(T)) {
            std::memcpy(&v, p, sizeof(T));
            p += sizeof(T);
            left -= sizeof(T);
        } else {
            p += left;
            left = 0;
        }
        return v;
    }

    // whatever is left, as doubles. any trailing partial double is dropped.
    std::vector<double> rest() {
        std::vector<double> out(left / sizeof(double));
        if (!out.empty()) {
            std::memcpy(out.data(), p, out.size() * sizeof(double));
        }
        p += left;
        left = 0;
        return out;
    }
};

void fuzz_drawdown(Reader& r) {
    std::vector<double> returns = r.rest();
    auto out = quantly::max_drawdown(returns.empty() ? nullptr : returns.data(), returns.size());
    if (out.duration < 0 || static_cast<std::size_t>(out.duration) > returns.size()) {
        std::abort();
    }
    // never positive: the anchor at 1.0 is the floor of the scan
    if (out.max_drawdown > 0.0) {
        std::abort();
    }
}

void fuzz_correlation(Reader& r, bool covariance) {
    std::size_t n_assets = 1 + r.take<uint8_t>() % kMaxAssets;
    std::vector<double> flat = r.rest();
    std::size_t n_obs = flat.size() / n_assets;
    flat.resize(n_assets * n_obs);

    std::vector<double> out(n_assets * n_assets, 0.0);
    const double* data = flat.empty() ? nullptr : flat.data();
    if (covariance) {
        quantly::covariance_matrix(data, n_assets, n_obs, 1, out.data());
        return;
    }
    quantly::correlation_matrix(data, n_assets, n_obs, out.data());

    for (std::size_t i = 0; i < n_assets; ++i) {
        for (std::size_t j = 0; j < n_assets; ++j) {
            double v = out[i * n_assets + j];
            // nan is allowed (flat series, overflow), anything else is clamped
            if (!std::isnan(v) && (v > 1.0 || v < -1.0)) {
                std::abort();
            }
            double w = out[j * n_assets + i];
            if (!(v == w || (std::isnan(v) && std::isnan(w)))) {
                std::abort();  // symmetric
            }
        }
    }
}

void fuzz_var(Reader& r) {
    double mu = r.take<double>();
    double sigma = r.take<double>();
    int horizon = static_cast<int>(r.take<int16_t>() % (kMaxHorizon + 1));
    std::size_t n_sims = r.take<uint16_t>() % (kMaxSims + 1);
    // confidence outside [0, 1] is outside the contract, see the report
    double conf = r.take<uint16_t>() / 65535.0;
    unsigned long long seed = r.take<uint64_t>();

    // a NaN sigma slips past the `sigma <= 0` guard and trips the stddev assert in
    // std::normal_distribution, and inf/NaN params make std::sort see NaN. the
    // python layer only passes finite moments, so non-finite ones are skipped here.
    if (!std::isfinite(mu) || !std::isfinite(sigma)) {
        return;
    }

    auto out = quantly::monte_carlo_var(mu, sigma, horizon, n_sims, conf, seed);
    if (n_sims > 0 && horizon > 0 && std::isfinite(out.var) && std::isfinite(out.cvar) &&
        out.cvar < out.var - 1e-9 * (1.0 + std::fabs(out.var))) {
        std::abort();  // the tail mean is never a smaller loss than its quantile
    }
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, std::size_t size) {
    if (size == 0) {
        return 0;
    }
    Reader r{data + 1, size - 1};
    switch (data[0] % 4) {
        case 0:
            fuzz_drawdown(r);
            break;
        case 1:
            fuzz_correlation(r, false);
            break;
        case 2:
            fuzz_correlation(r, true);
            break;
        default:
            fuzz_var(r);
            break;
    }
    return 0;
}
