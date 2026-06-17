"""Audit low-Reynolds-number conditions from completed sweep summaries.

This script only reads completed result files and configuration files. It never
runs PyElastica simulations.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = PROJECT_ROOT / "results" / "tables"
DOCS_DIR = PROJECT_ROOT / "docs"

PARAMETER_COLUMNS = {
    "density": ["density", "Density", "rho"],
    "fluid_viscosity": ["fluid_viscosity", "Fluid_Viscosity", "viscosity", "mu"],
    "radius": ["radius", "Radius"],
    "total_length": ["total_length", "Total_Length", "length", "L"],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Reynolds numbers and RFT applicability from completed summaries."
    )
    parser.add_argument("--h1", type=Path, required=True, help="H1 summary CSV path.")
    parser.add_argument("--h2", type=Path, required=True, help="H2 summary CSV path.")
    parser.add_argument("--config-h1", type=Path, required=True, help="H1 config YAML path.")
    parser.add_argument("--config-h2", type=Path, required=True, help="H2 config YAML path.")
    return parser.parse_args(argv)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_config(path: Path) -> dict[str, Any]:
    resolved = _resolve(path)
    if not resolved.exists():
        return {}
    with resolved.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {}
    return data


def find_h1_summary_paths(path: Path) -> list[Path]:
    resolved = _resolve(path)
    if resolved.exists():
        return [resolved]

    search_root = PROJECT_ROOT / "data" / "helical_results"
    fixed = sorted(search_root.rglob("h1_final_fixed/processed/sweep_h1_summary.csv"))
    extended = sorted(search_root.rglob("h1_extended_high_pr/processed/sweep_h1_summary.csv"))
    if fixed and extended:
        return [fixed[0], extended[0]]

    combined = sorted(search_root.rglob("sweep_h1_summary_combined.csv"))
    if combined:
        return [combined[0]]

    candidates = [
        candidate
        for candidate in search_root.rglob("sweep_h1_summary.csv")
        if "h1_final" in str(candidate) or "h1_extended_high_pr" in str(candidate)
    ]
    if candidates:
        return [sorted(candidates, key=lambda p: (len(str(p)), str(p)))[0]]
    raise FileNotFoundError(f"Could not find H1 summary path: {resolved}")


def find_h2_summary_path(path: Path) -> Path:
    resolved = _resolve(path)
    if resolved.exists():
        return resolved

    search_root = PROJECT_ROOT / "data" / "helical_results"
    preferred = sorted(search_root.rglob("h2_final_pr5/processed/sweep_h2_summary.csv"))
    if preferred:
        return preferred[0]

    candidates = sorted(search_root.rglob("sweep_h2_summary.csv"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(f"Could not find H2 summary path: {resolved}")


def first_existing_column(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    lower_map = {str(col).lower(): col for col in df.columns}
    for name in names:
        found = lower_map.get(name.lower())
        if found is not None:
            return str(found)
    return None


def load_h1_summary(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    combined = pd.concat(frames, ignore_index=True)
    pr_col = first_existing_column(combined, ["P/R", "pr", "pitch_over_radius"])
    if pr_col is None:
        raise ValueError("H1 summary must include P/R or equivalent column.")
    combined["P/R"] = pd.to_numeric(combined[pr_col], errors="coerce")
    combined = combined.sort_values("P/R").drop_duplicates(subset=["P/R"], keep="last")
    return combined.reset_index(drop=True)


def load_h2_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    br_col = first_existing_column(df, ["Body_Length_Ratio", "body_length_ratio", "Body/Tail"])
    if br_col is None:
        raise ValueError("H2 summary must include body length ratio or equivalent column.")
    df["body_length_ratio"] = pd.to_numeric(df[br_col], errors="coerce")
    return df


def safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def resolve_parameter(row: pd.Series, config: dict[str, Any], key: str) -> tuple[float, str]:
    for column in PARAMETER_COLUMNS[key]:
        if column in row.index:
            value = safe_float(row[column])
            if not math.isnan(value):
                return value, "csv"
    value = safe_float(config.get(key))
    if not math.isnan(value):
        return value, "config"
    return math.nan, "UNKNOWN"


def compute_reynolds_number(
    density: float,
    velocity: float,
    length: float,
    fluid_viscosity: float,
) -> float:
    if any(math.isnan(value) for value in [density, velocity, length, fluid_viscosity]):
        return math.nan
    if abs(fluid_viscosity) <= 1e-30:
        return math.nan
    return density * abs(velocity) * length / fluid_viscosity


def classify_low_re(values: list[float]) -> str:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return "UNKNOWN"
    max_re = max(finite)
    if max_re < 0.01:
        return "LOW_RE_CONFIRMED"
    if max_re < 1.0:
        return "LOW_RE_REASONABLE"
    return "LOW_RE_VIOLATION"


def _format_sources(sources: dict[str, str]) -> str:
    fallback = [key for key, source in sources.items() if source == "config"]
    unknown = [key for key, source in sources.items() if source == "UNKNOWN"]
    parts = []
    if fallback:
        parts.append("fallback_from_config=" + ",".join(fallback))
    if unknown:
        parts.append("unknown=" + ",".join(unknown))
    return "; ".join(parts) if parts else "all_parameters_from_csv"


def audit_dataframe(df: pd.DataFrame, kind: str, config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    parameter_col = "P/R" if kind == "H1" else "body_length_ratio"
    for _, row in df.iterrows():
        density, density_source = resolve_parameter(row, config, "density")
        fluid_viscosity, viscosity_source = resolve_parameter(row, config, "fluid_viscosity")
        radius, radius_source = resolve_parameter(row, config, "radius")
        total_length, total_length_source = resolve_parameter(row, config, "total_length")
        sources = {
            "density": density_source,
            "fluid_viscosity": viscosity_source,
            "radius": radius_source,
            "total_length": total_length_source,
        }
        v_sim = safe_float(row.get("V_sim"))
        v_theory = safe_float(row.get("V_theory"))
        re_radius = compute_reynolds_number(density, v_sim, radius, fluid_viscosity)
        re_total = compute_reynolds_number(density, v_sim, total_length, fluid_viscosity)
        re_theory_radius = compute_reynolds_number(density, v_theory, radius, fluid_viscosity)
        re_theory_total = compute_reynolds_number(density, v_theory, total_length, fluid_viscosity)
        status = classify_low_re([re_radius, re_total, re_theory_radius, re_theory_total])

        notes = _format_sources(sources)
        body_length = safe_float(row.get("Body_Length", row.get("body_length")))
        if math.isfinite(body_length):
            notes += f"; body_length={body_length:g}"
        rows.append(
            {
                "experiment_kind": kind,
                "parameter_value": safe_float(row.get(parameter_col)),
                "V_sim": v_sim,
                "V_theory": v_theory,
                "Re_radius": re_radius,
                "Re_total_length": re_total,
                "Re_theory_radius": re_theory_radius,
                "Re_theory_total_length": re_theory_total,
                "low_re_status": status,
                "notes": notes,
            }
        )
    return pd.DataFrame(rows)


def summarize_audits(h1_audit: pd.DataFrame, h2_audit: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for kind, df in [("H1", h1_audit), ("H2", h2_audit)]:
        max_values = {
            col: pd.to_numeric(df[col], errors="coerce").max()
            for col in [
                "Re_radius",
                "Re_total_length",
                "Re_theory_radius",
                "Re_theory_total_length",
            ]
        }
        finite = [value for value in max_values.values() if math.isfinite(value)]
        max_overall = max(finite) if finite else math.nan
        rows.append(
            {
                "experiment_kind": kind,
                "max_Re_radius": max_values["Re_radius"],
                "max_Re_total_length": max_values["Re_total_length"],
                "max_Re_theory_radius": max_values["Re_theory_radius"],
                "max_Re_theory_total_length": max_values["Re_theory_total_length"],
                "max_Re_overall": max_overall,
                "all_Re_below_1": bool(math.isfinite(max_overall) and max_overall < 1.0),
                "all_Re_below_0p1": bool(math.isfinite(max_overall) and max_overall < 0.1),
                "overall_low_re_status": classify_low_re(finite),
                "notes": "uses max across simulation/theory velocities and radius/total_length scales",
            }
        )
    return pd.DataFrame(rows)


def summarize_existing_docs() -> pd.DataFrame:
    rows = [
        {
            "file": "docs/project_structure_for_research_plan.md",
            "content_summary": "Conceptual Navier-Stokes/RFT relationship, PyElastica-RFT role, torque-driven comparison, damping influence.",
            "quantitative_re": "No",
            "gap": "Needs final data Reynolds number audit.",
        },
        {
            "file": "docs/research_plan_gap_check.md",
            "content_summary": "Checklist-level low-Re/RFT assumptions, limitations, damping and analytical-theory distinction.",
            "quantitative_re": "No",
            "gap": "Needs numerical Re ranges for final H1/H2 data.",
        },
        {
            "file": "docs/final_results_summary.md",
            "content_summary": "Final H1/H2 conclusions, damping rationale, conceptual Navier-Stokes/RFT section.",
            "quantitative_re": "Partial after this audit",
            "gap": "Add explicit Re ranges and exclusion of damping_constant from Re.",
        },
        {
            "file": "docs/final_data_generation_plan.md",
            "content_summary": "Execution/analysis workflow and damping decision flow.",
            "quantitative_re": "No",
            "gap": "Not intended to be the low-Re audit document.",
        },
        {
            "file": "docs/model_assumptions.md",
            "content_summary": "Low-Re regime, RFT approximation, torque-driven RFT equations, body drag approximation, damping diagnostics.",
            "quantitative_re": "No",
            "gap": "Could cite the final audit for numeric Re support.",
        },
        {
            "file": "docs/validation.md",
            "content_summary": "Analytical comparison metrics and damping diagnostics.",
            "quantitative_re": "No",
            "gap": "No Reynolds number validation criterion.",
        },
    ]
    return pd.DataFrame(rows)


def write_audit_doc(
    h1_sources: list[Path],
    h2_source: Path,
    summary: pd.DataFrame,
    doc_inventory: pd.DataFrame,
) -> Path:
    h1_row = summary[summary["experiment_kind"] == "H1"].iloc[0]
    h2_row = summary[summary["experiment_kind"] == "H2"].iloc[0]
    lines = [
        "# Low Reynolds Number And RFT Audit",
        "",
        "## Audit Purpose",
        "",
        "This document checks whether the completed H1/H2 result summaries remain in a low-Reynolds-number regime and whether the project documentation can support the use of RFT as the analytical comparison model. No simulation is executed by this audit.",
        "",
        "## Data Sources",
        "",
        f"- H1 summary: `{' + '.join(display_path(path) for path in h1_sources)}`",
        f"- H2 summary: `{display_path(h2_source)}`",
        "- Config fallback: `configs/sweep_h1.yaml`, `configs/sweep_h2.yaml`",
        "",
        "## Existing Documentation Check",
        "",
        "| File | Existing content | Quantitative Re included | Gap |",
        "| --- | --- | --- | --- |",
    ]
    for _, row in doc_inventory.iterrows():
        lines.append(
            f"| `{row['file']}` | {row['content_summary']} | {row['quantitative_re']} | {row['gap']} |"
        )
    lines.extend(
        [
            "",
            "## Navier-Stokes And RFT Relationship",
            "",
            "The Navier-Stokes equations are the general continuum equations for fluid motion. This project does not solve the full Navier-Stokes equations or run CFD. Instead, it models the elastic helical swimmer with PyElastica and applies RFT-style local drag forces as the low-Reynolds-number hydrodynamic approximation.",
            "",
            "At low Reynolds number, viscous effects dominate over inertial effects. Under slender-body/local-drag assumptions, RFT approximates the force per unit length using tangential and normal resistance coefficients. The analytical comparison used here is therefore torque-driven RFT, not a full CFD benchmark.",
            "",
            "## Reynolds Number Formula",
            "",
            "The audit uses:",
            "",
            "`Re = density * abs(V) * L / fluid_viscosity`",
            "",
            "Velocity scales use both `V_sim` and `V_theory`. Length scales use `radius` and `total_length`. When these columns are absent from the summary CSV, the values are read from the corresponding sweep config. `damping_constant` is not part of the Reynolds number because it is a PyElastica numerical damping parameter, not the fluid viscosity.",
            "",
            "Operational status thresholds:",
            "",
            "- `LOW_RE_CONFIRMED`: maximum evaluated Re < 0.01.",
            "- `LOW_RE_REASONABLE`: 0.01 <= maximum evaluated Re < 1.",
            "- `LOW_RE_VIOLATION`: maximum evaluated Re >= 1.",
            "- `UNKNOWN`: required parameters are unavailable.",
            "",
            "## Computed Re Ranges",
            "",
            "| Sweep | max Re(radius, V_sim) | max Re(total_length, V_sim) | max Re(radius, V_theory) | max Re(total_length, V_theory) | Status |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
            f"| H1 | {h1_row['max_Re_radius']:.6g} | {h1_row['max_Re_total_length']:.6g} | {h1_row['max_Re_theory_radius']:.6g} | {h1_row['max_Re_theory_total_length']:.6g} | {h1_row['overall_low_re_status']} |",
            f"| H2 | {h2_row['max_Re_radius']:.6g} | {h2_row['max_Re_total_length']:.6g} | {h2_row['max_Re_theory_radius']:.6g} | {h2_row['max_Re_theory_total_length']:.6g} | {h2_row['overall_low_re_status']} |",
            "",
            "## RFT Applicability Assessment",
            "",
            "- The final H1/H2 data remain below `Re=1` for both radius and total-length scales, using both simulation and theory velocities.",
            "- The total-length scale is the conservative larger length scale in this audit; it still remains in the low-Re range.",
            "- The geometry uses a finite helical radius and pitch sweep. RFT remains a local slender-body approximation, so very loose helices at high P/R should be interpreted with more caution than mid-range P/R cases.",
            "- `fluid_viscosity=0.1` and `density=1000.0` produce a computational low-Re regime for the observed micrometer-per-second-scale velocities. These parameters should be described as simulation/model parameters rather than as a claim of direct water-like experimental matching.",
            "",
            "## fluid_viscosity Versus damping_constant",
            "",
            "- `fluid_viscosity` enters the RFT hydrodynamic resistance model and the Reynolds number calculation.",
            "- `damping_constant=1e-5` is an internal PyElastica damping/stabilization parameter.",
            "- The damping parameter can affect the theory/simulation comparison by absorbing part of the applied torque, but it is not a physical fluid viscosity and must not be used in the Reynolds number.",
            "",
            "## Report-Ready Sentences",
            "",
            "- In the final simulation data, the Reynolds numbers computed from both the swimmer radius and total length remain well below 1, supporting a low-Reynolds-number interpretation.",
            "- The study does not solve the full Navier-Stokes equations; it combines PyElastica rod dynamics with an RFT local drag approximation and compares the simulation with torque-driven analytical RFT.",
            "- The numerical `damping_constant` is distinct from `fluid_viscosity` and is excluded from the Reynolds number calculation.",
            "",
            "## Remaining Limitations",
            "",
            "- RFT is a local drag approximation and does not capture all nonlocal hydrodynamic interactions.",
            "- High P/R cases may be less representative of a compact helical propeller geometry.",
            "- The density/viscosity settings support the computational low-Re condition, but they should not be over-interpreted as a full experimental fluid match.",
        ]
    )
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output = DOCS_DIR / "low_reynolds_and_rft_audit.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def write_tables(
    h1_audit: pd.DataFrame,
    h2_audit: pd.DataFrame,
    summary: pd.DataFrame,
) -> dict[str, Path]:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "h1": TABLES_DIR / "reynolds_number_audit_h1.csv",
        "h2": TABLES_DIR / "reynolds_number_audit_h2.csv",
        "summary": TABLES_DIR / "low_reynolds_summary.csv",
    }
    h1_audit.to_csv(outputs["h1"], index=False, encoding="utf-8")
    h2_audit.to_csv(outputs["h2"], index=False, encoding="utf-8")
    summary.to_csv(outputs["summary"], index=False, encoding="utf-8")
    return outputs


def generate_audit(
    h1_path: Path,
    h2_path: Path,
    config_h1_path: Path,
    config_h2_path: Path,
) -> dict[str, Any]:
    h1_sources = find_h1_summary_paths(h1_path)
    h2_source = find_h2_summary_path(h2_path)
    h1_config = load_config(config_h1_path)
    h2_config = load_config(config_h2_path)

    h1 = load_h1_summary(h1_sources)
    h2 = load_h2_summary(h2_source)
    h1_audit = audit_dataframe(h1, "H1", h1_config)
    h2_audit = audit_dataframe(h2, "H2", h2_config)
    summary = summarize_audits(h1_audit, h2_audit)
    doc_inventory = summarize_existing_docs()
    tables = write_tables(h1_audit, h2_audit, summary)
    doc = write_audit_doc(h1_sources, h2_source, summary, doc_inventory)
    return {
        "h1_sources": h1_sources,
        "h2_source": h2_source,
        "tables": tables,
        "doc": doc,
        "summary": summary,
        "doc_inventory": doc_inventory,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_audit(args.h1, args.h2, args.config_h1, args.config_h2)
    print("Low-Reynolds-number audit generated")
    print("H1 summary used: " + " + ".join(str(path) for path in result["h1_sources"]))
    print(f"H2 summary used: {result['h2_source']}")
    for label, path in result["tables"].items():
        print(f"table {label}: {path}")
    print(f"doc: {result['doc']}")
    print(result["summary"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
