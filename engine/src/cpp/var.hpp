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
VaRResult monte_carlo_var(double mu, double sigma, int horizon, std::size_t n_sims,
                          double confidence, unsigned long long seed);

}  // namespace quantly
