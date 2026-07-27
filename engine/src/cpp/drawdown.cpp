#include "drawdown.hpp"

namespace quantly {

Drawdown max_drawdown(const double* returns, std::size_t n) {
    if (n == 0) {
        return {0.0, 0};
    }

    double equity = 1.0;  // running equity curve, anchored at 1.0
    double peak = 1.0;    // running maximum of the equity curve
    double worst = 0.0;   // most negative drawdown seen (the anchor sits at 0)
    long longest = 0;
    long current = 0;

    // the anchor point (equity 1.0) is never underwater, matching the python
    // baseline, so the scan starts from the first actual return
    for (std::size_t i = 0; i < n; ++i) {
        equity *= (1.0 + returns[i]);
        if (equity > peak) {
            peak = equity;
        }
        double dd = equity / peak - 1.0;
        if (dd < worst) {
            worst = dd;
        }
        if (dd < 0.0) {
            ++current;
            if (current > longest) {
                longest = current;
            }
        } else {
            current = 0;
        }
    }
    return {worst, longest};
}

}  // namespace quantly
