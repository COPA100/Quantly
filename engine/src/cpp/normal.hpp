#pragma once

namespace quantly {

// inverse of the standard normal cdf (acklam's rational approximation, relative
// error about 1e-9). `p` must be in (0, 1).
double inverse_normal_cdf(double p);

}  // namespace quantly
