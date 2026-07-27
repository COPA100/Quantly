#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "drawdown.hpp"

using Catch::Approx;
using quantly::max_drawdown;

TEST_CASE("empty series has no drawdown") {
    auto d = max_drawdown(nullptr, 0);
    REQUIRE(d.max_drawdown == 0.0);
    REQUIRE(d.duration == 0);
}

TEST_CASE("monotonic gains never go underwater") {
    double r[] = {0.01, 0.02, 0.03};
    auto d = max_drawdown(r, 3);
    REQUIRE(d.max_drawdown == 0.0);
    REQUIRE(d.duration == 0);
}

TEST_CASE("worst decline and longest underwater streak") {
    // equity anchored at 1.0: 1.1, 0.55, 0.275, 0.33, 0.429
    // worst dd = 0.275/1.1 - 1 = -0.75; underwater for the last four periods
    double r[] = {0.1, -0.5, -0.5, 0.2, 0.3};
    auto d = max_drawdown(r, 5);
    REQUIRE(d.max_drawdown == Approx(-0.75));
    REQUIRE(d.duration == 4);
}

TEST_CASE("a single down period") {
    double r[] = {-0.2};
    auto d = max_drawdown(r, 1);
    REQUIRE(d.max_drawdown == Approx(-0.2));
    REQUIRE(d.duration == 1);
}
