import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_damping_check.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_damping_check", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_damping_config_has_requested_pr3_cases():
    module = _load_runner()

    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))

    assert config["pitch"] / config["radius"] == 3.0
    assert config["n_elem"] == 80
    assert config["total_steps"] == 120000
    assert config["step_skip"] == 1200
    assert config["damping_constants"] == [1.0e-3, 1.0e-4, 1.0e-5]


def test_damping_summary_maps_requested_fields():
    module = _load_runner()
    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))
    result = {
        "final_time": 1.2,
        "invalid_result": False,
        "failure_reason": "NONE",
        "analytical": {
            "V_sim": 2.0,
            "V_theory": 4.0,
            "omega_sim": 1.0,
            "omega_theory": 3.0,
            "damping_torque_to_applied_ratio": 0.5,
            "torque_residual_to_applied_ratio": 0.8,
            "torque_balance_with_damping_residual_ratio": 0.03,
            "steady_state_status": "OK",
            "omega_state_status": "TRANSIENT_LIKELY",
        },
        "stiffness": {
            "status": "OK",
            "deformation_exceeded": False,
        },
    }

    row = module.build_summary_row(result, config, damping_constant=1.0e-4)

    assert row["damping_constant"] == 1.0e-4
    assert row["V_theory_over_V_sim"] == 2.0
    assert row["omega_theory_over_omega_sim"] == 3.0
    assert row["damping_torque_to_applied_ratio"] == 0.5
    assert row["torque_residual_to_applied_ratio"] == 0.8
    assert row["torque_balance_with_damping_residual_ratio"] == 0.03
    assert row["omega_steady_state_status"] == "TRANSIENT_LIKELY"
    assert row["stiffness_status"] == "OK"
    assert row["deformation_exceeded"] is False


def test_damping_runner_dry_run_reports_cases_without_simulation(capsys):
    module = _load_runner()

    exit_code = module.main(["--dry-run", "--max-cases", "2"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "damping_constants: [0.001, 0.0001]" in output
    assert "dry-run: simulation not executed" in output
