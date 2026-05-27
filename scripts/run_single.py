"""Run a short smoke simulation through the package implementation."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def main() -> int:
    try:
        import helical_propeller.simulator as simulator
    except ModuleNotFoundError as exc:
        missing = exc.name or "unknown"
        if missing == "elastica":
            print(
                "Import failed: PyElastica is not installed or is not importable as "
                "'elastica'. Install dependencies with "
                "`.venv\\Scripts\\python.exe -m pip install -r requirements.txt`."
            )
        else:
            print(f"Import failed: missing Python module '{missing}'.")
        return 1
    except Exception as exc:
        print(f"Import failed while loading helical_propeller: {exc}")
        return 1

    simulator.log_simulation_timeseries = lambda *args, **kwargs: None

    smoke_params = {
        "n_elem": 6,
        "pitch": 0.02,
        "radius": 0.01,
        "total_length": 0.1,
        "body_length_ratio": 0.5,
        "density": 1000.0,
        "E": 1e7,
        "nu": 0.5,
        "fluid_viscosity": 0.1,
        "dt": 1e-5,
        "total_steps": 5,
        "step_skip": 1,
        "torque_magnitude": 1e-8,
    }

    captured_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured_stdout):
            result = simulator.run_simulation(**smoke_params)
    except Exception as exc:
        print(f"Smoke simulation failed: {exc}")
        return 1

    analytical = result.get("analytical")
    stiffness = result.get("stiffness")

    print("Smoke simulation summary")
    print(f"final_time: {result.get('final_time')}")
    if analytical:
        print(f"analytical.V_sim: {analytical.get('V_sim')}")
        print(f"analytical.V_theory: {analytical.get('V_theory')}")
        print(f"analytical.omega_sim: {analytical.get('omega_sim')}")
        print(f"analytical.omega_theory: {analytical.get('omega_theory')}")
        print(f"analytical.theory_mode: {analytical.get('theory_mode')}")
        print(f"analytical.pct_error_vs_theory: {analytical.get('pct_error_vs_theory')}")
        print(f"analytical.pct_error_vs_sim: {analytical.get('pct_error_vs_sim')}")
        print(f"analytical.error_status: {analytical.get('error_status')}")
        print(f"analytical.steady_state_status: {analytical.get('steady_state_status')}")
    else:
        print("analytical: unavailable")

    print(f"failure_reason: {result.get('failure_reason')}")
    print(f"invalid_result: {result.get('invalid_result')}")
    if stiffness:
        print(f"stiffness.status: {stiffness.get('status')}")
        print(f"stiffness.deformation_exceeded: {stiffness.get('deformation_exceeded')}")
    else:
        print("stiffness: unavailable")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
