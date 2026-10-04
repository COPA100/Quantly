import os

from hypothesis import HealthCheck, settings

# dev: quick random runs. ci: more examples, fixed seed so a red build reproduces.
settings.register_profile(
    "dev",
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "ci",
    max_examples=150,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
