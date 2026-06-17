"""Analyze damping summary CSV output without running simulations."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "h1_pr3_damping_check_summary.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "damping_decision_summary.csv"

CORE_FIELDS = [
    "damping_constant",
    "V_sim",
    "omega_sim",
    "V_theory_over_V_sim",
    "omega_theory_over_omega_sim",
    "damping_torque_to_applied_ratio",
    "torque_balance_with_damping_residual_ratio",
    "steady_state_status",
    "omega_steady_state_status",
    "invalid_result",
    "failure_reason",
    "stiffness_status",
    "deformation_exceeded",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank damping candidates from a damping summary CSV."
    )
    parser.add_argument(
        "summary_csv",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to damping summary CSV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Decision summary CSV path.",
    )
    return parser.parse_args(argv)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _as_float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return math.nan
    return result


def _safe_ratio_penalty(value: float, target: float = 1.0) -> float:
    if not math.isfinite(value) or value <= 0.0:
        return 1000.0
    return abs(math.log(value / target))


def _eligibility_reason(row: pd.Series) -> tuple[bool, str]:
    if _as_bool(row.get("invalid_result")):
        return False, f"invalid_result=True ({row.get('failure_reason', 'UNKNOWN')})"
    stiffness_status = row.get("stiffness_status")
    if stiffness_status is not None and not pd.isna(stiffness_status):
        if str(stiffness_status).strip().upper() != "OK":
            return False, f"stiffness_status={stiffness_status}"
    if _as_bool(row.get("deformation_exceeded")):
        return False, "deformation_exceeded=True"
    return True, "OK"


def score_row(row: pd.Series) -> float:
    """Lower score is better; invalid rows are filtered before ranking."""
    omega_ratio = _as_float(row.get("omega_theory_over_omega_sim"))
    velocity_ratio = _as_float(row.get("V_theory_over_V_sim"))
    damping_ratio = _as_float(row.get("damping_torque_to_applied_ratio"))
    residual_ratio = _as_float(row.get("torque_balance_with_damping_residual_ratio"))

    score = 0.0
    score += 2.0 * _safe_ratio_penalty(omega_ratio, target=1.0)
    score += 0.8 * _safe_ratio_penalty(velocity_ratio, target=1.0)
    if math.isfinite(damping_ratio):
        score += 1.5 * max(damping_ratio, 0.0)
        if damping_ratio > 0.2:
            score += 1.0
    else:
        score += 2.0
    if math.isfinite(residual_ratio):
        score += 0.5 * max(residual_ratio, 0.0)
    if str(row.get("omega_steady_state_status", "")).strip().upper() == "OK":
        score -= 0.5
    if str(row.get("steady_state_status", "")).strip().upper() == "OK":
        score -= 0.5
    return score


def analyze(summary_csv: Path) -> tuple[pd.DataFrame, list[str]]:
    path = _resolve(summary_csv)
    if not path.is_file():
        raise FileNotFoundError(
            f"Summary CSV not found: {path}. Copy the Colab summary CSV here or pass its path."
        )

    df = pd.read_csv(path)
    missing = [field for field in CORE_FIELDS if field not in df.columns]
    warnings: list[str] = []
    if missing:
        warnings.append(f"Missing expected columns: {', '.join(missing)}")

    for field in CORE_FIELDS:
        if field not in df.columns:
            df[field] = pd.NA

    decision = df[CORE_FIELDS].copy()
    eligible = []
    reasons = []
    scores = []
    for _, row in decision.iterrows():
        is_eligible, reason = _eligibility_reason(row)
        eligible.append(is_eligible)
        reasons.append(reason)
        scores.append(score_row(row) if is_eligible else math.inf)
    decision["eligible"] = eligible
    decision["exclusion_reason"] = reasons
    decision["decision_score"] = scores

    decision = decision.sort_values(
        by=["eligible", "decision_score", "damping_constant"],
        ascending=[False, True, True],
        kind="stable",
    ).reset_index(drop=True)

    decision["recommendation"] = ""
    eligible_indices = decision.index[decision["eligible"]].tolist()
    if eligible_indices:
        decision.loc[eligible_indices[0], "recommendation"] = "PRIMARY"
    if len(eligible_indices) > 1:
        decision.loc[eligible_indices[1], "recommendation"] = "SECONDARY"
    if not eligible_indices:
        warnings.append("No eligible damping candidate found.")

    high_damping = decision[
        pd.to_numeric(decision["damping_torque_to_applied_ratio"], errors="coerce") > 0.2
    ]
    if not high_damping.empty:
        warnings.append("Some rows have damping_torque_to_applied_ratio > 0.2.")
    if (
        "TRANSIENT_LIKELY"
        in set(str(value).strip().upper() for value in decision["steady_state_status"])
    ):
        warnings.append("At least one velocity row is TRANSIENT_LIKELY; use medium validation.")
    return decision, warnings


def print_report(decision: pd.DataFrame, warnings: list[str]) -> None:
    print("Damping decision summary")
    print(decision.to_string(index=False))
    primary = decision[decision["recommendation"] == "PRIMARY"]
    secondary = decision[decision["recommendation"] == "SECONDARY"]
    if not primary.empty:
        print(f"recommended damping: {primary.iloc[0]['damping_constant']}")
    if not secondary.empty:
        print(f"secondary candidate: {secondary.iloc[0]['damping_constant']}")
    if warnings:
        print("warnings:")
        for warning in warnings:
            print(f"  - {warning}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        decision, warnings = analyze(args.summary_csv)
    except FileNotFoundError as exc:
        print(exc)
        return 1
    print_report(decision, warnings)

    output_path = _resolve(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    decision.to_csv(output_path, index=False, encoding="utf-8")
    print(f"[OK] decision summary saved: {output_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
