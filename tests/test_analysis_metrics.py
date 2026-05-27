import math
import sys
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def test_compute_error_metrics_reports_both_reference_denominators():
    from helical_propeller.analysis_metrics import compute_error_metrics

    metrics = compute_error_metrics(2.0, 4.0)

    assert metrics["absolute_error"] == 2.0
    assert metrics["signed_error"] == -2.0
    assert metrics["pct_error_vs_theory"] == 50.0
    assert metrics["pct_error_vs_sim"] == 100.0
    assert metrics["pct_error"] == metrics["pct_error_vs_sim"]
    assert metrics["error_status"] == "OK"


def test_compute_error_metrics_handles_near_zero_without_infinite_ratios():
    from helical_propeller.analysis_metrics import compute_error_metrics

    sim_zero = compute_error_metrics(0.0, 2.0)
    both_zero = compute_error_metrics(0.0, 0.0)
    theory_zero = compute_error_metrics(2.0, 0.0)

    assert sim_zero["error_status"] == "SIM_NEAR_ZERO"
    assert sim_zero["pct_error_vs_sim"] is None
    assert sim_zero["pct_error_vs_theory"] == 100.0
    assert both_zero["error_status"] == "BOTH_NEAR_ZERO"
    assert both_zero["pct_error"] is None
    assert theory_zero["error_status"] == "THEORY_NEAR_ZERO"
    assert theory_zero["pct_error_vs_theory"] is None


def test_compute_error_metrics_handles_nonfinite_values():
    from helical_propeller.analysis_metrics import compute_error_metrics

    metrics = compute_error_metrics(float("nan"), float("inf"))

    assert metrics["error_status"] == "NONFINITE_VALUE"
    assert metrics["absolute_error"] is None
    assert metrics["pct_error"] is None


def test_compute_steady_state_metrics_reports_stability_and_transient():
    from helical_propeller.analysis_metrics import compute_steady_state_metrics

    stable = compute_steady_state_metrics([1.0] * 10)
    transient = compute_steady_state_metrics([1.0] * 8 + [1.0, 2.0])

    assert stable["steady_last_mean"] == 1.0
    assert stable["steady_prev_mean"] == 1.0
    assert stable["steady_relative_change"] == 0.0
    assert stable["steady_state_status"] == "OK"
    assert transient["steady_state_status"] == "TRANSIENT_LIKELY"


def test_compute_steady_state_metrics_handles_insufficient_and_nonfinite_data():
    from helical_propeller.analysis_metrics import compute_steady_state_metrics

    insufficient = compute_steady_state_metrics([1.0])
    nonfinite = compute_steady_state_metrics([1.0, math.nan])

    assert insufficient["steady_state_status"] == "INSUFFICIENT_DATA"
    assert nonfinite["steady_state_status"] == "NONFINITE_VALUE"


def test_result_status_identifies_nonfinite_velocity_for_exclusion():
    from helical_propeller.analysis_metrics import build_common_result_summary

    summary = build_common_result_summary(
        analytical={"V_sim": float("nan"), "V_theory": 1.0},
        efficiency=None,
        stiffness=None,
    )

    assert summary["status"] == "NAN/INF"
    assert summary["failure_reason"] == "NONFINITE_VELOCITY"
    assert summary["invalid_result"] is True

    history_summary = build_common_result_summary(
        analytical={"V_sim": 1.0, "V_theory": 1.0},
        efficiency=None,
        stiffness=None,
        raw_velocity=[1.0, float("inf"), 1.0],
    )
    assert history_summary["failure_reason"] == "NONFINITE_VELOCITY"
    assert history_summary["invalid_result"] is True

    geometry_risk = build_common_result_summary(
        analytical={
            "V_sim": float("nan"),
            "V_theory": 1.0,
            "theory_warning": "LOW_PITCH_RATIO",
        },
        efficiency=None,
        stiffness=None,
    )
    assert geometry_risk["failure_reason"] == "INVALID_GEOMETRY_OR_DISCRETIZATION"
