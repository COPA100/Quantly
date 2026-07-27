#pragma once

#include <cstddef>

namespace quantly {

struct Drawdown {
    double max_drawdown;  // most negative peak-to-trough decline (<= 0)
    long duration;        // longest run of consecutive underwater periods
};

// worst peak-to-trough decline and the longest underwater streak, computed from
// a returns series with the equity curve anchored at 1.0. matches the pure
// python baseline in common.analytics.metrics.max_drawdown.
Drawdown max_drawdown(const double* returns, std::size_t n);

}  // namespace quantly
