import importlib.util
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "generate_final_analysis_outputs.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_final_analysis_outputs", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_summary_computes_missing_ratios(tmp_path):
    module = _load_module()
    csv_path = tmp_path / "h1.csv"
    pd.DataFrame([
        {
            "P/R": 5.0,
            "Pitch": 0.05,
            "V_sim": 2.0,
            "V_theory": 6.0,
            "omega_sim": 4.0,
            "omega_theory": 8.0,
            "stiffness_status": "OK",
            "deformation_exceeded": False,
            "invalid_result": False,
            "failure_reason": "NONE",
        }
    ]).to_csv(csv_path, index=False)

    df = module.load_summary(csv_path, "h1")

    assert df.loc[0, "V_theory_over_V_sim"] == 3.0
    assert df.loc[0, "omega_theory_over_omega_sim"] == 2.0


def test_find_raw_file_matches_pr_and_body_ratio(tmp_path):
    module = _load_module()
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "sim_N80_pr6.00_T1e-08.csv").write_text("Time,Vz_mean,Omega_z\n", encoding="utf-8")
    (raw_dir / "sweep_h2_br0.50_timeseries.csv").write_text("Time,Vz_mean,Omega_z\n", encoding="utf-8")

    assert module.find_raw_file(raw_dir, "pr", 6.0).name == "sim_N80_pr6.00_T1e-08.csv"
    assert module.find_raw_file(raw_dir, "body", 0.5).name == "sweep_h2_br0.50_timeseries.csv"


def test_timeseries_plot_saves_file(tmp_path):
    module = _load_module()
    csv_path = tmp_path / "series.csv"
    output = tmp_path / "plot.png"
    pd.DataFrame({
        "Time": [0.0, 1.0],
        "Vz_mean": [0.0, 1.0],
        "Omega_z": [0.0, 2.0],
    }).to_csv(csv_path, index=False)

    ok, column = module.save_timeseries_plot(
        csv_path,
        module.VELOCITY_COLUMNS,
        output,
        "dummy",
        "Vz_mean",
    )

    assert ok
    assert column == "Vz_mean"
    assert output.is_file()
