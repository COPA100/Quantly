#include "var.hpp"

#include <algorithm>
#include <random>
#include <vector>

namespace quantly {

VaRResult monte_carlo_var(double mu, double sigma, int horizon, std::size_t n_sims,
                          double confidence, unsigned long long seed) {
    if (n_sims == 0 || horizon <= 0) {
        return {0.0, 0.0};
    }

    std::mt19937_64 rng(seed);
    std::normal_distribution<double> draw(mu, sigma);

    std::vector<double> pnl(n_sims);
    for (std::size_t s = 0; s < n_sims; ++s) {
        double growth = 1.0;
        for (int d = 0; d < horizon; ++d) {
            growth *= (1.0 + draw(rng));  // compound one day's return
        }
        pnl[s] = growth - 1.0;  // horizon return as a P&L fraction
    }
    std::sort(pnl.begin(), pnl.end());

    // the loss at the (1 - confidence) quantile of the sorted outcomes
    double alpha = 1.0 - confidence;
    std::size_t idx = static_cast<std::size_t>(alpha * static_cast<double>(n_sims));
    if (idx >= n_sims) {
        idx = n_sims - 1;
    }
    double var = -pnl[idx];

    // expected shortfall: mean of everything in the tail up to and including idx
    std::size_t count = idx + 1;
    double tail = 0.0;
    for (std::size_t i = 0; i < count; ++i) {
        tail += pnl[i];
    }
    double cvar = -(tail / static_cast<double>(count));

    return {var, cvar};
}

}  // namespace quantly
