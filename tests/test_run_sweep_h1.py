import importlib.util
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_sweep_h1.py"


def _load_run_sweep_h1():
    spec = importlib.util.spec_from_file_location("run_sweep_h1", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_h1_config_is_smoke_sized():
    module = _load_run_sweep_h1()

    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))

    assert config["pr_values"] == [1.0, 2.0]
    assert config["n_elem"] == 6
    assert config["total_steps"] == 5
    assert config["step_skip"] == 1
    assert module.is_smoke_sized(config)


def test_h1_runner_dry_run_does_not_call_sweep(monkeypatch, capsys):
    module = _load_run_sweep_h1()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("parameter_sweep_h1 should not run during dry-run")

    monkeypatch.setitem(
        __import__("sys").modules,
        "helical_propeller.sweeps",
        type("SweepModule", (), {"parameter_sweep_h1": fail_if_called}),
    )

    exit_code = module.main(["--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "dry-run: simulation not executed" in output


def test_h1_summary_prints_analysis_validity_fields(capsys):
    module = _load_run_sweep_h1()

    module.summarize_results({
        1.0: {
            "status": "OK",
            "pitch": 0.01,
            "V_sim": 1.0,
            "V_theory": 2.0,
            "pct_error_vs_theory": 50.0,
            "pct_error_vs_sim": 100.0,
            "error_status": "OK",
            "steady_state_status": "OK",
            "failure_reason": "NONE",
            "invalid_result": False,
        }
    })
    output = capsys.readouterr().out

    assert "V_sim=1.0" in output
    assert "pct_error_vs_theory=50.0" in output
    assert "failure_reason=NONE" in output


def test_parameter_sweep_h1_flattens_common_metrics(monkeypatch):
    if str(PROJECT_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from helical_propeller import sweeps

    velocity = np.array([[0.0, 0.0], [0.0, 0.0], [1.0e-3, 1.0e-3]])

    def fake_run_simulation(**kwargs):
        return {
            "final_velocity": velocity,
            "velocity": [velocity] * 5,
            "time": [0.0],
            "parameters": kwargs,
            "analytical": {
                "V_sim": 1.0,
                "V_theory": 2.0,
                "pct_error_vs_theory": 50.0,
                "pct_error_vs_sim": 100.0,
                "pct_error": 100.0,
                "error_status": "OK",
                "steady_state_status": "OK",
                "omega_z": 1.0,
                "C_t": 1.0,
            },
            "stiffness": {
                "status": "OK",
                "deformation_exceeded": False,
                "worst_metric_pct": 0.1,
            },
        }

    monkeypatch.setattr(sweeps, "run_simulation", fake_run_simulation)
    monkeypatch.setattr(sweeps, "log_sweep_summary", lambda *args, **kwargs: None)
    row = sweeps.parameter_sweep_h1(pr_values=[1.0], total_steps=1, step_skip=1)[1.0]

    assert row["pct_error_vs_theory"] == 50.0
    assert row["steady_state_status"] == "OK"
    assert row["failure_reason"] == "NONE"
    assert row["invalid_result"] is False
