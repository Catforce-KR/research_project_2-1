import importlib.util
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_sweep_h2.py"


def _load_run_sweep_h2():
    spec = importlib.util.spec_from_file_location("run_sweep_h2", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_h2_config_is_smoke_sized():
    module = _load_run_sweep_h2()

    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))

    assert config["body_ratio_values"] == [0.3, 0.5]
    assert config["n_elem"] == 6
    assert config["total_steps"] == 5
    assert config["step_skip"] == 1
    assert config["damping_constant"] == 1.0e-5
    assert module.is_smoke_sized(config)


def test_h2_runner_dry_run_does_not_call_sweep(monkeypatch, capsys):
    module = _load_run_sweep_h2()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("parameter_sweep_h2 should not run during dry-run")

    monkeypatch.setitem(
        __import__("sys").modules,
        "helical_propeller.sweeps",
        type("SweepModule", (), {"parameter_sweep_h2": fail_if_called}),
    )

    exit_code = module.main(["--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "damping_constant: 1e-05" in output
    assert "dry-run: simulation not executed" in output


def test_h2_timeseries_logger_uses_body_ratio_filename():
    module = _load_run_sweep_h2()
    calls = []

    def original_logger(sim_result, filepath=None, torque_magnitude=None):
        calls.append((filepath, torque_magnitude))
        return filepath

    logger = module.h2_timeseries_logger(original_logger)
    saved = logger(
        {"parameters": {"body_length_ratio": 0.3}},
        filepath="ignored.csv",
        torque_magnitude=1.0e-8,
    )

    assert saved == "sweep_h2_br0.30_timeseries.csv"
    assert calls == [("sweep_h2_br0.30_timeseries.csv", 1.0e-8)]


def test_h2_summary_prints_analysis_validity_fields(capsys):
    module = _load_run_sweep_h2()

    module.summarize_results({
        0.3: {
            "status": "NAN/INF",
            "body_length": 0.03,
            "V_sim": float("nan"),
            "V_theory": 2.0,
            "pct_error_vs_theory": None,
            "pct_error_vs_sim": None,
            "error_status": "NONFINITE_VALUE",
            "steady_state_status": "NONFINITE_VALUE",
            "failure_reason": "NONFINITE_VELOCITY",
            "invalid_result": True,
        }
    })
    output = capsys.readouterr().out

    assert "error_status=NONFINITE_VALUE" in output
    assert "failure_reason=NONFINITE_VELOCITY" in output
    assert "invalid_result=True" in output


def test_parameter_sweep_h2_marks_nonfinite_result_invalid(monkeypatch):
    if str(PROJECT_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from helical_propeller import sweeps

    velocity = np.array([[0.0, 0.0], [0.0, 0.0], [float("nan"), float("nan")]])

    calls = []

    def fake_run_simulation(**kwargs):
        calls.append(kwargs)
        return {
            "final_velocity": velocity,
            "velocity": [velocity] * 5,
            "time": [0.0],
            "parameters": kwargs,
            "analytical": {
                "V_sim": float("nan"),
                "V_theory": 2.0,
                "error_status": "NONFINITE_VALUE",
                "steady_state_status": "NONFINITE_VALUE",
                "omega_z": 1.0,
                "C_t": 1.0,
                "damping_constant": kwargs["damping_constant"],
            },
            "stiffness": None,
        }

    monkeypatch.setattr(sweeps, "run_simulation", fake_run_simulation)
    monkeypatch.setattr(sweeps, "log_sweep_summary", lambda *args, **kwargs: None)
    row = sweeps.parameter_sweep_h2(
        body_ratio_values=[0.3],
        total_steps=1,
        step_skip=1,
        damping_constant=1.0e-5,
    )[0.3]

    assert row["status"] == "NAN/INF"
    assert row["failure_reason"] == "NONFINITE_VELOCITY"
    assert row["invalid_result"] is True
    assert row["damping_constant"] == 1.0e-5
    assert calls[0]["damping_constant"] == 1.0e-5
