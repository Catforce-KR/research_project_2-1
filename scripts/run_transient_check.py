"""Run one H1 P/R condition over increasing durations for transient diagnosis."""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "h1_pr3_transient_check.yaml"
BASE_OUTPUT_NAME = "h1_pr3_transient_check"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


COMMON_CONFIG_KEYS = (
    "pitch",
    "radius",
    "total_length",
    "body_length_ratio",
    "n_elem",
    "torque_magnitude",
    "dt",
    "fluid_viscosity",
    "density",
    "E",
    "nu",
)

SUMMARY_FIELDS = (
    "total_steps",
    "step_skip",
    "final_time",
    "V_sim",
    "V_theory",
    "V_theory_over_V_sim",
    "omega_sim",
    "omega_theory",
    "omega_theory_over_omega_sim",
    "pct_error_vs_theory",
    "error_status",
    "steady_state_status",
    "omega_steady_state_status",
    "steady_relative_change",
    "omega_steady_relative_change",
    "force_residual_norm",
    "torque_residual_norm",
    "torque_coupling_term",
    "torque_rotational_resistance_term",
    "torque_applied_term",
    "torque_balance_residual",
    "torque_coupling_to_applied_ratio",
    "torque_rotational_to_applied_ratio",
    "torque_residual_to_applied_ratio",
    "helix_rotational_resistance",
    "body_rotational_drag",
    "total_rotational_resistance",
    "body_rotational_fraction",
    "helix_rotational_fraction",
    "effective_D_from_omega_sim",
    "effective_rotational_resistance_ratio",
    "effective_D_ratio",
    "D_total",
    "torque_frame_assumption",
    "omega_frame",
    "torque_axis",
    "omega_axis",
    "torque_sign_convention",
    "applied_torque_material_component",
    "applied_torque_global_z_projection",
    "applied_torque_axis_alignment",
    "torque_projection_to_omega_axis",
    "torque_frame_status",
    "frame_mismatch_risk",
    "damping_model",
    "damping_constant",
    "damping_effective_coefficient",
    "rotational_damping_mass",
    "damping_estimate_status",
    "damping_torque_estimate",
    "damping_torque_to_applied_ratio",
    "torque_balance_with_damping_residual",
    "torque_balance_with_damping_residual_ratio",
    "torque_balance_missing_fraction",
    "torque_balance_interpretation",
    "invalid_result",
    "failure_reason",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run P/R=3.0 with increasing durations to diagnose transient behavior."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="YAML config path. Defaults to configs/h1_pr3_transient_check.yaml.",
    )
    parser.add_argument(
        "--tag",
        default="",
        help="Optional suffix for preserving separate transient-check outputs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved cases without running simulations.",
    )
    args = parser.parse_args(argv)
    if args.tag and re.fullmatch(r"[A-Za-z0-9_-]+", args.tag) is None:
        parser.error("--tag may contain only letters, numbers, underscores, and hyphens")
    return args


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return config


def normalize_config(config: dict) -> dict:
    missing = [
        key for key in (*COMMON_CONFIG_KEYS, "total_steps", "step_skip")
        if key not in config
    ]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")

    normalized = dict(config)
    for key in (
        "pitch",
        "radius",
        "total_length",
        "body_length_ratio",
        "torque_magnitude",
        "dt",
        "fluid_viscosity",
        "density",
        "E",
        "nu",
    ):
        normalized[key] = float(normalized[key])
    normalized["n_elem"] = int(normalized["n_elem"])
    normalized["total_steps"] = [int(value) for value in normalized["total_steps"]]
    normalized["step_skip"] = [int(value) for value in normalized["step_skip"]]

    if len(normalized["total_steps"]) != len(normalized["step_skip"]):
        raise ValueError("total_steps and step_skip must contain the same number of entries")
    for steps, skip in zip(normalized["total_steps"], normalized["step_skip"]):
        if steps <= 0 or skip <= 0 or skip > steps:
            raise ValueError("Each step_skip must be positive and no larger than total_steps")
    return normalized


