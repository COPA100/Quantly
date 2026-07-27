#pragma once

#include <cstddef>

namespace quantly {

// all matrices are row-major. `data` is (n_assets x n_obs): one asset's return
// series per row, over the trailing window of observations. `out` is the
// (n_assets x n_assets) result, caller-allocated.

// pairwise sample covariance, normalized by (n_obs - ddof).
void covariance_matrix(const double* data, std::size_t n_assets, std::size_t n_obs, int ddof,
                       double* out);

// pairwise Pearson correlation. matches numpy.corrcoef: scale-invariant (ddof
// cancels), clamped to [-1, 1], NaN where a series has zero variance.
void correlation_matrix(const double* data, std::size_t n_assets, std::size_t n_obs, double* out);

}  // namespace quantly
