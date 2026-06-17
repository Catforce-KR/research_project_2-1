"""Analyze H1/H2 sweep summary CSVs without running simulations."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze H1 or H2 sweep summary CSV output.")
    parser.add_argument("summary_csv", type=Path, help="Path to H1/H2 summary CSV.")
    parser.add_argument(
        "--kind",
        choices=["auto", "h1", "h2"],
        default="auto",
        help="Sweep type. Auto-detected from columns by default.",
    )
    return parser.parse_args(argv)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _first_existing(df: pd.DataFrame, names: list[str]):
    for name in names:
        if name in df.columns:
            return name
    return None


def _bool_series(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    valid = denominator.abs() > 1e-30
    result = pd.Series([math.nan] * len(numerator), index=numerator.index, dtype=float)
    result.loc[valid] = numerator.loc[valid] / denominator.loc[valid]
    return result


def infer_kind(df: pd.DataFrame, requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    if _first_existing(df, ["P/R", "pr", "pitch_over_radius"]) is not None:
        return "h1"
    if _first_existing(df, ["Body_Length_Ratio", "body_length_ratio", "Body/Tail"]) is not None:
        return "h2"
    return "unknown"


def prepare_dataframe(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    out = df.copy()
    status_col = _first_existing(out, ["status", "Status"])
    invalid_col = _first_existing(out, ["invalid_result"])
    stiffness_col = _first_existing(out, ["stiffness_status"])
    deformation_col = _first_existing(out, ["deformation_exceeded"])

    out["_status"] = out[status_col] if status_col else "UNKNOWN"
    out["_invalid"] = _bool_series(out[invalid_col]) if invalid_col else out["_status"].astype(str).str.upper().ne("OK")
    out["_stiffness_ok"] = (
        out[stiffness_col].fillna("UNKNOWN").astype(str).str.upper().eq("OK")
        if stiffness_col else False
    )
    out["_deformation"] = _bool_series(out[deformation_col]) if deformation_col else False
    out["_eligible"] = (~out["_invalid"]) & out["_stiffness_ok"] & (~out["_deformation"])

    if kind == "h1":
        pr_col = _first_existing(out, ["P/R", "pr", "pitch_over_radius"])
        if pr_col:
            out["_x"] = pd.to_numeric(out[pr_col], errors="coerce")
        else:
            pitch_col = _first_existing(out, ["Pitch", "pitch"])
            radius_col = _first_existing(out, ["radius"])
            out["_x"] = pd.to_numeric(out[pitch_col], errors="coerce") / pd.to_numeric(out[radius_col], errors="coerce")
    else:
        br_col = _first_existing(out, ["Body_Length_Ratio", "body_length_ratio", "Body/Tail"])
        out["_x"] = pd.to_numeric(out[br_col], errors="coerce") if br_col else math.nan

    numeric_defaults = {
        "V_sim": ["V_sim", "Vz_com_avg", "Vz_final_mean"],
        "Eta_power": ["Eta_power", "eta_power"],
        "Eta_slip": ["Eta_slip", "eta_slip"],
        "omega_sim": ["omega_sim", "omega_z", "omega_used"],
        "V_theory_over_V_sim": ["V_theory_over_V_sim"],
        "omega_theory_over_omega_sim": ["omega_theory_over_omega_sim"],
    }
    for target, names in numeric_defaults.items():
        source = _first_existing(out, names)
        out[f"_{target}"] = pd.to_numeric(out[source], errors="coerce") if source else math.nan
    if "_V_theory_over_V_sim" in out and out["_V_theory_over_V_sim"].isna().all():
        v_theory = _first_existing(out, ["V_theory"])
        v_sim = _first_existing(out, ["V_sim", "Vz_com_avg", "Vz_final_mean"])
        if v_theory and v_sim:
            out["_V_theory_over_V_sim"] = _safe_ratio(out[v_theory], out[v_sim])
    if "_omega_theory_over_omega_sim" in out and out["_omega_theory_over_omega_sim"].isna().all():
        omega_theory = _first_existing(out, ["omega_theory"])
        omega_sim = _first_existing(out, ["omega_sim", "omega_z", "omega_used"])
        if omega_theory and omega_sim:
            out["_omega_theory_over_omega_sim"] = _safe_ratio(out[omega_theory], out[omega_sim])
    for text_col in ["steady_state_status", "omega_steady_state_status", "failure_reason"]:
        source = _first_existing(out, [text_col])
        out[f"_{text_col}"] = out[source] if source else ""
    return out


def _normalized(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    min_value = numeric.min(skipna=True)
    max_value = numeric.max(skipna=True)
    if not math.isfinite(float(min_value)) or not math.isfinite(float(max_value)):
        return pd.Series([0.0] * len(series), index=series.index)
    if abs(max_value - min_value) <= 1e-30:
        return pd.Series([0.0] * len(series), index=series.index)
    return (numeric - min_value) / (max_value - min_value)


def rank_candidates(df: pd.DataFrame) -> pd.DataFrame:
    ranked = df.copy()
    velocity_score = _normalized(ranked["_V_sim"].abs())
    power_score = _normalized(ranked["_Eta_power"])
    slip_score = _normalized(ranked["_Eta_slip"])
    steady_bonus = ranked["_steady_state_status"].astype(str).str.upper().eq("OK").astype(float) * 0.2
    omega_bonus = ranked["_omega_steady_state_status"].astype(str).str.upper().eq("OK").astype(float) * 0.2
    ranked["_candidate_score"] = (
        1.0 * velocity_score.fillna(0.0)
        + 0.8 * power_score.fillna(0.0)
        + 0.3 * slip_score.fillna(0.0)
        + steady_bonus
        + omega_bonus
    )
    ranked.loc[~ranked["_eligible"], "_candidate_score"] = -math.inf
    return ranked.sort_values(["_candidate_score", "_x"], ascending=[False, True], kind="stable")


def display_columns(kind: str) -> list[str]:
    x_name = "P/R" if kind == "h1" else "body_length_ratio"
    return [
        x_name,
        "V_sim",
        "Eta_power",
        "Eta_slip",
        "omega_sim",
        "V_theory_over_V_sim",
        "omega_theory_over_omega_sim",
        "steady_state_status",
        "omega_steady_state_status",
        "status",
        "stiffness_status",
        "deformation_exceeded",
    ]


def build_display(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    label = "P/R" if kind == "h1" else "body_length_ratio"
    display = pd.DataFrame({
        label: df["_x"],
        "V_sim": df["_V_sim"],
        "Eta_power": df["_Eta_power"],
        "Eta_slip": df["_Eta_slip"],
        "omega_sim": df["_omega_sim"],
        "V_theory_over_V_sim": df["_V_theory_over_V_sim"],
        "omega_theory_over_omega_sim": df["_omega_theory_over_omega_sim"],
        "steady_state_status": df["_steady_state_status"],
        "omega_steady_state_status": df["_omega_steady_state_status"],
        "status": df["_status"],
        "stiffness_status": df.get("stiffness_status", ""),
        "deformation_exceeded": df.get("deformation_exceeded", ""),
        "candidate_score": df["_candidate_score"],
    })
    return display


def analyze(summary_csv: Path, requested_kind: str = "auto") -> tuple[str, pd.DataFrame]:
    path = _resolve(summary_csv)
    if not path.is_file():
        raise FileNotFoundError(f"Sweep summary CSV not found: {path}")
    df = pd.read_csv(path)
    kind = infer_kind(df, requested_kind)
    prepared = prepare_dataframe(df, kind)
    ranked = rank_candidates(prepared)
    return kind, ranked


def print_report(kind: str, ranked: pd.DataFrame) -> None:
    title = "H1 P/R sweep" if kind == "h1" else "H2 body-ratio sweep"
    print(f"{title} analysis")
    print("ranked summary:")
    print(build_display(ranked, kind).to_string(index=False))

    invalid = ranked[ranked["_invalid"]]
    if not invalid.empty:
        print("invalid/failure cases:")
        print(build_display(invalid, kind).to_string(index=False))

    stiffness_problem = ranked[(~ranked["_stiffness_ok"]) | ranked["_deformation"]]
    if not stiffness_problem.empty:
        print("stiffness/deformation problem cases:")
        print(build_display(stiffness_problem, kind).to_string(index=False))

    eligible = ranked[ranked["_eligible"]]
    if eligible.empty:
        print("optimal candidates: none")
        return
    label = "P/R" if kind == "h1" else "body_length_ratio"
    print("optimal candidates:")
    for _, row in eligible.head(2).iterrows():
        print(
            f"  - {label}={row['_x']}: "
            f"V_sim={row['_V_sim']}, Eta_power={row['_Eta_power']}, "
            f"Eta_slip={row['_Eta_slip']}, score={row['_candidate_score']}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        kind, ranked = analyze(args.summary_csv, args.kind)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    print_report(kind, ranked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
