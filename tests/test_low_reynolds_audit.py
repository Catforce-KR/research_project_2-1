import importlib.util
import math
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "audit_low_reynolds_params.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_low_reynolds_params", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compute_reynolds_number():
    module = _load_module()

    value = module.compute_reynolds_number(
        density=1000.0,
        velocity=2.0e-6,
        length=0.1,
        fluid_viscosity=0.1,
    )

    assert math.isclose(value, 2.0e-3)


def test_classify_low_re_statuses():
    module = _load_module()

    assert module.classify_low_re([0.001]) == "LOW_RE_CONFIRMED"
    assert module.classify_low_re([0.05]) == "LOW_RE_REASONABLE"
    assert module.classify_low_re([1.0]) == "LOW_RE_VIOLATION"
    assert module.classify_low_re([math.nan]) == "UNKNOWN"


def test_config_fallback_for_missing_physical_columns():
    module = _load_module()
    df = pd.DataFrame(
        [
            {
                "P/R": 5.0,
                "V_sim": 2.0e-6,
                "V_theory": 3.0e-6,
            }
        ]
    )
    config = {
        "density": 1000.0,
        "fluid_viscosity": 0.1,
        "radius": 0.01,
        "total_length": 0.1,
    }

    audited = module.audit_dataframe(df, "H1", config)

    assert math.isclose(audited.loc[0, "Re_radius"], 2.0e-4)
    assert math.isclose(audited.loc[0, "Re_total_length"], 2.0e-3)
    assert "fallback_from_config" in audited.loc[0, "notes"]


def test_generate_audit_writes_tables_and_doc(tmp_path, monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "TABLES_DIR", tmp_path / "tables")
    monkeypatch.setattr(module, "DOCS_DIR", tmp_path / "docs")

    h1_csv = tmp_path / "h1.csv"
    h2_csv = tmp_path / "h2.csv"
    h1_config = tmp_path / "h1.yaml"
    h2_config = tmp_path / "h2.yaml"
    h1_csv.write_text("P/R,V_sim,V_theory\n5.0,2e-6,3e-6\n", encoding="utf-8")
    h2_csv.write_text("Body_Length_Ratio,V_sim,V_theory\n0.5,2.5e-6,3.5e-6\n", encoding="utf-8")
    config_text = "density: 1000.0\nfluid_viscosity: 0.1\nradius: 0.01\ntotal_length: 0.1\n"
    h1_config.write_text(config_text, encoding="utf-8")
    h2_config.write_text(config_text, encoding="utf-8")

    result = module.generate_audit(h1_csv, h2_csv, h1_config, h2_config)

    assert result["tables"]["h1"].is_file()
    assert result["tables"]["h2"].is_file()
    assert result["tables"]["summary"].is_file()
    assert result["doc"].is_file()
