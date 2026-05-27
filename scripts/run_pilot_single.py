"""Run a guarded pilot single simulation before full sweeps."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "pilot_single.yaml"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


CONFIG_KEYS = [
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
]

PILOT_LIMITS = {
    "n_elem": 20,
    "total_steps": 1000,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a guarded pilot single simulation before full sweeps."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML config path. Defaults to configs/pilot_single.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved config without running the simulation.",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def normalize_config(config: dict) -> dict:
    missing = [key for key in CONFIG_KEYS if key not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")

    normalized = dict(config)
    normalized["n_elem"] = int(normalized["n_elem"])
    normalized["total_steps"] = int(normalized["total_steps"])
    normalized["step_skip"] = int(normalized["step_skip"])

    for key in [
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
    ]:
        normalized[key] = float(normalized[key])

    return normalized


def exceeds_pilot_limits(config: dict) -> bool:
    return (
        config["n_elem"] > PILOT_LIMITS["n_elem"]
        or config["total_steps"] > PILOT_LIMITS["total_steps"]
    )


def print_config_summary(config_path: Path, config: dict, explicit_config: bool) -> None:
    mode = "explicit config" if explicit_config else "default pilot config"
    print("Pilot single simulation runner")
    print("purpose: representative-condition check before full sweeps")
    print("note: this runner reports diagnostics only, not final physical conclusions")
    print(f"config: {config_path}")
    print(f"mode: {mode}")
    print("resolved config:")
    for key in CONFIG_KEYS:
        print(f"  {key}: {config[key]}")


def print_result_summary(result: dict, efficiency: dict | None) -> None:
    analytical = result.get("analytical") or {}
    stiffness = result.get("stiffness") or {}
    efficiency = efficiency or {}

    print("Pilot single summary")
    print(f"final_time: {result.get('final_time')}")
    print(f"V_sim: {analytical.get('V_sim')}")
    print(f"V_theory: {analytical.get('V_theory')}")
    print(f"omega_sim: {analytical.get('omega_sim')}")
    print(f"omega_theory: {analytical.get('omega_theory')}")
    print(f"theory_mode: {analytical.get('theory_mode')}")
    print(f"pct_error_vs_theory: {analytical.get('pct_error_vs_theory')}")
    print(f"pct_error_vs_sim: {analytical.get('pct_error_vs_sim')}")
    print(f"error_status: {analytical.get('error_status')}")
    print(f"steady_state_status: {analytical.get('steady_state_status')}")
    print(f"failure_reason: {result.get('failure_reason')}")
    print(f"invalid_result: {result.get('invalid_result')}")
    print(f"Eta_slip: {efficiency.get('eta_slip')}")
    print(f"Eta_power: {efficiency.get('eta_power')}")
    print(f"omega_source: {efficiency.get('omega_source')}")
    print(f"efficiency_model: {efficiency.get('efficiency_model')}")
    print(f"stiffness_status: {stiffness.get('status')}")
    print(f"deformation_exceeded: {stiffness.get('deformation_exceeded')}")
    print(f"worst_metric_pct: {stiffness.get('worst_metric_pct')}")
    print("note: this pilot checks readiness only, not final physical conclusions")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    explicit_config = args.config is not None
    config_path = args.config if explicit_config else DEFAULT_CONFIG
    config_path = config_path if config_path.is_absolute() else PROJECT_ROOT / config_path

    try:
        config = normalize_config(load_config(config_path))
    except Exception as exc:
        print(f"Failed to load pilot single config: {exc}")
        return 1

    print_config_summary(config_path, config, explicit_config)

    if not explicit_config and exceeds_pilot_limits(config):
        print("Refusing to run: default pilot config exceeds pilot limits.")
        return 1
    if explicit_config and exceeds_pilot_limits(config):
        print("warning: explicit config exceeds the default pilot limits.")

    if args.dry_run:
        print("dry-run: simulation not executed")
        return 0

    from helical_propeller.efficiency import compute_efficiency
    from helical_propeller.simulator import run_simulation

    result = run_simulation(
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
    )
    efficiency = compute_efficiency(result, torque_magnitude=config["torque_magnitude"])
    print_result_summary(result, efficiency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
