"""Run a guarded n_elem convergence check before full sweeps."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "n_convergence_smoke.yaml"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


CONFIG_KEYS = [
    "pitch",
    "radius",
    "total_length",
    "body_length_ratio",
    "n_values",
    "torque_magnitude",
    "dt",
    "total_steps",
    "step_skip",
    "fluid_viscosity",
    "density",
    "E",
    "nu",
]

SMOKE_LIMITS = {
    "n_values": 3,
    "max_n_elem": 80,
    "total_steps": 1000,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a guarded n_elem convergence check before full sweeps."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML config path. Defaults to configs/n_convergence_smoke.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved config without running convergence.",
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
    normalized["n_values"] = [int(value) for value in normalized["n_values"]]
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


def exceeds_smoke_limits(config: dict) -> bool:
    return (
        len(config["n_values"]) > SMOKE_LIMITS["n_values"]
        or max(config["n_values"]) > SMOKE_LIMITS["max_n_elem"]
        or config["total_steps"] > SMOKE_LIMITS["total_steps"]
    )


def print_config_summary(config_path: Path, config: dict, explicit_config: bool) -> None:
    mode = "explicit config" if explicit_config else "default smoke config"
    print("n_elem convergence runner")
    print("purpose: n_elem candidate check before full sweeps")
    print("note: this runner reports diagnostics only, not final physical conclusions")
    print(f"config: {config_path}")
    print(f"mode: {mode}")
    print("resolved config:")
    for key in CONFIG_KEYS:
        print(f"  {key}: {config[key]}")
    if min(config["n_values"]) < 20:
        print("warning: n_elem values below 20 are considered too low for this geometry.")


def _analysis_summary(row: dict) -> dict:
    sim_result = row.get("sim_result") or {}
    analytical = sim_result.get("analytical") or row.get("analytical") or {}
    stiffness = sim_result.get("stiffness") or row.get("stiffness") or {}
    return {
        "V_sim": row.get("V_sim", analytical.get("V_sim")),
        "V_theory": row.get("V_theory", analytical.get("V_theory")),
        "omega_sim": row.get("omega_sim", analytical.get("omega_sim")),
        "omega_theory": row.get("omega_theory", analytical.get("omega_theory")),
        "theory_mode": row.get("theory_mode", analytical.get("theory_mode")),
        "pct_error_vs_theory": row.get("pct_error_vs_theory", analytical.get("pct_error_vs_theory")),
        "pct_error_vs_sim": row.get("pct_error_vs_sim", analytical.get("pct_error_vs_sim")),
        "error_status": row.get("error_status", analytical.get("error_status")),
        "steady_state_status": row.get("steady_state_status", analytical.get("steady_state_status")),
        "failure_reason": row.get("failure_reason"),
        "invalid_result": row.get("invalid_result"),
        "Eta_slip": row.get("Eta_slip"),
        "Eta_power": row.get("Eta_power"),
        "stiffness_status": row.get("stiffness_status", stiffness.get("status")),
        "deformation_exceeded": row.get(
            "deformation_exceeded",
            stiffness.get("deformation_exceeded"),
        ),
        "worst_metric_pct": row.get(
            "worst_metric_pct",
            stiffness.get("worst_metric_pct"),
        ),
    }


def print_result_summary(result: dict) -> None:
    results = result.get("results", {})
    convergence_achieved = result.get("convergence_achieved")
    print("n_elem convergence summary")
    print(f"tested_n_values: {sorted(results.keys())}")
    print(f"convergence_achieved: {convergence_achieved}")
    print(f"convergence_error_pct: {result.get('convergence_error_pct')}")
    if convergence_achieved:
        print(f"recommended_n_elem: {result.get('recommended_n')}")
    else:
        print("recommended_n_elem: not determined")
        if results:
            print(f"candidate_max_n_elem: {max(results)}")
    print("per-n summary:")
    for n_elem in sorted(results):
        row = results[n_elem]
        extra = _analysis_summary(row)
        print(
            "  "
            f"n_elem={int(n_elem)}, "
            f"status={row.get('status')}, "
            f"vz_final_mean={row.get('vz_final_mean')}, "
            f"vz_com_avg={row.get('vz_com_avg')}, "
            f"V_sim={extra['V_sim']}, "
            f"V_theory={extra['V_theory']}, "
            f"omega_sim={extra['omega_sim']}, "
            f"omega_theory={extra['omega_theory']}, "
            f"theory_mode={extra['theory_mode']}, "
            f"pct_error_vs_theory={extra['pct_error_vs_theory']}, "
            f"pct_error_vs_sim={extra['pct_error_vs_sim']}, "
            f"error_status={extra['error_status']}, "
            f"steady_state_status={extra['steady_state_status']}, "
            f"failure_reason={extra['failure_reason']}, "
            f"invalid_result={extra['invalid_result']}, "
            f"Eta_slip={extra['Eta_slip']}, "
            f"Eta_power={extra['Eta_power']}, "
            f"stiffness_status={extra['stiffness_status']}, "
            f"deformation_exceeded={extra['deformation_exceeded']}, "
            f"worst_metric_pct={extra['worst_metric_pct']}"
        )
    print("note: this convergence check reports candidates only, not final physical conclusions")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    explicit_config = args.config is not None
    config_path = args.config if explicit_config else DEFAULT_CONFIG
    config_path = config_path if config_path.is_absolute() else PROJECT_ROOT / config_path

    try:
        config = normalize_config(load_config(config_path))
    except Exception as exc:
        print(f"Failed to load n_elem convergence config: {exc}")
        return 1

    print_config_summary(config_path, config, explicit_config)

    if not explicit_config and exceeds_smoke_limits(config):
        print("Refusing to run: default n_elem convergence config exceeds smoke limits.")
        return 1
    if explicit_config and exceeds_smoke_limits(config):
        print("warning: explicit config exceeds the default smoke limits.")

    if args.dry_run:
        print("dry-run: convergence not executed")
        return 0

    from helical_propeller.sweeps import n_convergence_test

    result = n_convergence_test(
        pitch=config["pitch"],
        radius=config["radius"],
        total_length=config["total_length"],
        body_length_ratio=config["body_length_ratio"],
        n_values=config["n_values"],
        torque_magnitude=config["torque_magnitude"],
        dt=config["dt"],
        total_steps=config["total_steps"],
        step_skip=config["step_skip"],
        fluid_viscosity=config["fluid_viscosity"],
        density=config["density"],
        E=config["E"],
        nu=config["nu"],
    )
    print_result_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
