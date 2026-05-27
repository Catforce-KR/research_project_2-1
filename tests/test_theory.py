import math
import sys
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def test_compute_theoretical_velocity_basic_output():
    from helical_propeller.theory import compute_theoretical_velocity

    result = compute_theoretical_velocity(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        fluid_viscosity=0.1,
        torque_magnitude=1.0e-8,
    )

    assert result["pitch"] == 0.02
    assert result["radius"] == 0.01
    assert math.isfinite(result["V_theory"])
    assert result["C_t"] > 0.0
    assert result["C_n"] > 0.0
    assert result["Cn_over_Ct"] > 1.0
    assert math.isfinite(result["omega_theory"])
    assert result["theory_mode"] == "torque_driven_rft"
    assert result["A_total"] > result["A"]
    assert result["D_total"] > result["D"]


def test_torque_driven_theory_scales_with_applied_torque():
    from helical_propeller.theory import compute_theoretical_velocity

    low = compute_theoretical_velocity(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        torque_magnitude=1.0e-8,
    )
    high = compute_theoretical_velocity(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        torque_magnitude=2.0e-8,
    )

    assert high["V_theory"] > low["V_theory"] > 0.0
    assert high["omega_theory"] > low["omega_theory"] > 0.0
    assert math.isclose(high["V_theory"], 2.0 * low["V_theory"])


def test_balance_diagnostics_are_zero_for_solved_theory_state():
    from helical_propeller.theory import (
        compute_balance_diagnostics,
        compute_theoretical_velocity,
    )

    theory = compute_theoretical_velocity(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        torque_magnitude=1.0e-8,
    )
    diagnostics = compute_balance_diagnostics(
        V_sim=theory["V_theory"],
        omega_sim=theory["omega_theory"],
        A_total=theory["A_total"],
        B=theory["B"],
        D_total=theory["D_total"],
        torque_magnitude=1.0e-8,
    )

    assert math.isclose(diagnostics["force_residual"], 0.0, abs_tol=1.0e-20)
    assert math.isclose(diagnostics["torque_residual"], 0.0, abs_tol=1.0e-20)
    assert math.isclose(
        diagnostics["effective_rotational_resistance_ratio"],
        1.0,
        rel_tol=1.0e-12,
    )


def test_body_rotational_drag_reduces_torque_driven_velocity():
    from helical_propeller.theory import compute_theoretical_velocity

    compact_body = compute_theoretical_velocity(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        torque_magnitude=1.0e-8,
        body_radius=0.01,
    )
    wide_body = compute_theoretical_velocity(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        torque_magnitude=1.0e-8,
        body_radius=0.03,
    )

    assert wide_body["body_rotational_drag"] > compact_body["body_rotational_drag"]
    assert wide_body["V_theory"] < compact_body["V_theory"]


def test_low_pitch_ratio_is_reported_as_theory_warning():
    from helical_propeller.theory import compute_theoretical_velocity

    result = compute_theoretical_velocity(
        pitch=0.005,
        radius=0.01,
        total_length=0.1,
        torque_magnitude=1.0e-8,
    )

    assert result["theory_warning"] == "LOW_PITCH_RATIO"


def test_theory_geometry_uses_pitch_per_turn_and_axial_tail_span():
    from helical_propeller.theory import compute_helix_geometry

    geometry = compute_helix_geometry(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        body_length_ratio=0.5,
    )

    assert geometry["pitch_over_radius"] == 2.0
    assert geometry["body_length"] == 0.05
    assert geometry["tail_axial_length"] == 0.05
    assert geometry["tail_contour_length"] > geometry["tail_axial_length"]


def test_analytical_comparison_includes_error_and_steady_state_metrics():
    import numpy as np

    from helical_propeller.theory import analytical_comparison

    omega = np.array([[0.0], [0.0], [1.0]])
    result = analytical_comparison({
        "parameters": {
            "pitch": 0.02,
            "radius": 0.01,
            "total_length": 0.1,
            "body_length_ratio": 0.5,
            "torque_magnitude": 1.0e-8,
        },
        "omega_history": [np.zeros_like(omega)] * 10,
        "omega_z_history": [1.0] * 10,
        "vz_history": [1.0e-3] * 10,
    })

    assert result["V_sim"] == 1.0e-3
    assert result["error_status"] == "OK"
    assert result["pct_error"] == result["pct_error_vs_sim"]
    assert result["steady_last_mean"] == result["V_sim"]
    assert result["steady_state_status"] == "OK"
    assert result["omega_sim"] == 1.0
    assert result["theory_mode"] == "torque_driven_rft"
    assert result["A_total"] > result["A"]
    assert math.isfinite(result["force_residual_norm"])
    assert math.isfinite(result["torque_residual_norm"])
