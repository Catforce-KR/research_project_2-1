import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_transient_check.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_transient_check", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_transient_config_has_requested_pr3_duration_series():
    module = _load_runner()

    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))

    assert config["pitch"] / config["radius"] == 3.0
    assert config["n_elem"] == 80
    assert config["total_steps"] == [10000, 30000, 60000]
    assert config["step_skip"] == [100, 300, 600]


def test_transient_summary_maps_existing_diagnostic_fields():
    module = _load_runner()
    result = {
        "final_time": 0.3,
        "invalid_result": False,
        "failure_reason": "NONE",
        "analytical": {
            "V_sim": 2.0,
            "V_theory": 4.0,
            "omega_sim": 1.0,
            "omega_theory": 3.0,
            "pct_error_vs_theory": 50.0,
            "error_status": "OK",
            "steady_state_status": "TRANSIENT_LIKELY",
            "omega_state_status": "TRANSIENT_LIKELY",
            "steady_relative_change": 0.2,
            "omega_relative_change": 0.3,
            "force_residual_norm": 0.4,
            "torque_residual_norm": 0.5,
            "effective_rotational_resistance": 0.6,
            "effective_rotational_resistance_ratio": 7.0,
            "D_total": 0.1,
        },
    }

    row = module.build_summary_row(result, total_steps=30000, step_skip=300)

    assert row["V_theory_over_V_sim"] == 2.0
    assert row["omega_theory_over_omega_sim"] == 3.0
    assert row["omega_steady_state_status"] == "TRANSIENT_LIKELY"
    assert row["effective_D_from_omega_sim"] == 0.6
    assert row["effective_rotational_resistance_ratio"] == 7.0


def test_transient_runner_dry_run_reports_cases_without_simulation(capsys):
    module = _load_runner()

    exit_code = module.main(["--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "total_steps=60000" in output
    assert "dry-run: simulation not executed" in output
