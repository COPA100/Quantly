#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <random>
#include <vector>

#include "correlation.hpp"

using Catch::Approx;

TEST_CASE("perfectly correlated rows give +1") {
    // row1 = 2 * row0, so correlation is exactly 1
    std::vector<double> data = {1, 2, 3, 4, 2, 4, 6, 8};  // 2x4 row-major
    double out[4];
    quantly::correlation_matrix(data.data(), 2, 4, out);
    REQUIRE(out[0] == Approx(1.0));  // diagonal
    REQUIRE(out[1] == Approx(1.0));  // off-diagonal
    REQUIRE(out[3] == Approx(1.0));
}

TEST_CASE("anti-correlated rows give -1") {
    std::vector<double> data = {1, 2, 3, 4, 4, 3, 2, 1};
    double out[4];
    quantly::correlation_matrix(data.data(), 2, 4, out);
    REQUIRE(out[1] == Approx(-1.0));
    REQUIRE(out[2] == Approx(-1.0));  // matrix is symmetric
}

TEST_CASE("a flat row yields nan correlation, like numpy") {
    std::vector<double> data = {1, 1, 1, 1, 2, 3};
    double out[4];
    quantly::correlation_matrix(data.data(), 2, 3, out);
    REQUIRE(std::isnan(out[1]));
}

TEST_CASE("sample covariance matches a hand calculation") {
    // {1,2,3}: mean 2, centered ss = 2, sample var (ddof=1) = 2 / (3-1) = 1
    std::vector<double> data = {1, 2, 3};
    double out[1];
    quantly::covariance_matrix(data.data(), 1, 3, 1, out);
    REQUIRE(out[0] == Approx(1.0));
}

namespace {

// textbook two-pass pearson, the reference for the tiled kernel
std::vector<double> naive_corr(const std::vector<double>& d, std::size_t rows, std::size_t cols) {
    std::vector<double> out(rows * rows);
    std::vector<double> mean(rows, 0.0);
    for (std::size_t i = 0; i < rows; ++i) {
        for (std::size_t k = 0; k < cols; ++k) mean[i] += d[i * cols + k];
        mean[i] /= static_cast<double>(cols);
    }
    for (std::size_t i = 0; i < rows; ++i) {
        for (std::size_t j = 0; j < rows; ++j) {
            double xy = 0, xx = 0, yy = 0;
            for (std::size_t k = 0; k < cols; ++k) {
                double a = d[i * cols + k] - mean[i], b = d[j * cols + k] - mean[j];
                xy += a * b;
                xx += a * a;
                yy += b * b;
            }
            out[i * rows + j] = xy / std::sqrt(xx * yy);
        }
    }
    return out;
}

std::vector<double> random_matrix(std::size_t rows, std::size_t cols, unsigned seed) {
    std::mt19937_64 rng(seed);
    std::normal_distribution<double> n(0.0, 0.02);
    std::vector<double> d(rows * cols);
    for (auto& x : d) x = n(rng);
    return d;
}

}  // namespace

TEST_CASE("tiled kernel matches the naive reference across awkward shapes") {
    // sizes straddle the 16-wide tile and the 256-obs panel boundaries
    const std::size_t shapes[][2] = {{1, 5}, {2, 3}, {15, 40}, {16, 256}, {17, 257},
                                     {33, 513}, {50, 1260}, {70, 300}};
    for (auto& sh : shapes) {
        auto d = random_matrix(sh[0], sh[1], 5);
        auto ref = naive_corr(d, sh[0], sh[1]);
        std::vector<double> out(sh[0] * sh[0]);
        quantly::correlation_matrix(d.data(), sh[0], sh[1], out.data());
        for (std::size_t i = 0; i < out.size(); ++i) {
            REQUIRE(out[i] == Approx(ref[i]).margin(1e-12));
        }
    }
}

TEST_CASE("correlation is identical for any thread count") {
    // large enough to cross the threading threshold
    const std::size_t rows = 120, cols = 1260;
    auto d = random_matrix(rows, cols, 9);
    std::vector<double> base(rows * rows), other(rows * rows);
    quantly::correlation_matrix(d.data(), rows, cols, base.data(), 1);
    for (int threads : {0, 2, 3, 7, -1}) {
        quantly::correlation_matrix(d.data(), rows, cols, other.data(), threads);
        REQUIRE(other == base);
    }
}

TEST_CASE("a flat row stays nan in the threaded path and spares other pairs") {
    const std::size_t rows = 40, cols = 600;
    auto d = random_matrix(rows, cols, 3);
    for (std::size_t k = 0; k < cols; ++k) d[5 * cols + k] = 0.25;
    std::vector<double> out(rows * rows);
    quantly::correlation_matrix(d.data(), rows, cols, out.data(), 4);
    REQUIRE(std::isnan(out[5 * rows + 9]));
    REQUIRE(std::isnan(out[9 * rows + 5]));
    REQUIRE(!std::isnan(out[3 * rows + 9]));
    REQUIRE(out[3 * rows + 3] == Approx(1.0));
}