def _ratio(numerator, denominator):
    if numerator is None or denominator is None:
        return None
    if not math.isfinite(float(numerator)) or not math.isfinite(float(denominator)):
        return None
    if abs(float(denominator)) <= 1e-30:
        return None
    return float(numerator) / float(denominator)


def build_summary_row(result: dict, total_steps: int, step_skip: int) -> dict:
    analytical = result.get("analytical") or {}
    return {
        "total_steps": total_steps,
        "step_skip": step_skip,
        "final_time": result.get("final_time"),
        "V_sim": analytical.get("V_sim"),
        "V_theory": analytical.get("V_theory"),
        "V_theory_over_V_sim": _ratio(
            analytical.get("V_theory"),
            analytical.get("V_sim"),
        ),
        "omega_sim": analytical.get("omega_sim"),
        "omega_theory": analytical.get("omega_theory"),
        "omega_theory_over_omega_sim": _ratio(
            analytical.get("omega_theory"),
            analytical.get("omega_sim"),
        ),
        "pct_error_vs_theory": analytical.get("pct_error_vs_theory"),
        "error_status": analytical.get("error_status"),
        "steady_state_status": analytical.get("steady_state_status"),
        "omega_steady_state_status": analytical.get("omega_state_status"),
        "steady_relative_change": analytical.get("steady_relative_change"),
        "omega_steady_relative_change": analytical.get("omega_relative_change"),
        "force_residual_norm": analytical.get("force_residual_norm"),
        "torque_residual_norm": analytical.get("torque_residual_norm"),
        "torque_coupling_term": analytical.get("torque_coupling_term"),
        "torque_rotational_resistance_term": analytical.get(
            "torque_rotational_resistance_term"
        ),
        "torque_applied_term": analytical.get("torque_applied_term"),
        "torque_balance_residual": analytical.get("torque_balance_residual"),
        "torque_coupling_to_applied_ratio": analytical.get(
            "torque_coupling_to_applied_ratio"
        ),
        "torque_rotational_to_applied_ratio": analytical.get(
            "torque_rotational_to_applied_ratio"
        ),
        "torque_residual_to_applied_ratio": analytical.get(
            "torque_residual_to_applied_ratio"
        ),
        "helix_rotational_resistance": analytical.get("helix_rotational_resistance"),
        "body_rotational_drag": analytical.get("body_rotational_drag"),
        "total_rotational_resistance": analytical.get("total_rotational_resistance"),
        "body_rotational_fraction": analytical.get("body_rotational_fraction"),
        "helix_rotational_fraction": analytical.get("helix_rotational_fraction"),
        "effective_D_from_omega_sim": analytical.get(
            "effective_D_from_omega_sim",
            analytical.get("effective_rotational_resistance"),
        ),
        "effective_rotational_resistance_ratio": analytical.get(
            "effective_rotational_resistance_ratio"
        ),
        "effective_D_ratio": analytical.get(
            "effective_D_ratio",
            analytical.get("effective_rotational_resistance_ratio"),
        ),
        "D_total": analytical.get("D_total"),
        "torque_frame_assumption": analytical.get("torque_frame_assumption"),
        "omega_frame": analytical.get("omega_frame"),
        "torque_axis": analytical.get("torque_axis"),
        "omega_axis": analytical.get("omega_axis"),
        "torque_sign_convention": analytical.get("torque_sign_convention"),
        "applied_torque_material_component": analytical.get("applied_torque_material_component"),
        "applied_torque_global_z_projection": analytical.get(
            "applied_torque_global_z_projection"
        ),
        "applied_torque_axis_alignment": analytical.get("applied_torque_axis_alignment"),
        "torque_projection_to_omega_axis": analytical.get("torque_projection_to_omega_axis"),
        "torque_frame_status": analytical.get("torque_frame_status"),
        "frame_mismatch_risk": analytical.get("frame_mismatch_risk"),
        "damping_model": analytical.get("damping_model"),
        "damping_constant": analytical.get("damping_constant"),
        "damping_effective_coefficient": analytical.get("damping_effective_coefficient"),
        "rotational_damping_mass": analytical.get("rotational_damping_mass"),
        "damping_estimate_status": analytical.get("damping_estimate_status"),
        "damping_torque_estimate": analytical.get("damping_torque_estimate"),
        "damping_torque_to_applied_ratio": analytical.get(
            "damping_torque_to_applied_ratio"
        ),
        "torque_balance_with_damping_residual": analytical.get(
            "torque_balance_with_damping_residual"
        ),
        "torque_balance_with_damping_residual_ratio": analytical.get(
            "torque_balance_with_damping_residual_ratio"
        ),
        "torque_balance_missing_fraction": analytical.get("torque_balance_missing_fraction"),
        "torque_balance_interpretation": analytical.get("torque_balance_interpretation"),
        "invalid_result": result.get("invalid_result"),
        "failure_reason": result.get("failure_reason"),
    }


