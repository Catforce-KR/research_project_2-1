"""Run the three-case H1 theory check without overwriting earlier H1 outputs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
CONFIG_PATH = PROJECT_ROOT / "configs" / "sweep_h1_theory_check.yaml"
BASE_OUTPUT_NAME = "sweep_h1_theory_check"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


def _detail_logger(original_logger, output_prefix):
    def log_theory_check_timeseries(sim_result, filepath=None, torque_magnitude=None):
        params = sim_result["parameters"]
        detail_name = (
            f"{output_prefix}_N{params['n_elem']}_"
            f"pr{params['pitch'] / params['radius']:.2f}_"
            f"T{params['torque_magnitude']:.0e}.csv"
        )
        return original_logger(
            sim_result,
            filepath=detail_name,
            torque_magnitude=torque_magnitude,
        )

    return log_theory_check_timeseries


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tag",
        default="",
        help="Optional suffix for preserving separate theory-check outputs.",
    )
    args = parser.parse_args()
    if args.tag and re.fullmatch(r"[A-Za-z0-9_-]+", args.tag) is None:
        parser.error("--tag may contain only letters, numbers, underscores, and hyphens")
    return args


def main() -> int:
    args = _parse_args()
    config = _load_config()
    output_prefix = BASE_OUTPUT_NAME
    if args.tag:
        output_prefix = f"{BASE_OUTPUT_NAME}_{args.tag}"
    summary_name = f"{output_prefix}_summary.csv"
    from helical_propeller import simulator as simulator_module
    from helical_propeller import sweeps as sweeps_module
    from helical_propeller.logging_utils import log_sweep_summary

    original_timeseries_logger = simulator_module.log_simulation_timeseries
    original_summary_logger = sweeps_module.log_sweep_summary
    simulator_module.log_simulation_timeseries = _detail_logger(
        original_timeseries_logger,
        output_prefix,
    )
    sweeps_module.log_sweep_summary = (
        lambda results, filepath=None, sweep_type="h1": log_sweep_summary(
            results,
            filepath=summary_name,
            sweep_type=sweep_type,
        )
    )
    try:
        sweeps_module.parameter_sweep_h1(
            radius=float(config["radius"]),
            total_length=float(config["total_length"]),
            n_elem=int(config["n_elem"]),
            pr_values=[float(value) for value in config["pr_values"]],
            torque_magnitude=float(config["torque_magnitude"]),
            dt=float(config["dt"]),
            total_steps=int(config["total_steps"]),
            step_skip=int(config["step_skip"]),
            fluid_viscosity=float(config["fluid_viscosity"]),
            density=float(config["density"]),
            E=float(config["E"]),
            nu=float(config["nu"]),
            body_length_ratio=float(config["body_length_ratio"]),
        )
    finally:
        simulator_module.log_simulation_timeseries = original_timeseries_logger
        sweeps_module.log_sweep_summary = original_summary_logger
    print(f"theory_check_summary: data/processed/{summary_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
