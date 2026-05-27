"""Post-processing metrics and validity classification for simulation results."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np


EPS = 1e-30

ANALYSIS_FIELDS = (
    "V_sim",
    "V_theory",
    "absolute_error",
    "signed_error",
    "pct_error",
    "pct_error_vs_theory",
    "pct_error_vs_sim",
    "error_status",
    "steady_last_mean",
    "steady_prev_mean",
    "steady_relative_change",
    "steady_std",
    "steady_std_over_mean",
    "steady_state_status",
    "omega_theory",
    "omega_sim",
    "omega_last_mean",
    "omega_prev_mean",
    "omega_relative_change",
    "omega_std",
    "omega_std_over_mean",
    "omega_state_status",
    "theory_mode",
    "theory_warning",
    "helix_angle",
    "helix_angle_deg",
    "body_translational_drag",
    "body_rotational_drag",
    "A",
    "B",
    "D",
    "A_total",
    "D_total",
    "force_residual",
    "force_residual_norm",
    "torque_residual",
    "torque_residual_norm",
    "effective_rotational_resistance",
    "effective_rotational_resistance_ratio",
)

EFFICIENCY_FIELDS = (
    "Eta_slip",
    "Eta_power",
    "P_in",
    "P_out",
    "omega_used",
    "omega_source",
    "efficiency_model",
)
STIFFNESS_FIELDS = ("stiffness_status", "deformation_exceeded", "worst_metric_pct")
RESULT_STATUS_FIELDS = ("status", "failure_reason", "invalid_result")
COMMON_RESULT_FIELDS = (
    *RESULT_STATUS_FIELDS,
    *ANALYSIS_FIELDS,
    *EFFICIENCY_FIELDS,
    *STIFFNESS_FIELDS,
)


def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_nonfinite(value) -> bool:
    converted = _as_float(value)
    return converted is not None and not math.isfinite(converted)


def compute_error_metrics(V_sim, V_theory, eps: float = EPS) -> dict:
    """Return velocity errors with explicit denominator validity status.

    ``pct_error`` remains a compatibility alias for the historical
    simulation-referenced denominator and equals ``pct_error_vs_sim``.
    """
    v_sim = _as_float(V_sim)
    v_theory = _as_float(V_theory)
    metrics = {
        "absolute_error": None,
        "signed_error": None,
        "pct_error": None,
        "pct_error_vs_theory": None,
        "pct_error_vs_sim": None,
        "error_status": "UNDEFINED",
    }

    if v_sim is None or v_theory is None:
        return metrics
    if not math.isfinite(v_sim) or not math.isfinite(v_theory):
        metrics["error_status"] = "NONFINITE_VALUE"
        return metrics

    absolute_error = abs(v_sim - v_theory)
    metrics["absolute_error"] = absolute_error
    metrics["signed_error"] = v_sim - v_theory

    sim_near_zero = abs(v_sim) <= eps
    theory_near_zero = abs(v_theory) <= eps
    if sim_near_zero and theory_near_zero:
        metrics["error_status"] = "BOTH_NEAR_ZERO"
    elif sim_near_zero:
        metrics["pct_error_vs_theory"] = absolute_error / abs(v_theory) * 100.0
        metrics["error_status"] = "SIM_NEAR_ZERO"
    elif theory_near_zero:
        metrics["pct_error_vs_sim"] = absolute_error / abs(v_sim) * 100.0
        metrics["pct_error"] = metrics["pct_error_vs_sim"]
        metrics["error_status"] = "THEORY_NEAR_ZERO"
    else:
        metrics["pct_error_vs_theory"] = absolute_error / abs(v_theory) * 100.0
        metrics["pct_error_vs_sim"] = absolute_error / abs(v_sim) * 100.0
        metrics["pct_error"] = metrics["pct_error_vs_sim"]
        metrics["error_status"] = "OK"

    return metrics


def compute_steady_state_metrics(
    values: Iterable,
    relative_change_threshold: float = 0.1,
    std_over_mean_threshold: float = 0.2,
    eps: float = EPS,
) -> dict:
    """Measure whether the last 20 percent window appears approximately steady."""
    metrics = {
        "steady_last_mean": None,
        "steady_prev_mean": None,
        "steady_relative_change": None,
        "steady_std": None,
        "steady_std_over_mean": None,
        "steady_state_status": "INSUFFICIENT_DATA",
    }
    try:
        series = np.asarray(list(values), dtype=float).reshape(-1)
    except (TypeError, ValueError):
        metrics["steady_state_status"] = "NONFINITE_VALUE"
        return metrics

    if series.size < 2:
        return metrics

    window_size = max(1, series.size // 5)
    if series.size < 2 * window_size:
        return metrics

    last_window = series[-window_size:]
    prev_window = series[-2 * window_size:-window_size]
    last_mean = float(np.mean(last_window))
    prev_mean = float(np.mean(prev_window))
    steady_std = float(np.std(last_window))
    metrics.update({
        "steady_last_mean": last_mean,
        "steady_prev_mean": prev_mean,
        "steady_std": steady_std,
    })

    if not all(math.isfinite(value) for value in (last_mean, prev_mean, steady_std)):
        metrics["steady_state_status"] = "NONFINITE_VALUE"
        return metrics

    if abs(last_mean) <= eps:
        metrics["steady_state_status"] = "MEAN_NEAR_ZERO"
        return metrics

    relative_change = abs(last_mean - prev_mean) / max(abs(last_mean), eps)
    std_over_mean = steady_std / max(abs(last_mean), eps)
    metrics["steady_relative_change"] = relative_change
    metrics["steady_std_over_mean"] = std_over_mean
    if (
        relative_change > relative_change_threshold
        or std_over_mean > std_over_mean_threshold
    ):
        metrics["steady_state_status"] = "TRANSIENT_LIKELY"
    else:
        metrics["steady_state_status"] = "OK"
    return metrics


def summarize_result_status(
    status: str = "OK",
    analytical: dict | None = None,
    efficiency: dict | None = None,
    stiffness: dict | None = None,
    raw_velocity=None,
) -> dict:
    """Classify a result for exclusion without altering physical calculations."""
    analytical = analytical or {}
    efficiency = efficiency or {}
    stiffness = stiffness or {}
    effective_status = status or "OK"
    failure_reason = "NONE"

    raw_array = None if raw_velocity is None else np.asarray(raw_velocity)
    geometry_risk = analytical.get("theory_warning") == "LOW_PITCH_RATIO"
    if raw_array is not None and raw_array.size and not np.all(np.isfinite(raw_array)):
        failure_reason = (
            "INVALID_GEOMETRY_OR_DISCRETIZATION" if geometry_risk
            else "NONFINITE_VELOCITY"
        )
    elif _is_nonfinite(analytical.get("V_sim")):
        failure_reason = (
            "INVALID_GEOMETRY_OR_DISCRETIZATION" if geometry_risk
            else "NONFINITE_VELOCITY"
        )
    elif analytical.get("steady_state_status") == "NONFINITE_VALUE":
        failure_reason = "NONFINITE_VELOCITY"
    elif _is_nonfinite(analytical.get("V_theory")):
        failure_reason = "NONFINITE_THEORY"
    elif any(
        _is_nonfinite(efficiency.get(key))
        for key in ("eta_slip", "eta_power", "P_in", "P_out")
    ):
        failure_reason = "NONFINITE_EFFICIENCY"
    elif any(
        _is_nonfinite(stiffness.get(key))
        for key in (
            "max_displacement_pct",
            "pitch_deformation_pct",
            "max_pitch_deviation_pct",
            "kappa_deformation_pct",
            "sigma_deformation_pct",
            "worst_metric_pct",
        )
    ):
        failure_reason = "NONFINITE_STIFFNESS"
    elif effective_status in ("NAN/INF", "NONFINITE_VALUE"):
        failure_reason = "NONFINITE_VELOCITY"
    elif effective_status in ("BUCKLING", "UNSTABLE", "INCONSISTENT"):
        failure_reason = "NUMERICAL_INSTABILITY"
    elif effective_status == "INVALID_GEOMETRY_OR_DISCRETIZATION":
        failure_reason = "INVALID_GEOMETRY_OR_DISCRETIZATION"
    elif effective_status != "OK":
        failure_reason = "UNKNOWN"

    invalid_result = failure_reason != "NONE"
    if invalid_result and effective_status == "OK":
        effective_status = "NAN/INF" if failure_reason.startswith("NONFINITE_") else "INVALID"
    return {
        "status": effective_status,
        "failure_reason": failure_reason,
        "invalid_result": invalid_result,
    }


def build_common_result_summary(
    analytical: dict | None,
    efficiency: dict | None,
    stiffness: dict | None,
    status: str = "OK",
    raw_velocity=None,
) -> dict:
    """Flatten common analysis, efficiency, stiffness, and validity fields."""
    analytical = dict(analytical or {})
    efficiency = efficiency or {}
    stiffness = stiffness or {}

    if analytical.get("V_sim") is not None and analytical.get("V_theory") is not None:
        for key, value in compute_error_metrics(
            analytical.get("V_sim"),
            analytical.get("V_theory"),
        ).items():
            analytical.setdefault(key, value)

    summary = {field: analytical.get(field) for field in ANALYSIS_FIELDS}
    summary.update({
        "Eta_slip": efficiency.get("eta_slip"),
        "Eta_power": efficiency.get("eta_power"),
        "P_in": efficiency.get("P_in"),
        "P_out": efficiency.get("P_out"),
        "omega_used": efficiency.get("omega_used"),
        "omega_source": efficiency.get("omega_source"),
        "efficiency_model": efficiency.get("efficiency_model"),
        "stiffness_status": stiffness.get("status"),
        "deformation_exceeded": stiffness.get("deformation_exceeded"),
        "worst_metric_pct": stiffness.get("worst_metric_pct"),
    })
    summary.update(
        summarize_result_status(
            status=status,
            analytical=analytical,
            efficiency=efficiency,
            stiffness=stiffness,
            raw_velocity=raw_velocity,
        )
    )
    return summary
