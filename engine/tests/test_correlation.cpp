#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <cmath>
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
