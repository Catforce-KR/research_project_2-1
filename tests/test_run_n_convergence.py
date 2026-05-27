import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "run_n_convergence.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_n_convergence", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_n_convergence_config_is_within_limits():
    module = _load_runner()

    config = module.normalize_config(module.load_config(module.DEFAULT_CONFIG))

    assert config["pitch"] == 0.02
    assert config["radius"] == 0.01
    assert config["body_length_ratio"] == 0.5
    assert config["n_values"] == [20, 40, 80]
    assert config["total_steps"] == 1000
    assert config["step_skip"] == 10
    assert not module.exceeds_smoke_limits(config)


def test_n_convergence_dry_run_does_not_execute(capsys):
    module = _load_runner()

    exit_code = module.main(["--dry-run"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "n_elem candidate check before full sweeps" in output
    assert "dry-run: convergence not executed" in output


def test_n_convergence_summary_prints_candidate_rows(capsys):
    module = _load_runner()
    result = {
        "results": {
            10: {
                "status": "OK",
                "vz_final_mean": 1.0e-9,
                "vz_com_avg": 1.1e-9,
                "sim_result": {
                    "analytical": {
                        "V_sim": 1.1e-9,
                        "V_theory": 2.0e-9,
                        "pct_error_vs_theory": 45.0,
                        "pct_error_vs_sim": 81.8,
                        "error_status": "OK",
                        "steady_state_status": "TRANSIENT_LIKELY",
                    },
                    "stiffness": {
                        "status": "OK",
                        "deformation_exceeded": False,
                        "worst_metric_pct": 0.1,
                    },
                },
                "failure_reason": "NONE",
                "invalid_result": False,
            }
        },
        "convergence_achieved": False,
        "convergence_error_pct": 10.0,
        "recommended_n": 10,
    }

    module.print_result_summary(result)
    output = capsys.readouterr().out

    assert "tested_n_values: [10]" in output
    assert "recommended_n_elem: not determined" in output
    assert "candidate_max_n_elem: 10" in output
    assert "n_elem=10, status=OK" in output
    assert "V_sim=1.1e-09" in output
    assert "pct_error_vs_theory=45.0" in output
    assert "steady_state_status=TRANSIENT_LIKELY" in output
    assert "stiffness_status=OK" in output


def test_n_convergence_summary_prints_recommended_only_when_converged(capsys):
    module = _load_runner()
    result = {
        "results": {20: {"status": "OK", "vz_final_mean": 1.0e-9, "vz_com_avg": 1.0e-9}},
        "convergence_achieved": True,
        "convergence_error_pct": 0.5,
        "recommended_n": 20,
    }

    module.print_result_summary(result)
    output = capsys.readouterr().out

    assert "recommended_n_elem: 20" in output
    assert "candidate_max_n_elem" not in output


def test_n_convergence_config_summary_warns_for_low_n(capsys):
    module = _load_runner()
    config = module.normalize_config({
        "pitch": 0.02,
        "radius": 0.01,
        "total_length": 0.1,
        "body_length_ratio": 0.5,
        "n_values": [10, 20],
        "torque_magnitude": 1.0e-8,
        "dt": 1.0e-5,
        "total_steps": 100,
        "step_skip": 10,
        "fluid_viscosity": 0.1,
        "density": 1000.0,
        "E": 1.0e7,
        "nu": 0.5,
    })

    module.print_config_summary(module.DEFAULT_CONFIG, config, explicit_config=True)
    output = capsys.readouterr().out

    assert "warning: n_elem values below 20" in output


def test_n_convergence_test_preserves_analysis_efficiency_and_stiffness(monkeypatch):
    import sys

    import numpy as np

    PROJECT_SRC = PROJECT_ROOT / "src"
    if str(PROJECT_SRC) not in sys.path:
        sys.path.insert(0, str(PROJECT_SRC))

    from helical_propeller import sweeps

    def fake_run_simulation(**kwargs):
        n_elem = kwargs["n_elem"]
        velocity = np.array([
            np.zeros(n_elem + 1),
            np.zeros(n_elem + 1),
            np.full(n_elem + 1, n_elem * 1.0e-10),
        ])
        return {
            "final_velocity": velocity,
            "velocity": [velocity] * 5,
            "time": [0.0, 1.0],
            "final_time": 1.0,
            "parameters": kwargs,
            "analytical": {
                "V_sim": n_elem * 1.0e-10,
                "V_theory": n_elem * 2.0e-10,
                "pct_error": 100.0,
                "pct_error_vs_theory": 50.0,
                "pct_error_vs_sim": 100.0,
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

    result = sweeps.n_convergence_test(
        n_values=[10],
        total_steps=1,
        step_skip=1,
    )
    row = result["results"][10]

    assert row["n_elem"] == 10
    assert row["final_time"] == 1.0
    assert row["V_sim"] == 1.0e-9
    assert row["V_theory"] == 2.0e-9
    assert row["pct_error"] == 100.0
    assert row["pct_error_vs_theory"] == 50.0
    assert row["pct_error_vs_sim"] == 100.0
    assert row["error_status"] == "OK"
    assert row["failure_reason"] == "NONE"
    assert row["invalid_result"] is False
    assert row["Eta_slip"] == row["efficiency"]["eta_slip"]
    assert row["Eta_power"] == row["efficiency"]["eta_power"]
    assert row["stiffness_status"] == "OK"
    assert row["deformation_exceeded"] is False
    assert row["worst_metric_pct"] == 0.1
    assert row["analytical"]["V_sim"] == 1.0e-9
    assert row["stiffness"]["status"] == "OK"
