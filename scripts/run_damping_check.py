"""Run P/R=3.0 cases over damping constants for theory/simulation diagnosis."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "h1_pr3_damping_check.yaml"
OUTPUT_NAME = "h1_pr3_damping_check_summary.csv"

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
    "total_steps",
    "step_skip",
    "fluid_viscosity",
    "density",
    "E",
    "nu",
    "damping_constants",
)

SUMMARY_FIELDS = (
    "damping_constant",
    "pitch_over_radius",
    "total_steps",
    "step_skip",
    "final_time",
    "V_sim",
    "omega_sim",
    "V_theory_over_V_sim",
    "omega_theory_over_omega_sim",
    "damping_torque_to_applied_ratio",
    "torque_residual_to_applied_ratio",
    "torque_balance_with_damping_residual_ratio",
    "steady_state_status",
    "omega_steady_state_status",
    "invalid_result",
    "failure_reason",
    "stiffness_status",
    "deformation_exceeded",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare damping_constant effects for the H1 P/R=3.0 condition."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="YAML config path. Defaults to configs/h1_pr3_damping_check.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved cases without running simulations.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Optional number of leading damping constants to run.",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return config


def normalize_config(config: dict) -> dict:
    missing = [key for key in COMMON_CONFIG_KEYS if key not in config]
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
    normalized["total_steps"] = int(normalized["total_steps"])
    normalized["step_skip"] = int(normalized["step_skip"])
    normalized["damping_constants"] = [
        float(value) for value in normalized["damping_constants"]
    ]

    if normalized["total_steps"] <= 0:
        raise ValueError("total_steps must be positive")
    if normalized["step_skip"] <= 0 or normalized["step_skip"] > normalized["total_steps"]:
        raise ValueError("step_skip must be positive and no larger than total_steps")
    if not normalized["damping_constants"]:
        raise ValueError("damping_constants must not be empty")
    if any(value < 0.0 or not math.isfinite(value) for value in normalized["damping_constants"]):
        raise ValueError("damping_constants must be finite non-negative values")
    return normalized


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


def _damping_tag(damping_constant: float) -> str:
    return f"damping{damping_constant:.0e}".replace("+", "")


def build_summary_row(result: dict, config: dict, damping_constant: float) -> dict:
    analytical = result.get("analytical") or {}
    stiffness = result.get("stiffness") or {}
    return {
        "damping_constant": damping_constant,
        "pitch_over_radius": config["pitch"] / config["radius"],
        "total_steps": config["total_steps"],
        "step_skip": config["step_skip"],
        "final_time": result.get("final_time"),
        "V_sim": analytical.get("V_sim"),
        "omega_sim": analytical.get("omega_sim"),
        "V_theory_over_V_sim": _ratio(analytical.get("V_theory"), analytical.get("V_sim")),
        "omega_theory_over_omega_sim": _ratio(
            analytical.get("omega_theory"),
            analytical.get("omega_sim"),
        ),
        "damping_torque_to_applied_ratio": analytical.get(
            "damping_torque_to_applied_ratio"
        ),
        "torque_residual_to_applied_ratio": analytical.get(
            "torque_residual_to_applied_ratio"
        ),
        "torque_balance_with_damping_residual_ratio": analytical.get(
            "torque_balance_with_damping_residual_ratio"
        ),
        "steady_state_status": analytical.get("steady_state_status"),
        "omega_steady_state_status": analytical.get("omega_state_status"),
        "invalid_result": result.get("invalid_result"),
        "failure_reason": result.get("failure_reason"),
        "stiffness_status": stiffness.get("status", result.get("stiffness_status")),
        "deformation_exceeded": stiffness.get(
            "deformation_exceeded",
            result.get("deformation_exceeded"),
        ),
    }


def _print_config(config_path: Path, config: dict) -> None:
    print("H1 P/R=3.0 damping check")
    print("purpose: compare damping_constant effects without changing RFT/body drag")
    print(f"config: {config_path}")
    print(f"P/R: {config['pitch'] / config['radius']}")
    print(
        "case: "
        f"total_steps={config['total_steps']}, "
        f"step_skip={config['step_skip']}, "
        f"final_time={config['total_steps'] * config['dt']}"
    )
    print(f"damping_constants: {config['damping_constants']}")


def _timeseries_logger(original_logger, damping_constant: float):
    def log_tagged_timeseries(sim_result, filepath=None, torque_magnitude=None):
        detail_name = f"h1_pr3_damping_check_{_damping_tag(damping_constant)}.csv"
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
        print(f"Failed to load damping check config: {exc}")
        return 1

    if args.max_cases is not None:
        if args.max_cases <= 0:
            print("--max-cases must be positive")
            return 1
        config["damping_constants"] = config["damping_constants"][: args.max_cases]

    _print_config(config_path, config)
    if args.dry_run:
        print("dry-run: simulation not executed")
        return 0

    from helical_propeller import simulator as simulator_module

    original_timeseries_logger = simulator_module.log_simulation_timeseries
    rows = []
    try:
        for damping_constant in config["damping_constants"]:
            simulator_module.log_simulation_timeseries = _timeseries_logger(
                original_timeseries_logger,
                damping_constant,
            )
            result = simulator_module.run_simulation(
                pitch=config["pitch"],
                radius=config["radius"],
                total_length=config["total_length"],
                body_length_ratio=config["body_length_ratio"],
                n_elem=config["n_elem"],
                torque_magnitude=config["torque_magnitude"],
                dt=config["dt"],
                total_steps=config["total_steps"],
                step_skip=config["step_skip"],
                fluid_viscosity=config["fluid_viscosity"],
                density=config["density"],
                E=config["E"],
                nu=config["nu"],
                damping_constant=damping_constant,
            )
            row = build_summary_row(result, config, damping_constant)
            rows.append(row)
            print(
                "damping summary: "
                f"damping_constant={damping_constant}, "
                f"V_ratio={row['V_theory_over_V_sim']}, "
                f"omega_ratio={row['omega_theory_over_omega_sim']}, "
                f"damping/applied={row['damping_torque_to_applied_ratio']}, "
                f"torque_resid/applied={row['torque_residual_to_applied_ratio']}, "
                "resid_with_damping/applied="
                f"{row['torque_balance_with_damping_residual_ratio']}, "
                f"steady={row['steady_state_status']}, "
                f"omega_steady={row['omega_steady_state_status']}, "
                f"stiffness={row['stiffness_status']}, "
                f"invalid={row['invalid_result']}"
            )
    finally:
        simulator_module.log_simulation_timeseries = original_timeseries_logger

    output_path = PROJECT_ROOT / "data" / "processed" / OUTPUT_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=SUMMARY_FIELDS).to_csv(
        output_path,
        index=False,
        encoding="utf-8",
    )
    print(f"[OK] damping summary saved: {output_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
