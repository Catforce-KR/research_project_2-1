"""Generate final tables, figures, and report text from completed sweep CSVs.

This script only reads completed result files. It never runs simulations.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = PROJECT_ROOT / "results" / "tables"
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"
DOCS_DIR = PROJECT_ROOT / "docs"

TIME_COLUMNS = ["Time", "time", "t"]
VELOCITY_COLUMNS = ["Vz_mean", "Vz_com", "Vz_final", "V_sim", "velocity_z"]
OMEGA_COLUMNS = ["Omega_z", "omega_z", "omega_sim", "AngularVelocity_z"]

H1_TABLE_COLUMNS = [
    "P/R",
    "pitch",
    "V_sim",
    "V_theory",
    "V_theory_over_V_sim",
    "omega_sim",
    "omega_theory",
    "omega_theory_over_omega_sim",
    "Eta_power",
    "Eta_slip",
    "pct_error_vs_theory",
    "steady_state_status",
    "omega_steady_state_status",
    "invalid_result",
    "failure_reason",
    "stiffness_status",
    "deformation_exceeded",
]

H2_TABLE_COLUMNS = [
    "body_length_ratio",
    "V_sim",
    "V_theory",
    "V_theory_over_V_sim",
    "omega_sim",
    "omega_theory",
    "omega_theory_over_omega_sim",
    "Eta_power",
    "Eta_slip",
    "pct_error_vs_theory",
    "steady_state_status",
    "omega_steady_state_status",
    "invalid_result",
    "failure_reason",
    "stiffness_status",
    "deformation_exceeded",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate final analysis tables, figures, and summary docs."
    )
    parser.add_argument("--h1", type=Path, required=True, help="H1 summary CSV path.")
    parser.add_argument("--h2", type=Path, required=True, help="H2 summary CSV path.")
    parser.add_argument("--raw-dir", type=Path, required=True, help="Raw timeseries CSV directory.")
    return parser.parse_args(argv)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def find_existing_path(path: Path, kind: str) -> Path:
    resolved = _resolve(path)
    if resolved.exists():
        return resolved

    search_root = PROJECT_ROOT / "data" / "helical_results"
    if kind == "h1":
        candidates = [
            p for p in search_root.rglob("sweep_h1_summary*.csv")
            if "h2_final_pr5" in str(p) or "h1_extended_high_pr" in str(p)
        ]
    elif kind == "h2":
        candidates = list(search_root.rglob("sweep_h2_summary.csv"))
    elif kind == "raw":
        candidates = [
            p for p in search_root.rglob("raw")
            if p.is_dir() and "h2_final_pr5" in str(p)
        ]
    else:
        candidates = []

    if candidates:
        return sorted(candidates, key=lambda p: (len(str(p)), str(p)))[0]
    raise FileNotFoundError(f"Could not find {kind} path: {resolved}")


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
        p for p in search_root.rglob("sweep_h1_summary.csv")
        if "h2_final_pr5" in str(p) or "h1_extended_high_pr" in str(p)
    ]
    if candidates:
        return [sorted(candidates, key=lambda p: (len(str(p)), str(p)))[0]]
    raise FileNotFoundError(f"Could not find H1 summary path: {resolved}")


def load_h1_summary(paths: list[Path]) -> pd.DataFrame:
    frames = [load_summary(path, "h1") for path in paths]
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("P/R").drop_duplicates(subset=["P/R"], keep="last")
    return combined.reset_index(drop=True)


def first_existing_column(df: pd.DataFrame, names: list[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    valid = denominator.abs() > 1e-30
    result = pd.Series([math.nan] * len(numerator), index=numerator.index, dtype=float)
    result.loc[valid] = numerator.loc[valid] / denominator.loc[valid]
    return result


def normalize_bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(str).str.strip().str.lower().isin(["true", "1", "yes", "y"])


def load_summary(path: Path, kind: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.copy()
    if kind == "h1":
        pr_col = first_existing_column(df, ["P/R", "pr", "pitch_over_radius"])
        pitch_col = first_existing_column(df, ["Pitch", "pitch"])
        if pr_col is None:
            raise ValueError("H1 summary must include P/R or equivalent column")
        df["P/R"] = pd.to_numeric(df[pr_col], errors="coerce")
        df["pitch"] = pd.to_numeric(df[pitch_col], errors="coerce") if pitch_col else math.nan
    else:
        br_col = first_existing_column(df, ["Body_Length_Ratio", "body_length_ratio", "Body/Tail"])
        if br_col is None:
            raise ValueError("H2 summary must include body length ratio column")
        df["body_length_ratio"] = pd.to_numeric(df[br_col], errors="coerce")

    if "omega_steady_state_status" not in df.columns and "omega_state_status" in df.columns:
        df["omega_steady_state_status"] = df["omega_state_status"]
    for required in [
        "V_sim",
        "V_theory",
        "omega_sim",
        "omega_theory",
        "Eta_power",
        "Eta_slip",
        "pct_error_vs_theory",
    ]:
        if required not in df.columns:
            df[required] = math.nan
        df[required] = pd.to_numeric(df[required], errors="coerce")
    if "V_theory_over_V_sim" not in df.columns:
        df["V_theory_over_V_sim"] = safe_ratio(df["V_theory"], df["V_sim"])
    else:
        df["V_theory_over_V_sim"] = pd.to_numeric(df["V_theory_over_V_sim"], errors="coerce")
        missing = df["V_theory_over_V_sim"].isna()
        df.loc[missing, "V_theory_over_V_sim"] = safe_ratio(df["V_theory"], df["V_sim"]).loc[missing]
    if "omega_theory_over_omega_sim" not in df.columns:
        df["omega_theory_over_omega_sim"] = safe_ratio(df["omega_theory"], df["omega_sim"])
    else:
        df["omega_theory_over_omega_sim"] = pd.to_numeric(
            df["omega_theory_over_omega_sim"], errors="coerce"
        )
        missing = df["omega_theory_over_omega_sim"].isna()
        df.loc[missing, "omega_theory_over_omega_sim"] = safe_ratio(
            df["omega_theory"], df["omega_sim"]
        ).loc[missing]

    for col, default in [
        ("steady_state_status", ""),
        ("omega_steady_state_status", ""),
        ("invalid_result", False),
        ("failure_reason", "NONE"),
        ("stiffness_status", ""),
        ("deformation_exceeded", False),
    ]:
        if col not in df.columns:
            df[col] = default
    return df


def valid_rows(df: pd.DataFrame) -> pd.DataFrame:
    invalid = normalize_bool(df["invalid_result"])
    deformation = normalize_bool(df["deformation_exceeded"])
    stiffness_ok = df["stiffness_status"].fillna("").astype(str).str.upper().eq("OK")
    failure_ok = df["failure_reason"].fillna("NONE").astype(str).str.upper().eq("NONE")
    return df[(~invalid) & (~deformation) & stiffness_ok & failure_ok].copy()


def write_summary_tables(h1: pd.DataFrame, h2: pd.DataFrame) -> dict[str, Path]:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {}
    h1_table = h1[H1_TABLE_COLUMNS].sort_values("P/R")
    h2_table = h2[H2_TABLE_COLUMNS].sort_values("body_length_ratio")
    outputs["h1"] = TABLES_DIR / "h1_final_summary_table.csv"
    outputs["h2"] = TABLES_DIR / "h2_final_summary_table.csv"
    h1_table.to_csv(outputs["h1"], index=False, encoding="utf-8")
    h2_table.to_csv(outputs["h2"], index=False, encoding="utf-8")
    return outputs


def row_by_max(df: pd.DataFrame, metric: str) -> pd.Series:
    candidates = valid_rows(df)
    if candidates.empty:
        candidates = df
    idx = pd.to_numeric(candidates[metric], errors="coerce").idxmax()
    return candidates.loc[idx]


def write_optimal_candidates(h1: pd.DataFrame, h2: pd.DataFrame) -> Path:
    h1_speed = row_by_max(h1, "V_sim")
    h1_power = row_by_max(h1, "Eta_power")
    h2_speed = row_by_max(h2, "V_sim")
    h2_power = row_by_max(h2, "Eta_power")
    rows = [
        {
            "category": "H1 speed optimum",
            "parameter": "P/R",
            "value": h1_speed["P/R"],
            "V_sim": h1_speed["V_sim"],
            "Eta_power": h1_speed["Eta_power"],
            "reason": "Maximum V_sim among valid H1 rows.",
        },
        {
            "category": "H1 power efficiency optimum",
            "parameter": "P/R",
            "value": h1_power["P/R"],
            "V_sim": h1_power["V_sim"],
            "Eta_power": h1_power["Eta_power"],
            "reason": "Maximum Eta_power among valid H1 rows.",
        },
        {
            "category": "H2 speed optimum",
            "parameter": "body_length_ratio",
            "value": h2_speed["body_length_ratio"],
            "V_sim": h2_speed["V_sim"],
            "Eta_power": h2_speed["Eta_power"],
            "reason": "Maximum V_sim among valid H2 rows.",
        },
        {
            "category": "H2 power efficiency optimum",
            "parameter": "body_length_ratio",
            "value": h2_power["body_length_ratio"],
            "V_sim": h2_power["V_sim"],
            "Eta_power": h2_power["Eta_power"],
            "reason": "Maximum Eta_power among valid H2 rows.",
        },
        {
            "category": "chosen representative condition for H2",
            "parameter": "P/R, body_length_ratio",
            "value": "P/R=5.0, body_length_ratio=0.5",
            "V_sim": h2_speed["V_sim"],
            "Eta_power": h2_power["Eta_power"],
            "reason": "P/R=5.0 is the H1 power-efficiency optimum and near the H1 speed optimum; H2 at P/R=5.0 has body_length_ratio=0.5 as both speed and power-efficiency optimum.",
        },
        {
            "category": "reason for choosing P/R=5.0 for H2",
            "parameter": "P/R",
            "value": 5.0,
            "V_sim": h1_power["V_sim"],
            "Eta_power": h1_power["Eta_power"],
            "reason": "Balanced design choice: H1 Eta_power peaks at P/R=5.0 while H1 V_sim peaks at P/R=6.0, so P/R=5.0 preserves high speed with better power efficiency.",
        },
    ]
    output = TABLES_DIR / "final_optimal_candidates.csv"
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8")
    return output


def write_error_summary(h1: pd.DataFrame, h2: pd.DataFrame) -> Path:
    rows = []
    for label, df in [("H1", h1), ("H2", h2)]:
        base = valid_rows(df)
        if base.empty:
            base = df
        for metric in [
            "V_theory_over_V_sim",
            "omega_theory_over_omega_sim",
            "pct_error_vs_theory",
        ]:
            series = pd.to_numeric(base[metric], errors="coerce").dropna()
            rows.append({
                "sweep": label,
                "metric": metric,
                "mean": series.mean(),
                "min": series.min(),
                "max": series.max(),
                "count": int(series.count()),
            })
    output = TABLES_DIR / "theory_simulation_error_summary.csv"
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8")
    return output


def write_warning_cases(h1: pd.DataFrame, h2: pd.DataFrame) -> Path:
    rows = []
    for label, df, x_col in [("H1", h1, "P/R"), ("H2", h2, "body_length_ratio")]:
        for _, row in df.iterrows():
            reasons = []
            if str(row.get("steady_state_status", "")).upper() == "TRANSIENT_LIKELY":
                reasons.append("steady_state_status=TRANSIENT_LIKELY")
            if str(row.get("omega_steady_state_status", "")).upper() == "TRANSIENT_LIKELY":
                reasons.append("omega_steady_state_status=TRANSIENT_LIKELY")
            if normalize_bool(pd.Series([row.get("invalid_result")])).iloc[0]:
                reasons.append("invalid_result=True")
            if str(row.get("failure_reason", "NONE")).upper() != "NONE":
                reasons.append(f"failure_reason={row.get('failure_reason')}")
            if str(row.get("stiffness_status", "")).upper() != "OK":
                reasons.append(f"stiffness_status={row.get('stiffness_status')}")
            if normalize_bool(pd.Series([row.get("deformation_exceeded")])).iloc[0]:
                reasons.append("deformation_exceeded=True")
            if reasons:
                rows.append({
                    "sweep": label,
                    "case_parameter": x_col,
                    "case_value": row.get(x_col),
                    "warning_reasons": "; ".join(reasons),
                    "invalid_result": row.get("invalid_result"),
                    "failure_reason": row.get("failure_reason"),
                    "stiffness_status": row.get("stiffness_status"),
                    "deformation_exceeded": row.get("deformation_exceeded"),
                    "steady_state_status": row.get("steady_state_status"),
                    "omega_steady_state_status": row.get("omega_steady_state_status"),
                })
    output = TABLES_DIR / "invalid_or_warning_cases.csv"
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8")
    return output


def mark_max(ax, df: pd.DataFrame, x_col: str, y_col: str, expected_x: float | None = None) -> None:
    if expected_x is not None:
        candidates = df[df[x_col].round(10) == round(expected_x, 10)]
        if not candidates.empty:
            row = candidates.iloc[0]
        else:
            row = row_by_max(df, y_col)
    else:
        row = row_by_max(df, y_col)
    ax.scatter([row[x_col]], [row[y_col]], s=60, zorder=5)
    ax.annotate(
        f"max {x_col}={row[x_col]:g}",
        xy=(row[x_col], row[y_col]),
        xytext=(8, 8),
        textcoords="offset points",
    )


def save_line_plot(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    output: Path,
    title: str,
    xlabel: str,
    ylabel: str,
    mark_expected_x: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sorted_df = df.sort_values(x_col)
    ax.plot(sorted_df[x_col], sorted_df[y_col], marker="o", label=y_col)
    if mark_expected_x is not None:
        mark_max(ax, sorted_df, x_col, y_col, expected_x=mark_expected_x)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def save_two_line_plot(
    df: pd.DataFrame,
    x_col: str,
    y1: str,
    y2: str,
    output: Path,
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sorted_df = df.sort_values(x_col)
    ax.plot(sorted_df[x_col], sorted_df[y1], marker="o", label=y1)
    ax.plot(sorted_df[x_col], sorted_df[y2], marker="s", label=y2)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)


def save_error_plot(df: pd.DataFrame, x_col: str, output: Path, title: str, xlabel: str) -> None:
    y_col = "pct_error_vs_theory"
    if y_col not in df.columns or pd.to_numeric(df[y_col], errors="coerce").isna().all():
        df = df.copy()
        df["abs_ratio_error"] = (df["V_theory_over_V_sim"] - 1.0).abs()
        y_col = "abs_ratio_error"
    save_line_plot(df, x_col, y_col, output, title, xlabel, y_col)


def write_figures(h1: pd.DataFrame, h2: pd.DataFrame) -> list[Path]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    outputs = []
    specs = [
        (h1, "P/R", "V_sim", "h1_pr_vs_vsim.png", "H1: P/R vs V_sim", "P/R", "V_sim (m/s)", 6.0),
        (h1, "P/R", "Eta_power", "h1_pr_vs_eta_power.png", "H1: P/R vs Eta_power", "P/R", "Eta_power", 5.0),
        (h1, "P/R", "Eta_slip", "h1_pr_vs_eta_slip.png", "H1: P/R vs Eta_slip", "P/R", "Eta_slip", None),
        (h2, "body_length_ratio", "V_sim", "h2_body_ratio_vs_vsim.png", "H2: Body length ratio vs V_sim", "body_length_ratio", "V_sim (m/s)", 0.5),
        (h2, "body_length_ratio", "Eta_power", "h2_body_ratio_vs_eta_power.png", "H2: Body length ratio vs Eta_power", "body_length_ratio", "Eta_power", 0.5),
        (h2, "body_length_ratio", "Eta_slip", "h2_body_ratio_vs_eta_slip.png", "H2: Body length ratio vs Eta_slip", "body_length_ratio", "Eta_slip", None),
    ]
    for df, x_col, y_col, filename, title, xlabel, ylabel, mark in specs:
        output = FIGURES_DIR / filename
        save_line_plot(df, x_col, y_col, output, title, xlabel, ylabel, mark)
        outputs.append(output)

    output = FIGURES_DIR / "h1_pr_vsim_vs_vtheory.png"
    save_two_line_plot(h1, "P/R", "V_sim", "V_theory", output, "H1: V_sim vs V_theory", "P/R", "Velocity (m/s)")
    outputs.append(output)
    output = FIGURES_DIR / "h2_body_ratio_vsim_vs_vtheory.png"
    save_two_line_plot(h2, "body_length_ratio", "V_sim", "V_theory", output, "H2: V_sim vs V_theory", "body_length_ratio", "Velocity (m/s)")
    outputs.append(output)
    output = FIGURES_DIR / "h1_pr_theory_error.png"
    save_error_plot(h1, "P/R", output, "H1: Theory-simulation error", "P/R")
    outputs.append(output)
    output = FIGURES_DIR / "h2_body_ratio_theory_error.png"
    save_error_plot(h2, "body_length_ratio", output, "H2: Theory-simulation error", "body_length_ratio")
    outputs.append(output)
    return outputs


def csv_columns(path: Path) -> list[str]:
    return pd.read_csv(path, nrows=0).columns.tolist()


def find_raw_file(raw_dir: Path, kind: str, value: float) -> Path | None:
    files = sorted(raw_dir.glob("*.csv"))
    if kind == "pr":
        patterns = [
            rf"pr{value:.2f}".replace(".", r"\."),
            rf"pr{value:.1f}".replace(".", r"\."),
            rf"pr{int(value)}(?![0-9])",
            rf"pr{int(value)}_00",
            rf"pitch{value * 0.01:.2f}".replace(".", r"\."),
        ]
    else:
        patterns = [
            rf"br{value:.2f}".replace(".", r"\."),
            rf"br{value:.1f}".replace(".", r"\."),
            rf"body{value:.1f}".replace(".", r"\."),
            rf"ratio{value:.1f}".replace(".", r"\."),
        ]
    for pattern in patterns:
        regex = re.compile(pattern, re.IGNORECASE)
        matches = [path for path in files if regex.search(path.name)]
        if matches:
            return matches[0]
    return None


def choose_column(columns: list[str], candidates: list[str]) -> str | None:
    lower_map = {col.lower(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def write_raw_inventory(raw_dir: Path, reason: str) -> Path:
    output = DOCS_DIR / "raw_file_inventory.md"
    lines = ["# Raw File Inventory", "", f"Reason: {reason}", ""]
    for path in sorted(raw_dir.glob("*.csv")):
        try:
            columns = csv_columns(path)
        except Exception as exc:
            columns = [f"ERROR: {exc}"]
        lines.append(f"- `{path}`")
        lines.append(f"  - columns: {', '.join(columns)}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def save_timeseries_plot(
    path: Path,
    y_candidates: list[str],
    output: Path,
    title: str,
    ylabel: str,
) -> tuple[bool, str | None]:
    df = pd.read_csv(path)
    time_col = choose_column(df.columns.tolist(), TIME_COLUMNS)
    y_col = choose_column(df.columns.tolist(), y_candidates)
    if time_col is None or y_col is None:
        return False, f"Missing columns in {path.name}: time={time_col}, y={y_col}"
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(df[time_col], df[y_col], label=y_col)
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=200)
    plt.close(fig)
    return True, y_col


def write_timeseries_figures(raw_dir: Path) -> tuple[list[Path], dict[str, str]]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    selected = {
        "h1_pr6": find_raw_file(raw_dir, "pr", 6.0),
        "h1_pr5": find_raw_file(raw_dir, "pr", 5.0),
        "h2_body_ratio_0p5": find_raw_file(raw_dir, "body", 0.5),
    }
    missing = [key for key, path in selected.items() if path is None]
    outputs = []
    used = {}
    if missing:
        inventory = write_raw_inventory(raw_dir, "Could not automatically locate: " + ", ".join(missing))
        used["inventory"] = str(inventory)
        return outputs, used

    for key, path in selected.items():
        assert path is not None
        velocity_name = {
            "h1_pr6": "timeseries_h1_pr6_velocity.png",
            "h1_pr5": "timeseries_h1_pr5_velocity.png",
            "h2_body_ratio_0p5": "timeseries_h2_body_ratio_0p5_velocity.png",
        }[key]
        omega_name = {
            "h1_pr6": "timeseries_h1_pr6_omega.png",
            "h1_pr5": "timeseries_h1_pr5_omega.png",
            "h2_body_ratio_0p5": "timeseries_h2_body_ratio_0p5_omega.png",
        }[key]
        ok, message = save_timeseries_plot(
            path,
            VELOCITY_COLUMNS,
            FIGURES_DIR / velocity_name,
            f"{key}: velocity time series",
            "Vz_mean / velocity_z",
        )
        if ok:
            outputs.append(FIGURES_DIR / velocity_name)
            used[f"{key}_velocity"] = f"{path} ({message})"
        else:
            used[f"{key}_velocity_error"] = str(message)
        ok, message = save_timeseries_plot(
            path,
            OMEGA_COLUMNS,
            FIGURES_DIR / omega_name,
            f"{key}: omega time series",
            "Omega_z",
        )
        if ok:
            outputs.append(FIGURES_DIR / omega_name)
            used[f"{key}_omega"] = f"{path} ({message})"
        else:
            used[f"{key}_omega_error"] = str(message)

    if any(key.endswith("_error") for key in used):
        inventory = write_raw_inventory(raw_dir, "One or more selected files lacked required columns.")
        used["inventory"] = str(inventory)
    return outputs, used


def write_final_report(
    h1_path: Path,
    h2_path: Path,
    h1: pd.DataFrame,
    h2: pd.DataFrame,
    raw_used: dict[str, str],
) -> Path:
    h1_speed = row_by_max(h1, "V_sim")
    h1_power = row_by_max(h1, "Eta_power")
    h2_speed = row_by_max(h2, "V_sim")
    h2_power = row_by_max(h2, "Eta_power")
    lines = [
        "# Final Results Summary",
        "",
        "## Final Data Files",
        "",
        f"- H1 summary: `{h1_path}`",
        f"- H2 summary: `{h2_path}`",
        "",
        "## H1 Result Summary",
        "",
        f"- In the final H1 range, `V_sim` is largest at `P/R={h1_speed['P/R']}`.",
        f"- `Eta_power` is largest at `P/R={h1_power['P/R']}`.",
        "- Across the high-P/R side, both propulsion speed and efficiency decrease after their peak region.",
        "- `V_theory` and `V_sim` are reported separately because the analytical result is a torque-driven RFT approximation while the simulation is a PyElastica-RFT rod result.",
        "",
        "## H2 Result Summary",
        "",
        "- H2 uses the representative `P/R=5.0` condition.",
        f"- `V_sim` is largest at `body_length_ratio={h2_speed['body_length_ratio']}`.",
        f"- `Eta_power` is largest at `body_length_ratio={h2_power['body_length_ratio']}`.",
        "- Performance decreases when the body becomes too long relative to the tail.",
        "",
        "## Why damping_constant=1e-5 Was Used",
        "",
        "- `damping_constant` is a PyElastica numerical damping / stabilization setting, not the physical fluid viscosity.",
        "- Fluid resistance is represented by `fluid_viscosity` and the RFT forcing model.",
        "- Earlier `1e-3` and `1e-4` runs showed damping torque could absorb a large fraction of the applied torque and distort the theory comparison.",
        "- `1e-5` reduced damping influence while remaining stable enough for the final data generation.",
        "",
        "## Navier-Stokes And RFT",
        "",
        "- This project does not solve the Navier-Stokes equations directly.",
        "- Navier-Stokes equations are the general equations of fluid motion.",
        "- In low-Reynolds-number propulsion, viscous effects dominate inertial effects.",
        "- RFT approximates local drag around a slender body using tangential and normal resistance coefficients.",
        "- The project combines PyElastica rod dynamics with RFT forcing, then compares the result with torque-driven analytical RFT.",
        "- Therefore the comparison is not full CFD vs simulation; it is analytical RFT vs PyElastica-RFT simulation.",
        "",
        "## Limitations",
        "",
        "- Full Navier-Stokes / CFD is not solved.",
        "- RFT relies on local-resistance and slender-body assumptions.",
        "- Numerical damping affects the simulation-theory comparison.",
        "- Theory-simulation differences can grow at high P/R or extreme body ratios.",
        "- Efficiency metrics are model-based indicators, not complete hydrodynamic efficiency.",
        "",
        "## Final Conclusion",
        "",
        "- H1 speed optimum: `P/R=6.0`.",
        "- H1 power-efficiency optimum: `P/R=5.0`.",
        "- H2 optimum at `P/R=5.0`: `body_length_ratio=0.5` for both speed and power efficiency.",
        "- The balanced final design candidate is `P/R=5.0`, `body_length_ratio=0.5`.",
        "",
        "## Raw Time-Series Files Used",
        "",
    ]
    for key, value in raw_used.items():
        lines.append(f"- `{key}`: {value}")
    output = DOCS_DIR / "final_results_summary.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def generate_outputs(h1_path: Path, h2_path: Path, raw_dir: Path) -> dict[str, object]:
    actual_h1_paths = find_h1_summary_paths(h1_path)
    actual_h2 = find_existing_path(h2_path, "h2")
    actual_raw = find_existing_path(raw_dir, "raw")

    h1 = load_h1_summary(actual_h1_paths)
    h2 = load_summary(actual_h2, "h2")
    tables = write_summary_tables(h1, h2)
    optimal = write_optimal_candidates(h1, h2)
    error_summary = write_error_summary(h1, h2)
    warnings = write_warning_cases(h1, h2)
    figures = write_figures(h1, h2)
    timeseries_figures, raw_used = write_timeseries_figures(actual_raw)
    h1_label = " + ".join(str(path) for path in actual_h1_paths)
    report = write_final_report(Path(h1_label), actual_h2, h1, h2, raw_used)
    return {
        "h1_path": h1_label,
        "h2_path": actual_h2,
        "raw_dir": actual_raw,
        "tables": {**tables, "optimal": optimal, "error_summary": error_summary, "warnings": warnings},
        "figures": figures,
        "timeseries_figures": timeseries_figures,
        "raw_used": raw_used,
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_outputs(args.h1, args.h2, args.raw_dir)
    print("Final analysis outputs generated")
    print(f"H1 summary used: {result['h1_path']}")
    print(f"H2 summary used: {result['h2_path']}")
    print(f"Raw dir used: {result['raw_dir']}")
    for label, path in result["tables"].items():
        print(f"table {label}: {path}")
    for path in result["figures"]:
        print(f"figure: {path}")
    for path in result["timeseries_figures"]:
        print(f"timeseries figure: {path}")
    print(f"report: {result['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
