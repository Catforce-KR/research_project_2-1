import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_stiffness_calibration.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_stiffness_calibration", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_stiffness_calibration_config_is_within_limits():
    module = _load_runner()

    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))

    assert config["pitch"] == 0.02
    assert config["radius"] == 0.01
    assert config["body_length_ratio"] == 0.5
    assert config["n_elem"] == 20
    assert config["total_steps"] == 1000
    assert config["step_skip"] == 10
    assert config["E_values"] == [1.0e6, 3.0e6, 1.0e7, 3.0e7]
    assert not module.exceeds_smoke_limits(config)


def test_stiffness_calibration_dry_run_does_not_execute(capsys):
    module = _load_runner()

    exit_code = module.main(["--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stiffness candidate check before full sweeps" in output
    assert "dry-run: calibration not executed" in output


def test_stiffness_calibration_summary_prints_per_e_rows(capsys):
    module = _load_runner()
    result = {
        "results": {
            1.0e6: {
                "status": "OK",
                "worst_metric_pct": 0.1,
                "deformation_exceeded": False,
            }
        },
        "threshold_crossed": 1.0e6,
        "recommended_E": 2.0e6,
        "recommended_G": 6.666666666666667e5,
        "all_deformed": False,
        "all_ok": True,
    }

    module.print_result_summary(result)
    output = capsys.readouterr().out

    assert "tested_E_values: [1000000.0]" in output
    assert "recommended_E: 2000000.0" in output
    assert "E=1.000e+06, status=OK" in output


def test_stiffness_timeseries_logger_uses_e_specific_filename():
    module = _load_runner()
    calls = []

    def original_logger(sim_result, filepath=None, torque_magnitude=None):
        calls.append((filepath, torque_magnitude))
        return filepath

    logger = module.stiffness_timeseries_logger(original_logger)
    saved = logger(
        {
            "parameters": {
                "E": 3.0e6,
                "n_elem": 20,
                "pitch": 0.02,
                "radius": 0.01,
                "torque_magnitude": 1.0e-8,
            }
        },
        filepath="ignored.csv",
        torque_magnitude=1.0e-8,
    )

    assert saved == "stiffness_E3e6_N20_pr2.00_T1e-08.csv"
    assert calls == [("stiffness_E3e6_N20_pr2.00_T1e-08.csv", 1.0e-8)]
