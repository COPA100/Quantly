#include "correlation.hpp"

#include <cmath>
#include <vector>

namespace quantly {

namespace {

std::vector<double> row_means(const double* data, std::size_t rows, std::size_t cols) {
    std::vector<double> means(rows, 0.0);
    for (std::size_t i = 0; i < rows; ++i) {
        const double* row = data + i * cols;
        double sum = 0.0;
        for (std::size_t k = 0; k < cols; ++k) {
            sum += row[k];
        }
        means[i] = cols ? sum / static_cast<double>(cols) : 0.0;
    }
    return means;
}

}  // namespace

void covariance_matrix(const double* data, std::size_t rows, std::size_t cols, int ddof,
                       double* out) {
    std::vector<double> means = row_means(data, rows, cols);
    double denom = static_cast<double>(cols) - static_cast<double>(ddof);
    for (std::size_t i = 0; i < rows; ++i) {
        for (std::size_t j = i; j < rows; ++j) {
            const double* ri = data + i * cols;
            const double* rj = data + j * cols;
            double acc = 0.0;
            for (std::size_t k = 0; k < cols; ++k) {
                acc += (ri[k] - means[i]) * (rj[k] - means[j]);
            }
            double cov = denom > 0.0 ? acc / denom : 0.0;
            out[i * rows + j] = cov;
            out[j * rows + i] = cov;
        }
    }
}

void correlation_matrix(const double* data, std::size_t rows, std::size_t cols, double* out) {
    std::vector<double> means = row_means(data, rows, cols);

    // centered sum of squares per row; ddof cancels in the correlation ratio
    std::vector<double> sumsq(rows, 0.0);
    for (std::size_t i = 0; i < rows; ++i) {
        const double* ri = data + i * cols;
        double acc = 0.0;
        for (std::size_t k = 0; k < cols; ++k) {
            double d = ri[k] - means[i];
            acc += d * d;
        }
        sumsq[i] = acc;
    }

    for (std::size_t i = 0; i < rows; ++i) {
        for (std::size_t j = i; j < rows; ++j) {
            const double* ri = data + i * cols;
            const double* rj = data + j * cols;
            double acc = 0.0;
            for (std::size_t k = 0; k < cols; ++k) {
                acc += (ri[k] - means[i]) * (rj[k] - means[j]);
            }
            // nan when a series is flat (denom 0), matching numpy.corrcoef
            double corr = acc / std::sqrt(sumsq[i] * sumsq[j]);
            if (corr > 1.0) {
                corr = 1.0;
            } else if (corr < -1.0) {
                corr = -1.0;
            }
            out[i * rows + j] = corr;
            out[j * rows + i] = corr;
        }
    }
}

}  // namespace quantly
