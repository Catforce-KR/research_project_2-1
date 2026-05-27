"""Run a guarded H2 body-to-tail smoke sweep."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "sweep_h2_smoke.yaml"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


SWEEP_KEYS = [
    "pitch",
    "radius",
    "total_length",
    "n_elem",
    "body_ratio_values",
    "torque_magnitude",
    "dt",
    "total_steps",
    "step_skip",
    "fluid_viscosity",
    "density",
    "E",
    "nu",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a guarded H2 body-to-tail smoke sweep."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML config path. Defaults to configs/sweep_h2_smoke.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved config without running simulations.",
    )
    parser.add_argument(
        "--allow-long",
        action="store_true",
        help="Allow a config larger than the smoke guard limits to run.",
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def normalize_config(config: dict) -> dict:
    missing = [key for key in SWEEP_KEYS if key not in config]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")

    normalized = dict(config)
    normalized["body_ratio_values"] = [
        float(value) for value in normalized["body_ratio_values"]
    ]
    normalized["n_elem"] = int(normalized["n_elem"])
    normalized["total_steps"] = int(normalized["total_steps"])
    normalized["step_skip"] = int(normalized["step_skip"])

    for key in [
        "pitch",
        "radius",
        "total_length",
        "torque_magnitude",
        "dt",
        "fluid_viscosity",
        "density",
        "E",
        "nu",
    ]:
        normalized[key] = float(normalized[key])

    return normalized


def is_smoke_sized(config: dict) -> bool:
    return (
        len(config["body_ratio_values"]) <= 2
        and config["n_elem"] <= 6
        and config["total_steps"] <= 10
        and config["step_skip"] <= config["total_steps"]
    )


def print_config_summary(config_path: Path, config: dict, explicit_config: bool) -> None:
    mode = "explicit config" if explicit_config else "default smoke config"
    print("H2 body-to-tail sweep runner")
    print("purpose: smoke/dry verification only; no physical conclusion is reported")
    print(f"config: {config_path}")
    print(f"mode: {mode}")
    print("resolved config:")
    for key in SWEEP_KEYS:
        print(f"  {key}: {config[key]}")
    print(
        "execution size: "
        f"cases={len(config['body_ratio_values'])}, "
        f"n_elem={config['n_elem']}, "
        f"total_steps={config['total_steps']}"
    )


def summarize_results(results: dict) -> None:
    print("H2 smoke sweep summary")
    for body_ratio in sorted(results):
        row = results[body_ratio]
        print(
            "  "
            f"body_ratio={float(body_ratio):.2f}, "
            f"status={row.get('status')}, "
            f"body_length={row.get('body_length')}, "
            f"V_sim={row.get('V_sim')}, "
            f"V_theory={row.get('V_theory')}, "
            f"omega_theory={row.get('omega_theory')}, "
            f"theory_mode={row.get('theory_mode')}, "
            f"pct_error_vs_theory={row.get('pct_error_vs_theory')}, "
            f"pct_error_vs_sim={row.get('pct_error_vs_sim')}, "
            f"error_status={row.get('error_status')}, "
            f"steady_state_status={row.get('steady_state_status')}, "
            f"failure_reason={row.get('failure_reason')}, "
            f"invalid_result={row.get('invalid_result')}"
        )


def h2_timeseries_logger(original_logger):
    def log_with_body_ratio_name(sim_result, filepath=None, torque_magnitude=None):
        params = sim_result.get("parameters", {})
        body_ratio = float(params.get("body_length_ratio", 0.0))
        detail_name = f"sweep_h2_br{body_ratio:.2f}_timeseries.csv"
        return original_logger(
            sim_result,
            filepath=detail_name,
            torque_magnitude=torque_magnitude,
        )

    return log_with_body_ratio_name


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    explicit_config = args.config is not None
    config_path = args.config if explicit_config else DEFAULT_CONFIG
    config_path = config_path if config_path.is_absolute() else PROJECT_ROOT / config_path

    try:
        config = normalize_config(load_config(config_path))
    except Exception as exc:
        print(f"Failed to load H2 sweep config: {exc}")
        return 1

    print_config_summary(config_path, config, explicit_config)

    smoke_sized = is_smoke_sized(config)
    if not explicit_config and not smoke_sized:
        print("Refusing to run: default config is not smoke-sized.")
        return 1

    if args.dry_run:
        if explicit_config and not smoke_sized:
            print("dry-run: explicit config is larger than smoke limits; --allow-long is required to execute it.")
        print("dry-run: simulation not executed")
        return 0

    if explicit_config and not smoke_sized and not args.allow_long:
        print("Refusing to run: explicit config is larger than smoke limits. Re-run with --allow-long to execute.")
        return 1
    if explicit_config and not smoke_sized and args.allow_long:
        print(
            "long-run allowed: "
            f"cases={len(config['body_ratio_values'])}, "
            f"n_elem={config['n_elem']}, "
            f"total_steps={config['total_steps']}"
        )

    from helical_propeller import simulator as simulator_module
    from helical_propeller.sweeps import parameter_sweep_h2

    original_logger = simulator_module.log_simulation_timeseries
    simulator_module.log_simulation_timeseries = h2_timeseries_logger(original_logger)
    try:
        results = parameter_sweep_h2(
            pitch=config["pitch"],
            radius=config["radius"],
            total_length=config["total_length"],
            n_elem=config["n_elem"],
            body_ratio_values=config["body_ratio_values"],
            torque_magnitude=config["torque_magnitude"],
            dt=config["dt"],
            total_steps=config["total_steps"],
            step_skip=config["step_skip"],
            fluid_viscosity=config["fluid_viscosity"],
            density=config["density"],
            E=config["E"],
            nu=config["nu"],
        )
    finally:
        simulator_module.log_simulation_timeseries = original_logger

    summarize_results(results)
    print("note: this smoke sweep checks execution only, not physical conclusions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
