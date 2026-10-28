
import numpy as np
import pytest

from simulation.metrics import compute_recovery_metrics


def test_detects_sustained_recovery_after_blackout():
    t = np.arange(0.0, 6.01, 0.1)
    error = np.full_like(t, 0.4)

    # High error during and immediately after the blackout.
    error[(t >= 2.0) & (t < 4.0)] = 2.0
    error[(t >= 4.0) & (t < 4.5)] = 1.5

    result = compute_recovery_metrics(
        t, error,
        blackout_start=2.0,
        blackout_end=4.0,
    )

    assert result["recovered"] is True
    assert result["recovery_time_s"] == pytest.approx(0.5)
    assert result["recovery_baseline_m"] == pytest.approx(0.4)
    assert result["recovery_threshold_m"] == pytest.approx(0.5)


def test_reports_no_recovery_when_error_stays_high():
    t = np.arange(0.0, 6.01, 0.1)
    error = np.full_like(t, 2.0)
    error[t < 2.0] = 0.4

    result = compute_recovery_metrics(
        t, error,
        blackout_start=2.0,
        blackout_end=4.0,
    )

    assert result["recovered"] is False
    assert result["recovery_time_s"] is None


def test_recovery_requires_sustained_low_error():
    t = np.arange(0.0, 6.01, 0.1)
    error = np.full_like(t, 0.4)
    error[(t >= 2.0) & (t < 4.0)] = 2.0

    # Brief dip below threshold, followed by another error spike.
    error[(t >= 4.0) & (t < 4.2)] = 0.4
    error[(t >= 4.2) & (t < 4.5)] = 1.0

    result = compute_recovery_metrics(
        t, error,
        blackout_start=2.0,
        blackout_end=4.0,
    )

    assert result["recovered"] is True
    assert result["recovery_time_s"] == pytest.approx(0.5)


def test_rejects_non_increasing_timestamps():
    with pytest.raises(ValueError, match="strictly increasing"):
        compute_recovery_metrics(
            [0.0, 1.0, 1.0, 2.0],
            [0.4, 0.5, 0.6, 0.4],
            blackout_start=1.0,
            blackout_end=1.5,
        )
def test_reports_post_blackout_minimum_and_final_error():
    import numpy as np

    from simulation.metrics import compute_recovery_metrics

    t = np.arange(0.0, 5.1, 0.1)
    error = np.full_like(t, 2.0)

    # Known errors after the blackout ends at t=2.0.
    error[np.isclose(t, 2.0)] = 1.2
    error[np.isclose(t, 3.0)] = 0.8
    error[-1] = 1.5

    result = compute_recovery_metrics(
        t=t,
        formation_rms=error,
        blackout_start=1.0,
        blackout_end=2.0,
    )

    assert result["post_blackout_min_error_m"] == 0.8
    assert result["final_error_m"] == 1.5
