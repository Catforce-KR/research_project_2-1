"""Run a guarded stiffness calibration before full sweeps."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "stiffness_calibration_smoke.yaml"

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
    "E_values",
    "nu",
    "fluid_viscosity",
    "density",
    "dt",
    "total_steps",
    "step_skip",
    "deformation_threshold",
]

SMOKE_LIMITS = {
    "n_elem": 20,
    "total_steps": 1000,
    "E_values": 4,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a guarded stiffness calibration before full sweeps."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML config path. Defaults to configs/stiffness_calibration_smoke.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved config without running calibration.",
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
    normalized["E_values"] = [float(value) for value in normalized["E_values"]]
    normalized["n_elem"] = int(normalized["n_elem"])
    normalized["total_steps"] = int(normalized["total_steps"])
    normalized["step_skip"] = int(normalized["step_skip"])

    for key in [
        "pitch",
        "radius",
        "total_length",
        "body_length_ratio",
        "torque_magnitude",
        "nu",
        "fluid_viscosity",
        "density",
        "dt",
        "deformation_threshold",
    ]:
        normalized[key] = float(normalized[key])

    return normalized


def exceeds_smoke_limits(config: dict) -> bool:
    return (
        config["n_elem"] > SMOKE_LIMITS["n_elem"]
        or config["total_steps"] > SMOKE_LIMITS["total_steps"]
        or len(config["E_values"]) > SMOKE_LIMITS["E_values"]
    )


def print_config_summary(config_path: Path, config: dict, explicit_config: bool) -> None:
    mode = "explicit config" if explicit_config else "default smoke config"
    print("Stiffness calibration runner")
    print("purpose: stiffness candidate check before full sweeps")
    print("note: this runner reports diagnostics only, not final physical conclusions")
    print(f"config: {config_path}")
    print(f"mode: {mode}")
    print("resolved config:")
    for key in CONFIG_KEYS:
        print(f"  {key}: {config[key]}")


def print_result_summary(result: dict) -> None:
    print("Stiffness calibration summary")
    print(f"tested_E_values: {sorted(result.get('results', {}).keys())}")
    print(f"threshold_crossed: {result.get('threshold_crossed')}")
    print(f"recommended_E: {result.get('recommended_E')}")
    print(f"recommended_G: {result.get('recommended_G')}")
    print(f"all_deformed: {result.get('all_deformed')}")
    print(f"all_ok: {result.get('all_ok')}")
    print("per-E summary:")
    for E in sorted(result.get("results", {})):
        row = result["results"][E]
        print(
            "  "
            f"E={float(E):.3e}, "
            f"status={row.get('status')}, "
            f"worst_metric_pct={row.get('worst_metric_pct')}, "
            f"deformation_exceeded={row.get('deformation_exceeded')}"
        )
    print("note: this calibration checks candidates only, not final physical conclusions")


def format_e_for_filename(E: float) -> str:
    text = f"{float(E):.0e}"
    mantissa, exponent = text.split("e")
    exponent_value = int(exponent)
    return f"{mantissa}e{exponent_value}"


def stiffness_timeseries_logger(original_logger):
    def log_with_stiffness_name(sim_result, filepath=None, torque_magnitude=None):
        params = sim_result.get("parameters", {})
        E = float(params.get("E", 0.0))
        n_elem = int(params.get("n_elem", 0))
        pitch = float(params.get("pitch", 0.0))
        radius = float(params.get("radius", 1.0))
        torque = float(
            torque_magnitude
            if torque_magnitude is not None
            else params.get("torque_magnitude", 0.0)
        )
        pr = pitch / radius if abs(radius) > 1e-30 else 0.0
        detail_name = (
            f"stiffness_E{format_e_for_filename(E)}_"
            f"N{n_elem}_pr{pr:.2f}_T{torque:.0e}.csv"
        )
        return original_logger(
            sim_result,
            filepath=detail_name,
            torque_magnitude=torque_magnitude,
        )

    return log_with_stiffness_name


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    explicit_config = args.config is not None
    config_path = args.config if explicit_config else DEFAULT_CONFIG
    config_path = config_path if config_path.is_absolute() else PROJECT_ROOT / config_path

    try:
        config = normalize_config(load_config(config_path))
    except Exception as exc:
        print(f"Failed to load stiffness calibration config: {exc}")
        return 1

    print_config_summary(config_path, config, explicit_config)

    if not explicit_config and exceeds_smoke_limits(config):
        print("Refusing to run: default stiffness calibration config exceeds smoke limits.")
        return 1
    if explicit_config and exceeds_smoke_limits(config):
        print("warning: explicit config exceeds the default smoke limits.")

    if args.dry_run:
        print("dry-run: calibration not executed")
        return 0

    from helical_propeller import simulator as simulator_module
    from helical_propeller.stiffness import stiffness_calibration

    original_logger = simulator_module.log_simulation_timeseries
    simulator_module.log_simulation_timeseries = stiffness_timeseries_logger(original_logger)
    try:
        result = stiffness_calibration(
            pitch=config["pitch"],
            radius=config["radius"],
            total_length=config["total_length"],
            body_length_ratio=config["body_length_ratio"],
            n_elem=config["n_elem"],
            torque_magnitude=config["torque_magnitude"],
            E_values=config["E_values"],
            nu=config["nu"],
            fluid_viscosity=config["fluid_viscosity"],
            density=config["density"],
            dt=config["dt"],
            total_steps=config["total_steps"],
            step_skip=config["step_skip"],
            deformation_threshold=config["deformation_threshold"],
        )
    finally:
        simulator_module.log_simulation_timeseries = original_logger
    print_result_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