def _print_config(config_path: Path, config: dict) -> None:
    print("H1 P/R=3.0 transient check")
    print("purpose: assess duration sensitivity before any additional physics change")
    print(f"config: {config_path}")
    print(f"P/R: {config['pitch'] / config['radius']}")
    for steps, skip in zip(config["total_steps"], config["step_skip"]):
        print(f"  case: total_steps={steps}, step_skip={skip}, final_time={steps * config['dt']}")


def _timeseries_logger(original_logger, output_prefix: str):
    def log_tagged_timeseries(sim_result, filepath=None, torque_magnitude=None):
        steps = sim_result["parameters"]["total_steps"]
        detail_name = f"{output_prefix}_steps{steps}.csv"
        return original_logger(
            sim_result,
            filepath=detail_name,
            torque_magnitude=torque_magnitude,
        )

    return log_tagged_timeseries


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    try:
        config = normalize_config(load_config(config_path))
    except Exception as exc:
        print(f"Failed to load transient check config: {exc}")
        return 1
    _print_config(config_path, config)
    if args.dry_run:
        print("dry-run: simulation not executed")
        return 0

    output_prefix = BASE_OUTPUT_NAME if not args.tag else f"{BASE_OUTPUT_NAME}_{args.tag}"
    from helical_propeller import simulator as simulator_module

    original_timeseries_logger = simulator_module.log_simulation_timeseries
    simulator_module.log_simulation_timeseries = _timeseries_logger(
        original_timeseries_logger,
        output_prefix,
    )
    rows = []
    try:
        for total_steps, step_skip in zip(config["total_steps"], config["step_skip"]):
            result = simulator_module.run_simulation(
                pitch=config["pitch"],
                radius=config["radius"],
                total_length=config["total_length"],
                body_length_ratio=config["body_length_ratio"],
                n_elem=config["n_elem"],
                torque_magnitude=config["torque_magnitude"],
                dt=config["dt"],
                total_steps=total_steps,
                step_skip=step_skip,
                fluid_viscosity=config["fluid_viscosity"],
                density=config["density"],
                E=config["E"],
                nu=config["nu"],
            )
            row = build_summary_row(result, total_steps, step_skip)
            rows.append(row)
            print(
                "transient summary: "
                f"steps={total_steps}, "
                f"V_ratio={row['V_theory_over_V_sim']}, "
                f"omega_ratio={row['omega_theory_over_omega_sim']}, "
                f"steady={row['steady_state_status']}, "
                f"omega_steady={row['omega_steady_state_status']}, "
                f"torque_rot/applied={row['torque_rotational_to_applied_ratio']}, "
                f"torque_coupling/applied={row['torque_coupling_to_applied_ratio']}, "
                f"torque_resid/applied={row['torque_residual_to_applied_ratio']}, "
                f"effective_D_ratio={row['effective_D_ratio']}, "
                f"damping/applied={row['damping_torque_to_applied_ratio']}, "
                f"resid_with_damping/applied={row['torque_balance_with_damping_residual_ratio']}, "
                f"torque_interp={row['torque_balance_interpretation']}, "
                f"frames={row['torque_frame_status']}/{row['omega_frame']}"
            )
    finally:
        simulator_module.log_simulation_timeseries = original_timeseries_logger

    output_path = PROJECT_ROOT / "data" / "processed" / f"{output_prefix}_summary.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=SUMMARY_FIELDS).to_csv(
        output_path,
        index=False,
        encoding="utf-8",
    )
    print(f"[OK] transient summary saved: {output_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
