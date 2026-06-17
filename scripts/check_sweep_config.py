"""Preflight-check H1/H2 sweep YAML files without running simulations."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a sweep config before Colab execution.")
    parser.add_argument("config", type=Path, help="Path to configs/sweep_h1.yaml or sweep_h2.yaml.")
    parser.add_argument(
        "--kind",
        choices=["auto", "h1", "h2"],
        default="auto",
        help="Sweep type. Auto-detected from config keys by default.",
    )
    parser.add_argument(
        "--expected-pr",
        type=float,
        default=None,
        help="Optional expected P/R for H2 pitch/radius comparison.",
    )
    return parser.parse_args(argv)


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_config(path: Path) -> dict:
    resolved = _resolve(path)
    with resolved.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {resolved}")
    return config


def infer_kind(config: dict, requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    if "pr_values" in config:
        return "h1"
    if "body_ratio_values" in config:
        return "h2"
    return "unknown"


def _as_float(config: dict, key: str):
    try:
        return float(config[key])
    except (KeyError, TypeError, ValueError):
        return None


def _as_int(config: dict, key: str):
    try:
        return int(config[key])
    except (KeyError, TypeError, ValueError):
        return None


def inspect_config(config: dict, kind: str, expected_pr: float | None = None) -> tuple[list[str], list[str]]:
    summary: list[str] = []
    warnings: list[str] = []

    damping_value = config.get("damping_constant")
    if damping_value is None:
        warnings.append("damping_constant is not explicitly set in the sweep config.")
    summary.append(f"damping_constant: {damping_value}")

    total_steps = _as_int(config, "total_steps")
    step_skip = _as_int(config, "step_skip")
    n_elem = _as_int(config, "n_elem")
    torque = config.get("torque_magnitude")
    summary.extend([
        f"total_steps: {total_steps}",
        f"step_skip: {step_skip}",
        f"n_elem: {n_elem}",
        f"torque_magnitude: {torque}",
    ])

    if total_steps is None:
        warnings.append("total_steps is missing or not an integer.")
    elif total_steps < 240000:
        warnings.append("total_steps is below 240000; this may be short for final sweeps.")
    if step_skip is None:
        warnings.append("step_skip is missing or not an integer.")
    elif total_steps is not None:
        if step_skip <= 0 or step_skip > total_steps:
            warnings.append("step_skip must be positive and no larger than total_steps.")
        else:
            records = total_steps // step_skip + 1
            summary.append(f"approx_record_count: {records}")
            if records < 50:
                warnings.append("step_skip records fewer than 50 samples.")
            if records > 500:
                warnings.append("step_skip records more than 500 samples; raw CSV may be larger than needed.")
            if total_steps % step_skip != 0:
                warnings.append("total_steps is not divisible by step_skip.")
    if n_elem != 80:
        warnings.append(f"n_elem is {n_elem}; confirm this is intentional.")
    if torque is None:
        warnings.append("torque_magnitude is missing.")

    if kind == "h1":
        pr_values = [float(value) for value in config.get("pr_values", [])]
        summary.append(f"pr_values: {pr_values}")
        if 0.5 in pr_values:
            warnings.append("H1 pr_values includes 0.5; previous runs flagged low-P/R risk.")
        risky_low_pr = sorted(value for value in pr_values if value in (1.0, 1.5))
        if risky_low_pr:
            warnings.append(
                "H1 pr_values includes previous NaN/INF region values: "
                + ", ".join(str(value) for value in risky_low_pr)
            )
    elif kind == "h2":
        pitch = _as_float(config, "pitch")
        radius = _as_float(config, "radius")
        pr = pitch / radius if pitch is not None and radius not in (None, 0.0) else None
        summary.append(f"pitch: {pitch}")
        summary.append(f"radius: {radius}")
        summary.append(f"pitch_over_radius: {pr}")
        summary.append(f"body_ratio_values: {config.get('body_ratio_values')}")
        if expected_pr is not None and pr is not None and abs(pr - expected_pr) > 1e-12:
            warnings.append(f"H2 P/R={pr} does not match expected P/R={expected_pr}.")
    else:
        warnings.append("Could not infer sweep kind; expected pr_values or body_ratio_values.")

    output_keys = [key for key in ("output", "output_path", "output_name", "tag") if key in config]
    if output_keys:
        summary.append("output_identifier: " + ", ".join(f"{key}={config[key]}" for key in output_keys))
    else:
        warnings.append("No output path/tag key found; confirm how Colab will preserve summary CSVs.")

    return summary, warnings


def print_report(config_path: Path, kind: str, summary: list[str], warnings: list[str]) -> None:
    print("Sweep config preflight")
    print(f"config: {_resolve(config_path)}")
    print(f"kind: {kind}")
    print("summary:")
    for line in summary:
        print(f"  - {line}")
    if warnings:
        print("warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("warnings: none")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config)
    except Exception as exc:
        print(f"Failed to load sweep config: {exc}")
        return 1
    kind = infer_kind(config, args.kind)
    summary, warnings = inspect_config(config, kind, expected_pr=args.expected_pr)
    print_report(args.config, kind, summary, warnings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
