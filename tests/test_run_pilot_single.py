import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_pilot_single.py"


def _load_run_pilot_single():
    spec = importlib.util.spec_from_file_location("run_pilot_single", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_pilot_config_is_within_limits():
    module = _load_run_pilot_single()

    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))

    assert config["pitch"] == 0.02
    assert config["radius"] == 0.01
    assert config["body_length_ratio"] == 0.5
    assert config["n_elem"] == 20
    assert config["total_steps"] == 1000
    assert config["step_skip"] == 10
    assert not module.exceeds_pilot_limits(config)


def test_pilot_runner_dry_run_does_not_import_simulation(capsys):
    module = _load_run_pilot_single()

    exit_code = module.main(["--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "representative-condition check before full sweeps" in output
    assert "dry-run: simulation not executed" in output


def test_pilot_summary_prints_analysis_validity_fields(capsys):
    module = _load_run_pilot_single()

    module.print_result_summary(
        {
            "final_time": 1.0,
            "analytical": {
                "V_sim": 1.0,
                "V_theory": 2.0,
                "pct_error_vs_theory": 50.0,
                "pct_error_vs_sim": 100.0,
                "error_status": "OK",
                "steady_state_status": "TRANSIENT_LIKELY",
            },
            "failure_reason": "NONE",
            "invalid_result": False,
        },
        {},
    )
    output = capsys.readouterr().out

    assert "pct_error_vs_theory: 50.0" in output
    assert "steady_state_status: TRANSIENT_LIKELY" in output
    assert "invalid_result: False" in output
