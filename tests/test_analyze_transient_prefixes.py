import importlib.util
import math
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "analyze_transient_prefixes.py"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_analyzer():
    spec = importlib.util.spec_from_file_location("analyze_transient_prefixes", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config():
    return {
        "pitch": 0.03,
        "radius": 0.01,
        "total_length": 0.1,
        "body_length_ratio": 0.5,
        "torque_magnitude": 1.0e-8,
        "dt": 1.0e-5,
        "total_steps": [10],
        "fluid_viscosity": 0.1,
        "density": 1000.0,
    }


def test_analyze_prefixes_reuses_steady_and_balance_metrics():
    module = _load_analyzer()
    timeseries = pd.DataFrame({
        "Time": [value * 1.0e-5 for value in range(11)],
        "Vz_mean": [1.0e-7] * 11,
        "Omega_z": [2.0e-4] * 11,
    })

    summary = module.analyze_prefixes(timeseries, _config(), [10])
    row = summary.iloc[0]

    assert row["sample_count"] == 11
    assert row["window_samples"] == 2
    assert row["V_sim"] == 1.0e-7
    assert row["omega_sim"] == 2.0e-4
    assert row["steady_state_status"] == "OK"
    assert row["omega_steady_state_status"] == "OK"
    assert row["failure_reason"] == "NONE"
    assert not row["invalid_result"]
    assert row["total_rotational_resistance"] > 0.0
    assert math.isclose(
        row["body_rotational_fraction"] + row["helix_rotational_fraction"],
        1.0,
        rel_tol=1.0e-12,
    )
    assert row["torque_rotational_to_applied_ratio"] >= 0.0
    assert row["torque_residual_to_applied_ratio"] >= 0.0
    assert row["torque_frame_assumption"] == "ASSUMED_MATERIAL_COMPONENT_2"
    assert row["omega_frame"] == "INERTIAL_GLOBAL_Z"
    assert row["torque_frame_status"] == "PROJECTION_UNAVAILABLE"
    assert row["damping_estimate_status"] == "ESTIMATED_FROM_MEAN_GLOBAL_Z_OMEGA_LEGACY_RAW"
    assert row["damping_torque_estimate"] is not None


def test_analyze_prefixes_rejects_checkpoint_past_run_length():
    module = _load_analyzer()
    timeseries = pd.DataFrame({
        "Time": [0.0],
        "Vz_mean": [0.0],
        "Omega_z": [0.0],
    })

    try:
        module.analyze_prefixes(timeseries, _config(), [11])
    except ValueError as exc:
        assert "exceeds configured total_steps" in str(exc)
    else:
        raise AssertionError("Expected checkpoint range validation failure")
