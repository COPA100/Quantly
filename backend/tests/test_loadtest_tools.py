import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "loadtest"))

import capacity  # noqa: E402
import simulate_scaling as sim  # noqa: E402


def write_run(tmp_path, name, book, workers, jobs, drain_ms):
    path = tmp_path / name
    path.write_text(
        json.dumps(
            {
                "scenario": "burst",
                "book": book,
                "workers": workers,
                "metrics": {
                    "jobs_complete": {"count": jobs},
                    "completed_at_ms": {"max": drain_ms},
                    "time_to_complete_ms": {"avg": 5000},
                },
            }
        )
    )
    return path


def test_load_run_and_throughput(tmp_path):
    run = capacity.load_run(write_run(tmp_path, "a.json", "warm", 2, 100, 50_000))
    assert run.throughput == pytest.approx(2.0)
    assert run.per_worker == pytest.approx(1.0)
    assert run.service_time == pytest.approx(1.0)


def test_rejects_non_burst_and_empty_runs(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"scenario": "steady", "metrics": {}}))
    with pytest.raises(ValueError):
        capacity.load_run(p)
    with pytest.raises(ValueError):
        capacity.load_run(write_run(tmp_path, "z.json", "warm", 1, 0, 0))


def test_littles_law_sizing():
    # 5 jobs/s at 2 s each keeps 10 workers busy, 70% target needs 15
    assert capacity.required_workers(5, 2.0, 0.7) == 15
    assert capacity.required_workers(0.1, 1.0, 1.0) == 1
    with pytest.raises(ValueError):
        capacity.required_workers(1, 1, 0)


def test_backlog_target():
    assert capacity.backlog_target(0.5, 30) == pytest.approx(15)


def test_drain_rate_from_samples():
    # 100 jobs cleared at 2/s after the peak
    samples = [
        (0, 0),
        (10, 100),
        (20, 80),
        (30, 60),
        (40, 40),
        (50, 20),
        (60, 0),
        (70, 0),
    ]
    assert capacity.drain_rate_from_samples(samples) == pytest.approx(2.0)
    assert capacity.drain_rate_from_samples([(0, 1)]) is None


def test_render_has_warm_and_cold_rows(tmp_path):
    runs = [
        capacity.load_run(write_run(tmp_path, "w.json", "warm", 1, 60, 30_000)),
        capacity.load_run(write_run(tmp_path, "c.json", "cold", 1, 30, 30_000)),
    ]
    text = capacity.render(runs, 2.0, 0.5, 30)
    assert "| warm | 1 | 60 |" in text and "| cold | 1 | 30 |" in text
    # warm: 2 jobs/s/worker, 2 uploads/s at 50% needs 2 workers
    assert "| warm | 2 |" in text


def test_desired_replicas_math():
    assert sim.desired_replicas(2, 40, 20, 0, 10) == 4
    assert sim.desired_replicas(4, 5, 20, 1, 10) == 1
    assert sim.desired_replicas(2, 1000, 20, 0, 10) == 10  # max clamp
    assert sim.desired_replicas(0, 50, 20, 0, 10) == 3  # from zero


def test_backlog_metric_avoids_zero_division():
    assert sim.backlog_per_worker(30, 0) == 30
    assert sim.backlog_per_worker(30, 3) == 10


def test_scales_out_then_back_to_zero():
    policy = sim.Policy(target=20, max_replicas=10, start_s=60)
    rows = sim.simulate(sim.synthetic_burst(), policy)
    peak = max(r.running for r in rows)
    assert 1 < peak <= 10
    assert rows[0].running == 0
    assert rows[-1].running == policy.min_replicas
    # a requested task only runs after the start delay
    first_ask = next(i for i, r in enumerate(rows) if r.desired > 0)
    assert rows[first_ask].running == 0


def test_scale_in_waits_for_quiet_samples():
    policy = sim.Policy(target=10, scale_in_samples=3, scale_in_cooldown_s=0, start_s=0)
    series = [(0, 100), (60, 100), (120, 0), (180, 0), (240, 0), (300, 0)]
    rows = sim.simulate(series, policy)
    assert rows[2].running > 0 and rows[3].running > 0  # still quiet < 3 samples
    assert rows[4].running < rows[3].running
