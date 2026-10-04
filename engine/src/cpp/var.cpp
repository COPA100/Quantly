#include "var.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

#include "normal.hpp"
#include "parallel.hpp"
#include "rng.hpp"
#include "sobol.hpp"

namespace quantly {

namespace {

constexpr std::size_t kBlock = 1024;  // paths per block, fixed so output is thread-invariant
constexpr double kTwoPi = 6.283185307179586476925286766559;
constexpr double kInv2Pow53 = 1.0 / 9007199254740992.0;
constexpr double kInv2Pow32 = 1.0 / 4294967296.0;

VaRResult degenerate(double mu, int horizon) {
    // no volatility -> every path is the same deterministic compounding of
    // mu, so var == cvar == that single loss
    double growth = 1.0;
    for (int d = 0; d < horizon; ++d) {
        growth *= (1.0 + mu);
    }
    double loss = -(growth - 1.0);
    return {loss, loss};
}

// standard normals for one block via box-muller on philox output. stream is
// keyed by (seed, block); the j-th philox call yields two normals.
void fill_normals(unsigned long long seed, std::size_t block, double* z, std::size_t total) {
    constexpr std::size_t kBatch = 64;
    const auto k0 = static_cast<std::uint32_t>(seed);
    const auto k1 = static_cast<std::uint32_t>(seed >> 32);
    const auto b_lo = static_cast<std::uint32_t>(block);
    const auto b_hi = static_cast<std::uint32_t>(static_cast<std::uint64_t>(block) >> 32);
    const std::size_t calls = (total + 1) / 2;

    std::uint32_t c0[kBatch], c1[kBatch], c2[kBatch], c3[kBatch];
    for (std::size_t base = 0; base < calls; base += kBatch) {
        std::size_t m = std::min(kBatch, calls - base);
        for (std::size_t i = 0; i < m; ++i) {
            c0[i] = static_cast<std::uint32_t>(base + i);
            c1[i] = static_cast<std::uint32_t>((base + i) >> 32);
            c2[i] = b_lo;
            c3[i] = b_hi;
        }
        philox4x32_10(k0, k1, c0, c1, c2, c3, m);
        for (std::size_t i = 0; i < m; ++i) {
            // 53-bit uniforms; u1 in (0, 1] so the log is finite
            std::uint64_t a = (static_cast<std::uint64_t>(c1[i]) << 32) | c0[i];
            std::uint64_t b = (static_cast<std::uint64_t>(c3[i]) << 32) | c2[i];
            double u1 = static_cast<double>((a >> 11) + 1) * kInv2Pow53;
            double u2 = static_cast<double>(b >> 11) * kInv2Pow53;
            double r = std::sqrt(-2.0 * std::log(u1));
            double theta = kTwoPi * u2;
            std::size_t j = 2 * (base + i);
            z[j] = r * std::cos(theta);
            if (j + 1 < total) {
                z[j + 1] = r * std::sin(theta);
            }
        }
    }
}

// compound day-major normals z[d * n + p] into per-path P&L fractions
void compound(const double* z, std::size_t n, int horizon, double mu, double sigma, double* pnl) {
    for (std::size_t p = 0; p < n; ++p) {
        pnl[p] = 1.0;
    }
    for (int d = 0; d < horizon; ++d) {
        const double* zd = z + static_cast<std::size_t>(d) * n;
        for (std::size_t p = 0; p < n; ++p) {
            pnl[p] *= 1.0 + (mu + sigma * zd[p]);
        }
    }
    for (std::size_t p = 0; p < n; ++p) {
        pnl[p] -= 1.0;
    }
}

VaRResult tail_stats(std::vector<double>& pnl, double confidence) {
    const std::size_t n = pnl.size();
    double alpha = 1.0 - confidence;
    std::size_t idx = static_cast<std::size_t>(alpha * static_cast<double>(n));
    if (idx >= n) {
        idx = n - 1;
    }
    // selection instead of a full sort: only the idx-th order statistic and the
    // set of values below it matter
    std::nth_element(pnl.begin(), pnl.begin() + static_cast<std::ptrdiff_t>(idx), pnl.end());
    double var = -pnl[idx];

    // expected shortfall: mean of everything in the tail up to and including idx
    std::size_t count = idx + 1;
    double tail = 0.0;
    for (std::size_t i = 0; i < count; ++i) {
        tail += pnl[i];
    }
    return {var, -(tail / static_cast<double>(count))};
}

}  // namespace

VaRResult monte_carlo_var(double mu, double sigma, int horizon, std::size_t n_sims,
                          double confidence, unsigned long long seed, int threads) {
    if (n_sims == 0 || horizon <= 0) {
        return {0.0, 0.0};
    }
    if (sigma <= 0.0) {
        return degenerate(mu, horizon);
    }

    std::vector<double> pnl(n_sims);
    const std::size_t n_blocks = (n_sims + kBlock - 1) / kBlock;
    parallel_for(n_blocks, threads, [&](std::size_t b) {
        std::size_t first = b * kBlock;
        std::size_t n = std::min(kBlock, n_sims - first);
        std::vector<double> z(n * static_cast<std::size_t>(horizon));
        fill_normals(seed, b, z.data(), z.size());
        compound(z.data(), n, horizon, mu, sigma, pnl.data() + first);
    });
    return tail_stats(pnl, confidence);
}

VaRResult monte_carlo_var_qmc(double mu, double sigma, int horizon, std::size_t n_sims,
                              double confidence, unsigned long long seed, int threads) {
    if (n_sims == 0 || horizon <= 0) {
        return {0.0, 0.0};
    }
    if (sigma <= 0.0) {
        return degenerate(mu, horizon);
    }

    Sobol sobol(horizon);  // throws for horizon > 30

    // random digital shift per dimension, drawn from philox
    std::vector<std::uint32_t> shift(static_cast<std::size_t>(horizon));
    for (std::size_t d = 0; d < shift.size(); d += 2) {
        std::uint32_t c0 = static_cast<std::uint32_t>(d / 2), c1 = 0, c2 = 0xFFFFFFFFu, c3 = 0;
        philox4x32_10(static_cast<std::uint32_t>(seed), static_cast<std::uint32_t>(seed >> 32),
                      &c0, &c1, &c2, &c3, 1);
        shift[d] = c0;
        if (d + 1 < shift.size()) {
            shift[d + 1] = c1;
        }
    }

    // helmert basis: row 0 is the equal-weight direction, row k contrasts the
    // first k days with day k. orthonormal, so z stays standard normal.
    const auto h = static_cast<std::size_t>(horizon);
    std::vector<double> basis(h * h, 0.0);
    for (std::size_t d = 0; d < h; ++d) {
        basis[d] = 1.0 / std::sqrt(static_cast<double>(h));
    }
    for (std::size_t k = 1; k < h; ++k) {
        double norm = std::sqrt(static_cast<double>(k * (k + 1)));
        for (std::size_t d = 0; d < k; ++d) {
            basis[k * h + d] = 1.0 / norm;
        }
        basis[k * h + k] = -static_cast<double>(k) / norm;
    }

    std::vector<double> pnl(n_sims);
    const std::size_t n_blocks = (n_sims + kBlock - 1) / kBlock;
    parallel_for(n_blocks, threads, [&](std::size_t b) {
        std::size_t first = b * kBlock;
        std::size_t n = std::min(kBlock, n_sims - first);
        std::vector<double> w(n * h), z(n * h, 0.0);
        std::uint32_t state[kSobolMaxDim];
        sobol.point(first, state);
        for (std::size_t p = 0; p < n; ++p) {
            for (std::size_t d = 0; d < h; ++d) {
                double u = (static_cast<double>(state[d] ^ shift[d]) + 0.5) * kInv2Pow32;
                w[d * n + p] = inverse_normal_cdf(u);
            }
            sobol.next(first + p, state);
        }
        // rotate: z = basis^T w, so the first (best-distributed) sobol dimension
        // drives the common level of all days and later ones the small wiggles
        for (std::size_t j = 0; j < h; ++j) {
            for (std::size_t d = 0; d < h; ++d) {
                double c = basis[j * h + d];
                const double* wj = w.data() + j * n;
                double* zd = z.data() + d * n;
                for (std::size_t p = 0; p < n; ++p) {
                    zd[p] += c * wj[p];
                }
            }
        }
        compound(z.data(), n, horizon, mu, sigma, pnl.data() + first);
    });
    return tail_stats(pnl, confidence);
}

}  // namespace quantly
