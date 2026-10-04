#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <stdexcept>

#include "normal.hpp"
#include "var.hpp"

using Catch::Approx;
using quantly::monte_carlo_var;
using quantly::monte_carlo_var_qmc;

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

TEST_CASE("results are identical for any thread count") {
    // 50k paths = 49 blocks, so threads genuinely split the work
    auto base = monte_carlo_var(0.0005, 0.02, 21, 50000, 0.95, 7, 1);
    for (int threads : {0, 2, 3, 8, -1}) {
        auto r = monte_carlo_var(0.0005, 0.02, 21, 50000, 0.95, 7, threads);
        REQUIRE(r.var == base.var);
        REQUIRE(r.cvar == base.cvar);
    }
}

TEST_CASE("qmc results are identical for any thread count") {
    auto base = monte_carlo_var_qmc(0.0005, 0.02, 21, 1 << 15, 0.95, 7, 1);
    for (int threads : {2, 5, -1}) {
        auto r = monte_carlo_var_qmc(0.0005, 0.02, 21, 1 << 15, 0.95, 7, threads);
        REQUIRE(r.var == base.var);
        REQUIRE(r.cvar == base.cvar);
    }
}

TEST_CASE("one-day var agrees with the analytic normal quantile") {
    // horizon 1: pnl ~ N(mu, sigma), so var = -(mu + sigma * z_0.05)
    const double mu = 0.001, sigma = 0.02;
    const double z05 = quantly::inverse_normal_cdf(0.05);
    const double analytic = -(mu + sigma * z05);
    // quantile s.e. at 4M paths is about 2e-5; 1e-4 is a 5-sigma bound
    auto r = monte_carlo_var(mu, sigma, 1, 4'000'000, 0.95, 11);
    REQUIRE(std::abs(r.var - analytic) < 1e-4);
    // expected shortfall of a normal: -(mu - sigma * pdf(z) / alpha)
    double pdf = std::exp(-0.5 * z05 * z05) / std::sqrt(2.0 * 3.14159265358979323846);
    double es = -(mu - sigma * pdf / 0.05);
    REQUIRE(std::abs(r.cvar - es) < 1.5e-4);
}

TEST_CASE("qmc beats plain mc at equal n on a smooth case") {
    const double mu = 0.001, sigma = 0.02;
    const double analytic = -(mu + sigma * quantly::inverse_normal_cdf(0.05));
    const std::size_t n = 1 << 14;
    double mc_sq = 0.0, qmc_sq = 0.0;
    const int reps = 16;
    for (int s = 1; s <= reps; ++s) {
        double e1 = monte_carlo_var(mu, sigma, 1, n, 0.95, s).var - analytic;
        double e2 = monte_carlo_var_qmc(mu, sigma, 1, n, 0.95, s).var - analytic;
        mc_sq += e1 * e1;
        qmc_sq += e2 * e2;
    }
    REQUIRE(std::sqrt(qmc_sq / reps) < 0.5 * std::sqrt(mc_sq / reps));
}

TEST_CASE("qmc rejects horizons beyond the sobol table") {
    REQUIRE_THROWS_AS(monte_carlo_var_qmc(0.0, 0.02, 31, 1024, 0.95, 1), std::invalid_argument);
}
