import sys
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def test_compute_efficiency_from_analytical_result():
    from helical_propeller.efficiency import compute_efficiency

    sim_result = {
        "analytical": {
            "V_sim": 1.0e-4,
            "omega_sim": 2.0,
            "omega_theory": 3.0,
            "C_t": 0.5,
            "body_translational_drag": 0.025,
        },
        "parameters": {
            "pitch": 0.02,
            "total_length": 0.1,
            "body_length_ratio": 0.5,
            "torque_magnitude": 1.0e-8,
        },
    }

    result = compute_efficiency(sim_result)

    assert result is not None
    assert result["eta_slip"] > 0.0
    assert result["eta_power"] > 0.0
    assert result["body_length"] == 0.05
    assert result["tail_length"] == 0.05
    assert result["omega_used"] == 2.0
    assert result["omega_source"] == "omega_sim"
    assert result["efficiency_model"] == "rft_useful_power_ratio"
    assert result["Eta_power"] == result["eta_power"]


def test_compute_efficiency_uses_theory_omega_when_sim_omega_unavailable():
    from helical_propeller.efficiency import compute_efficiency

    result = compute_efficiency({
        "analytical": {
            "V_sim": 1.0e-4,
            "omega_theory": 3.0,
            "C_t": 0.5,
        },
        "parameters": {"pitch": 0.02, "total_length": 0.1, "torque_magnitude": 1.0e-8},
    })

    assert result["omega_used"] == 3.0
    assert result["omega_source"] == "omega_theory"


def test_compute_efficiency_returns_none_without_analytical_data():
    from helical_propeller.efficiency import compute_efficiency

    assert compute_efficiency({"parameters": {}}) is None
