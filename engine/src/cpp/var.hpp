#pragma once

#include <cstddef>

namespace quantly {

struct VaRResult {
    double var;   // value at risk: loss magnitude (>= 0) at the confidence level
    double cvar;  // conditional VaR / expected shortfall of the tail beyond var
};

// Monte Carlo VaR: simulate `n_sims` paths of `horizon` daily normal returns
// N(mu, sigma), compound each to a horizon P&L, and read the loss quantile at
// (1 - confidence). path-dependent compounding is the loop C++ wins on.
//
// paths are split into fixed blocks of 1024; block b draws from its own
// philox4x32-10 stream keyed by (seed, b). the result therefore depends only on
// (inputs, seed), never on `threads`. threads < 0 uses all hardware threads,
// 0 and 1 run on the calling thread.
VaRResult monte_carlo_var(double mu, double sigma, int horizon, std::size_t n_sims,
                          double confidence, unsigned long long seed, int threads = -1);

// quasi-monte carlo variant: sobol points over a helmert rotation of the daily
// shocks (horizon <= 30), with a seeded random digital shift so different seeds
// give independent replicates.
// powers of two for n_sims keep the point set balanced. same thread invariance.
VaRResult monte_carlo_var_qmc(double mu, double sigma, int horizon, std::size_t n_sims,
                              double confidence, unsigned long long seed, int threads = -1);

}  // namespace quantly
