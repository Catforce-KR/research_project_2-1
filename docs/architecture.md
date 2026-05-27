# Architecture

## Current Structure

The active simulation implementation now lives under `src/helical_propeller/`. The root `research_code.py` file is retained as a compatibility wrapper so existing `import research_code` users continue to work.

The original pre-modularization script is backed up as `research_code_legacy.py`.

## Module Layout

The package originated from a behavior-preserving extraction. The analytical layer now also contains an explicit torque-driven RFT approximation aligned with the configured endpoint-torque simulation.

Current modules:

- `geometry.py`: body-tail geometry generation, helix coordinates, directors, rest lengths.
- `forces.py`: PyElastica RFT forcing and endpoint torque classes.
- `callbacks.py`: PyElastica callback data collector, including inertial-axis omega, torque projection, and damping-equivalent diagnostic histories.
- `theory.py`: torque-driven analytical RFT resistance model, body drag approximation, and analytical/simulation torque/damping diagnostics.
- `analysis_metrics.py`: error, steady-state, and invalid-result post-processing shared by simulations and sweeps.
- `simulator.py`: PyElastica system assembly and single-run execution.
- `stiffness.py`: stiffness and deformation checks.
- `efficiency.py`: RFT useful-power and slip metrics using simulation angular velocity when available.
- `sweeps.py`: H1 pitch/radius and H2 body-to-tail sweep orchestration.
- `logging_utils.py`: CSV logging and result path handling.
- `plotting.py`: reserved for shared plotting helpers.
- `cli.py`: compatibility command-line modes previously hosted in `research_code.py`.

## Current Entry Points

- `research_code.py`: compatibility wrapper that re-exports the package API.
- `src/helical_propeller/simulator.py`: `SpiralRodSimulator` and `run_simulation`.
- `scripts/run_single.py`: short smoke runner that imports `helical_propeller.simulator.run_simulation` with small parameters.

## Execution Environment

- Project commands must use the Windows CPython venv interpreter at `.venv\Scripts\python.exe`.
- Do not use bare `python`, `.venv\bin\python.exe`, or `C:\msys64\ucrt64\bin\python.exe`.
- If `.venv\Scripts\python.exe` is unavailable, treat it as an environment problem instead of routing execution through MSYS Python.
- The default validation commands are `.venv\Scripts\python.exe -m pytest tests` and `.venv\Scripts\python.exe scripts\run_single.py`.

## Dependency Direction

- `simulator` depends on `geometry`, `forces`, `callbacks`, `theory`, `analysis_metrics`, `efficiency`, `stiffness`, and `logging_utils`.
- `sweeps` depends on `simulator`, `analysis_metrics`, `efficiency`, and `logging_utils`.
- `stiffness_calibration` imports `run_simulation` inside the function to avoid a module-level circular import.
- `efficiency_curve_analysis` imports `parameter_sweep_h1` inside the function to avoid a module-level circular import.
- `geometry`, `theory`, `analysis_metrics`, `efficiency`, and `stiffness_check` remain usable without importing `simulator`.

## Boundary Rules

- Do not change RFT coefficients or analytical formulas without updating `docs/model_assumptions.md`.
- Do not mix analytical prediction and PyElastica simulation result in summaries.
- Keep long sweeps out of smoke scripts and tests.
- Do not run long parameter sweeps, stiffness calibration sweeps, or convergence sweeps unless explicitly requested.
