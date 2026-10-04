#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <cstdint>
#include <set>
#include <vector>

#include "normal.hpp"
#include "rng.hpp"
#include "sobol.hpp"

using Catch::Approx;

TEST_CASE("philox4x32-10 matches the random123 known answer") {
    std::uint32_t c0 = 0, c1 = 0, c2 = 0, c3 = 0;
    quantly::philox4x32_10(0, 0, &c0, &c1, &c2, &c3, 1);
    REQUIRE(c0 == 0x6627e8d5u);
    REQUIRE(c1 == 0xe169c58du);
    REQUIRE(c2 == 0xbc57ac4cu);
    REQUIRE(c3 == 0x9b00dbd8u);
}

TEST_CASE("philox batches equal one-at-a-time calls") {
    constexpr std::size_t n = 37;
    std::uint32_t a[4][n], b[4][n];
    for (std::size_t i = 0; i < n; ++i) {
        a[0][i] = b[0][i] = static_cast<std::uint32_t>(i * 7919);
        a[1][i] = b[1][i] = 1;
        a[2][i] = b[2][i] = 5;
        a[3][i] = b[3][i] = 9;
    }
    quantly::philox4x32_10(11, 22, a[0], a[1], a[2], a[3], n);
    for (std::size_t i = 0; i < n; ++i) {
        quantly::philox4x32_10(11, 22, &b[0][i], &b[1][i], &b[2][i], &b[3][i], 1);
        for (int k = 0; k < 4; ++k) {
            REQUIRE(a[k][i] == b[k][i]);
        }
    }
}

TEST_CASE("inverse normal cdf round-trips through erfc") {
    for (double p : {1e-8, 1e-4, 0.01, 0.05, 0.3, 0.5, 0.8, 0.975, 0.9999}) {
        double z = quantly::inverse_normal_cdf(p);
        double back = 0.5 * std::erfc(-z / std::sqrt(2.0));
        REQUIRE(back == Approx(p).epsilon(1e-7));
    }
}

TEST_CASE("sobol first dimensions are the known sequence") {
    quantly::Sobol s(2);
    std::uint32_t x[2];
    const double expect0[] = {0.0, 0.5, 0.75, 0.25, 0.375};
    const double expect1[] = {0.0, 0.5, 0.25, 0.75, 0.375};
    for (int i = 0; i < 5; ++i) {
        s.point(static_cast<std::uint64_t>(i), x);
        REQUIRE(x[0] / 4294967296.0 == Approx(expect0[i]));
        REQUIRE(x[1] / 4294967296.0 == Approx(expect1[i]));
    }
}

TEST_CASE("sobol incremental update matches direct indexing") {
    quantly::Sobol s(21);
    std::uint32_t state[21], direct[21];
    s.point(1000, state);
    for (std::uint64_t i = 1000; i < 1300; ++i) {
        s.point(i, direct);
        for (int d = 0; d < 21; ++d) {
            REQUIRE(state[d] == direct[d]);
        }
        s.next(i, state);
    }
}

TEST_CASE("every sobol dimension is stratified over a power-of-two prefix") {
    // the first 2^10 points of a (t,s)-sequence put exactly one point in each
    // of 2^10 equal bins in every 1d projection
    quantly::Sobol s(quantly::kSobolMaxDim);
    std::vector<std::set<std::uint32_t>> bins(quantly::kSobolMaxDim);
    std::uint32_t x[quantly::kSobolMaxDim];
    for (std::uint64_t i = 0; i < 1024; ++i) {
        s.point(i, x);
        for (int d = 0; d < quantly::kSobolMaxDim; ++d) {
            bins[static_cast<std::size_t>(d)].insert(x[d] >> 22);
        }
    }
    for (auto& b : bins) {
        REQUIRE(b.size() == 1024);
    }
}
