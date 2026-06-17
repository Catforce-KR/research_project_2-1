import importlib.util
from pathlib import Path

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name):
    path = PROJECT_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyze_damping_results_ranks_dummy_csv(tmp_path):
    module = _load_script("analyze_damping_results")
    csv_path = tmp_path / "damping.csv"
    pd.DataFrame([
        {
            "damping_constant": 1.0e-4,
            "V_sim": 1.0,
            "omega_sim": 1.0,
            "V_theory_over_V_sim": 2.0,
            "omega_theory_over_omega_sim": 1.5,
            "damping_torque_to_applied_ratio": 0.2,
            "torque_balance_with_damping_residual_ratio": 0.1,
            "steady_state_status": "TRANSIENT_LIKELY",
            "omega_steady_state_status": "OK",
            "invalid_result": False,
            "failure_reason": "NONE",
            "stiffness_status": "OK",
            "deformation_exceeded": False,
        },
        {
            "damping_constant": 1.0e-5,
            "V_sim": 1.1,
            "omega_sim": 1.1,
            "V_theory_over_V_sim": 1.4,
            "omega_theory_over_omega_sim": 1.1,
            "damping_torque_to_applied_ratio": 0.02,
            "torque_balance_with_damping_residual_ratio": 0.2,
            "steady_state_status": "OK",
            "omega_steady_state_status": "OK",
            "invalid_result": False,
            "failure_reason": "NONE",
            "stiffness_status": "OK",
            "deformation_exceeded": False,
        },
    ]).to_csv(csv_path, index=False)

    decision, warnings = module.analyze(csv_path)

    assert decision.iloc[0]["recommendation"] == "PRIMARY"
    assert decision.iloc[0]["damping_constant"] == 1.0e-5
    assert isinstance(warnings, list)


def test_check_sweep_config_reads_yaml_and_warns(tmp_path):
    module = _load_script("check_sweep_config")
    config_path = tmp_path / "sweep_h1.yaml"
    config = {
        "pr_values": [0.5, 1.0],
        "n_elem": 80,
        "radius": 0.01,
        "total_length": 0.1,
        "body_length_ratio": 0.5,
        "torque_magnitude": 1.0e-8,
        "dt": 1.0e-5,
        "total_steps": 30000,
        "step_skip": 300,
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    loaded = module.load_config(config_path)
    kind = module.infer_kind(loaded)
    summary, warnings = module.inspect_config(loaded, kind)

    assert kind == "h1"
    assert any("damping_constant" in warning for warning in warnings)
    assert any("previous NaN/INF" in warning for warning in warnings)
    assert any("0.5" in warning for warning in warnings)
    assert any("n_elem: 80" in line for line in summary)


def test_analyze_sweep_results_ranks_h1_dummy_csv(tmp_path):
    module = _load_script("analyze_sweep_results")
    csv_path = tmp_path / "h1.csv"
    pd.DataFrame([
        {
            "Status": "OK",
            "P/R": 2.0,
            "V_sim": 1.0,
            "Eta_power": 0.1,
            "Eta_slip": 0.2,
            "omega_sim": 1.0,
            "steady_state_status": "OK",
            "omega_steady_state_status": "OK",
            "invalid_result": False,
            "stiffness_status": "OK",
            "deformation_exceeded": False,
        },
        {
            "Status": "NAN/INF",
            "P/R": 0.5,
            "V_sim": None,
            "Eta_power": 0.0,
            "Eta_slip": 0.0,
            "omega_sim": None,
            "steady_state_status": "NONFINITE_VALUE",
            "omega_steady_state_status": "NONFINITE_VALUE",
            "invalid_result": True,
            "stiffness_status": "OK",
            "deformation_exceeded": False,
        },
    ]).to_csv(csv_path, index=False)

    kind, ranked = module.analyze(csv_path, "h1")

    assert kind == "h1"
    assert ranked.iloc[0]["_x"] == 2.0
    assert ranked.iloc[0]["_eligible"]
    assert ranked.iloc[-1]["_invalid"]
