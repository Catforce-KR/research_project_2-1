import sys
import csv
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _redirect_output_dirs(monkeypatch, tmp_path):
    import helical_propeller.logging_utils as logging_utils

    monkeypatch.setattr(logging_utils, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(logging_utils, "DATA_RAW_DIR", tmp_path / "data" / "raw")
    monkeypatch.setattr(logging_utils, "DATA_PROCESSED_DIR", tmp_path / "data" / "processed")
    return logging_utils


def _minimal_sim_result():
    return {
        "time": [0.0, 1.0],
        "velocity": [
            np.array([[0.0, 0.0], [0.0, 0.0], [1.0e-9, 1.0e-9]]),
            np.array([[0.0, 0.0], [0.0, 0.0], [2.0e-9, 2.0e-9]]),
        ],
        "omega": [
            np.array([[0.0], [0.0], [1.0]]),
            np.array([[0.0], [0.0], [1.0]]),
        ],
        "parameters": {
            "body_length_ratio": 0.5,
            "total_length": 0.1,
            "torque_magnitude": 1.0e-8,
        },
        "analytical": {
            "C_t": 1.0,
            "pct_error": 0.0,
            "V_theory": 2.0e-9,
        },
    }


def _minimal_sweep_results():
    sim_result = _minimal_sim_result()
    return {
        1.0: {
            "status": "OK",
            "pitch": 0.01,
            "vz_final_mean": 2.0e-9,
            "vz_com_avg": 1.5e-9,
            "time": sim_result["time"],
            "velocity_history": sim_result["velocity"],
            "parameters": sim_result["parameters"],
            "analytical": {
                "pct_error": 0.0,
                "V_theory": 2.0e-9,
                "V_sim": 2.0e-9,
                "Cn_over_Ct": 2.0,
                "absolute_error": 0.0,
                "signed_error": 0.0,
                "pct_error_vs_theory": 0.0,
                "pct_error_vs_sim": 0.0,
                "error_status": "OK",
                "steady_last_mean": 2.0e-9,
                "steady_prev_mean": 2.0e-9,
                "steady_relative_change": 0.0,
                "steady_std": 0.0,
                "steady_std_over_mean": 0.0,
                "steady_state_status": "OK",
                "omega_theory": 3.0,
                "omega_sim": 2.0,
                "theory_mode": "torque_driven_rft",
                "helix_angle": 0.3,
                "body_translational_drag": 0.5,
                "body_rotational_drag": 0.01,
                "A": 1.0,
                "B": 2.0,
                "D": 3.0,
                "A_total": 1.5,
                "D_total": 3.01,
                "force_residual": 0.1,
                "force_residual_norm": 0.2,
                "torque_residual": 0.3,
                "torque_residual_norm": 0.4,
                "effective_rotational_resistance": 4.0,
                "effective_rotational_resistance_ratio": 1.25,
            },
            "efficiency": {
                "eta_slip": 0.1,
                "eta_power": 0.01,
                "P_in": 1.0e-8,
                "P_out": 1.0e-10,
                "omega_used": 2.0,
                "omega_source": "omega_sim",
                "efficiency_model": "rft_useful_power_ratio",
            },
            "stiffness": {
                "status": "OK",
                "deformation_exceeded": False,
                "worst_metric_pct": 0.5,
            },
            "stiffness_status": "OK",
            "deformation_exceeded": False,
            "worst_metric_pct": 0.5,
            "failure_reason": "NONE",
            "invalid_result": False,
        }
    }


def test_log_simulation_timeseries_defaults_to_data_raw(tmp_path, monkeypatch):
    logging_utils = _redirect_output_dirs(monkeypatch, tmp_path)

    saved = logging_utils.log_simulation_timeseries(_minimal_sim_result(), filepath="single.csv")

    assert Path(saved) == Path("data/raw/single.csv")
    assert (tmp_path / "data" / "raw" / "single.csv").is_file()


def test_log_sweep_summary_defaults_to_data_processed(tmp_path, monkeypatch):
    logging_utils = _redirect_output_dirs(monkeypatch, tmp_path)

    saved = logging_utils.log_sweep_summary(
        _minimal_sweep_results(),
        filepath="sweep_summary.csv",
        sweep_type="h1",
    )

    assert Path(saved) == Path("data/processed/sweep_summary.csv")
    assert (tmp_path / "data" / "processed" / "sweep_summary.csv").is_file()

    with (tmp_path / "data" / "processed" / "sweep_summary.csv").open(newline="") as f:
        row = next(csv.DictReader(f))

    assert row["V_sim"] == "2e-09"
    assert row["V_theory"] == "2e-09"
    assert row["pct_error"] == "0.0"
    assert row["pct_error_vs_theory"] == "0.0"
    assert row["pct_error_vs_sim"] == "0.0"
    assert row["error_status"] == "OK"
    assert row["steady_state_status"] == "OK"
    assert row["failure_reason"] == "NONE"
    assert row["invalid_result"] == "False"
    assert row["omega_theory"] == "3.0"
    assert row["omega_sim"] == "2.0"
    assert row["theory_mode"] == "torque_driven_rft"
    assert row["A_total"] == "1.5"
    assert row["body_translational_drag"] == "0.5"
    assert row["force_residual_norm"] == "0.2"
    assert row["torque_residual_norm"] == "0.4"
    assert row["effective_rotational_resistance"] == "4.0"
    assert row["effective_rotational_resistance_ratio"] == "1.25"
    assert row["omega_used"] == "2.0"
    assert row["omega_source"] == "omega_sim"
    assert row["efficiency_model"] == "rft_useful_power_ratio"
    assert row["Eta_slip"] == "0.1"
    assert row["Eta_power"] == "0.01"
    assert row["stiffness_status"] == "OK"
    assert row["deformation_exceeded"] == "False"
    assert row["worst_metric_pct"] == "0.5"


def test_log_all_sweep_data_splits_summary_and_detail_paths(tmp_path, monkeypatch):
    logging_utils = _redirect_output_dirs(monkeypatch, tmp_path)

    saved = logging_utils.log_all_sweep_data(
        _minimal_sweep_results(),
        base_filename="sweep",
        sweep_type="h1",
    )

    assert Path(saved["summary"]) == Path("data/processed/sweep_summary.csv")
    assert Path(saved["ts_pr1.00"]) == Path("data/raw/sweep_pr1.00_timeseries.csv")
    assert (tmp_path / "data" / "processed" / "sweep_summary.csv").is_file()
    assert (tmp_path / "data" / "raw" / "sweep_pr1.00_timeseries.csv").is_file()


def test_log_sweep_summary_writes_nonfinite_invalid_row(tmp_path, monkeypatch):
    logging_utils = _redirect_output_dirs(monkeypatch, tmp_path)
    result = _minimal_sweep_results()
    row = result[1.0]
    row.update({
        "status": "NAN/INF",
        "failure_reason": "NONFINITE_VELOCITY",
        "invalid_result": True,
    })
    row["analytical"].update({
        "V_sim": float("nan"),
        "error_status": "NONFINITE_VALUE",
        "steady_state_status": "NONFINITE_VALUE",
    })

    saved = logging_utils.log_sweep_summary(result, filepath="invalid.csv", sweep_type="h1")

    assert Path(saved) == Path("data/processed/invalid.csv")
    with (tmp_path / "data" / "processed" / "invalid.csv").open(newline="") as f:
        saved_row = next(csv.DictReader(f))
    assert saved_row["invalid_result"] == "True"
    assert saved_row["failure_reason"] == "NONFINITE_VELOCITY"
    assert saved_row["error_status"] == "NONFINITE_VALUE"
