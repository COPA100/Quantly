import numpy as np


def monte_carlo_var(
    mu: float,
    sigma: float,
    horizon: int,
    n_sims: int,
    confidence: float = 0.95,
    seed: int = 0,
) -> dict:
    # numpy-vectorized baseline for the C++ engine's monte_carlo_var. simulate
    # n_sims paths of `horizon` daily normal returns, compound each, and read the
    # loss quantile at (1 - confidence). same method as the C++ version so the
    # two agree up to monte-carlo sampling noise.
    if n_sims <= 0 or horizon <= 0:
        return {"var": 0.0, "cvar": 0.0}

    rng = np.random.default_rng(seed)
    draws = rng.normal(mu, sigma, size=(n_sims, horizon))
    pnl = np.sort(np.prod(1.0 + draws, axis=1) - 1.0)

    idx = min(int((1.0 - confidence) * n_sims), n_sims - 1)
    var = float(-pnl[idx])
    cvar = float(-pnl[: idx + 1].mean())
    return {"var": var, "cvar": cvar}
