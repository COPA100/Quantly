#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "var.hpp"

using Catch::Approx;
using quantly::monte_carlo_var;

TEST_CASE("degenerate inputs give zero var") {
    REQUIRE(monte_carlo_var(0.0, 0.02, 0, 1000, 0.95, 1).var == 0.0);
    REQUIRE(monte_carlo_var(0.0, 0.02, 5, 0, 0.95, 1).var == 0.0);
}

TEST_CASE("zero volatility means no loss") {
    auto r = monte_carlo_var(0.0, 0.0, 10, 1000, 0.95, 1);
    REQUIRE(r.var == Approx(0.0));
    REQUIRE(r.cvar == Approx(0.0));
}

TEST_CASE("deterministic under a seed, with cvar past var") {
    auto a = monte_carlo_var(0.0, 0.02, 10, 20000, 0.95, 42);
    auto b = monte_carlo_var(0.0, 0.02, 10, 20000, 0.95, 42);
    REQUIRE(a.var == b.var);
    REQUIRE(a.cvar == b.cvar);
    REQUIRE(a.var > 0.0);
    REQUIRE(a.cvar >= a.var);
}

TEST_CASE("a different seed gives a different draw") {
    auto a = monte_carlo_var(0.0, 0.02, 10, 20000, 0.95, 1);
    auto b = monte_carlo_var(0.0, 0.02, 10, 20000, 0.95, 2);
    REQUIRE(a.var != b.var);
}
