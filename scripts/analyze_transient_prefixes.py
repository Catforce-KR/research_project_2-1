"""Analyze time-series prefixes from one long P/R=3.0 transient check."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "h1_pr3_transient_check_480000.yaml"
DEFAULT_RAW = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "h1_pr3_transient_check_duration_480000_steps480000.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "h1_pr3_transient_check_duration_480000_prefix_summary.csv"
)
DEFAULT_CHECKPOINTS = (60000, 120000, 240000, 360000, 480000)

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute prefix diagnostics from a long P/R=3.0 raw timeseries."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--checkpoints",
        nargs="+",
        type=int,
        default=list(DEFAULT_CHECKPOINTS),
        help="Prefix endpoint steps to evaluate.",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return config


def _ratio(numerator, denominator):
    if numerator is None or denominator is None:
        return None
    numerator = float(numerator)
    denominator = float(denominator)
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    if abs(denominator) <= 1e-30:
        return None
    return numerator / denominator


def _prefix_invalid_reason(prefix: pd.DataFrame, theory: dict) -> tuple[bool, str]:
    if not np.isfinite(prefix[["Vz_mean", "Omega_z"]].to_numpy(dtype=float)).all():
        return True, "NONFINITE_VELOCITY"
    if not math.isfinite(float(theory["V_theory"])) or not math.isfinite(
        float(theory["omega_theory"])
    ):
        return True, "NONFINITE_THEORY"
    return False, "NONE"


def analyze_prefixes(
    timeseries: pd.DataFrame,
    config: dict,
    checkpoints: list[int] | tuple[int, ...],
) -> pd.DataFrame:
    from helical_propeller.analysis_metrics import (
        compute_error_metrics,
        compute_steady_state_metrics,
    )
    from helical_propeller.theory import (
        compute_balance_diagnostics,
        compute_theoretical_velocity,
    )

    dt = float(config["dt"])
    raw_steps = config["total_steps"]
    total_steps = int(raw_steps[0] if isinstance(raw_steps, list) else raw_steps)
    theory = compute_theoretical_velocity(
        pitch=float(config["pitch"]),
        radius=float(config["radius"]),
        total_length=float(config["total_length"]),
        filament_radius=float(config["radius"]),
        fluid_viscosity=float(config["fluid_viscosity"]),
        torque_magnitude=float(config["torque_magnitude"]),
        body_length_ratio=float(config["body_length_ratio"]),
        body_radius=float(config.get("body_radius", config["radius"])),
    )
    rows = []
    for checkpoint_steps in checkpoints:
        if checkpoint_steps > total_steps:
            raise ValueError(
                f"checkpoint_steps={checkpoint_steps} exceeds configured total_steps={total_steps}"
            )
        checkpoint_time = checkpoint_steps * dt
        prefix = timeseries.loc[
            timeseries["Time"] <= checkpoint_time + max(1e-12, abs(checkpoint_time) * 1e-10)
        ]
        if prefix.empty:
            raise ValueError(f"No timeseries records found for checkpoint {checkpoint_steps}")

        vz = prefix["Vz_mean"].tolist()
        omega = prefix["Omega_z"].tolist()
        steady = compute_steady_state_metrics(vz)
        omega_steady = compute_steady_state_metrics(omega)
        V_sim = steady["steady_last_mean"]
        omega_sim = omega_steady["steady_last_mean"]
        errors = compute_error_metrics(V_sim, theory["V_theory"])
        balance = compute_balance_diagnostics(
            V_sim=V_sim,
            omega_sim=omega_sim,
            A_total=theory["A_total"],
            B=theory["B"],
            D_total=theory["D_total"],
            torque_magnitude=float(config["torque_magnitude"]),
        )
        invalid_result, failure_reason = _prefix_invalid_reason(prefix, theory)
        window_samples = max(1, len(prefix) // 5)
        rows.append({
            "checkpoint_steps": int(checkpoint_steps),
            "final_time": float(prefix["Time"].iloc[-1]),
            "sample_count": len(prefix),
            "window_samples": window_samples,
            "V_sim": V_sim,
            "V_theory": theory["V_theory"],
            "V_theory_over_V_sim": _ratio(theory["V_theory"], V_sim),
            "omega_sim": omega_sim,
            "omega_theory": theory["omega_theory"],
            "omega_theory_over_omega_sim": _ratio(theory["omega_theory"], omega_sim),
            "pct_error_vs_theory": errors["pct_error_vs_theory"],
            "error_status": errors["error_status"],
            "steady_state_status": steady["steady_state_status"],
            "steady_relative_change": steady["steady_relative_change"],
            "omega_steady_state_status": omega_steady["steady_state_status"],
            "omega_steady_relative_change": omega_steady["steady_relative_change"],
            "force_residual_norm": balance["force_residual_norm"],
            "torque_residual_norm": balance["torque_residual_norm"],
            "effective_D_from_omega_sim": balance["effective_rotational_resistance"],
            "effective_D_ratio": balance["effective_rotational_resistance_ratio"],
            "invalid_result": invalid_result,
            "failure_reason": failure_reason,
        })
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    raw_path = args.raw if args.raw.is_absolute() else PROJECT_ROOT / args.raw
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    try:
        config = load_config(config_path)
        timeseries = pd.read_csv(raw_path)
        summary = analyze_prefixes(timeseries, config, args.checkpoints)
    except Exception as exc:
        print(f"Failed to analyze transient prefixes: {exc}")
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False, encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"[OK] transient prefix summary saved: {output_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
