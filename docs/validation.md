# Validation

## Analytical Comparison

For a completed simulation, compare the measured or estimated propulsion velocity with the analytical RFT prediction. Report analytical prediction and PyElastica simulation result separately.

Track at minimum:

- `V_theory`
- simulated propulsion velocity
- `absolute_error`, `signed_error`, `pct_error_vs_theory`, and `pct_error_vs_sim` where meaningful
- `error_status`, including near-zero and nonfinite handling
- steady-state window metrics and `steady_state_status`
- `failure_reason` and `invalid_result`
- `omega_sim`, `omega_theory`, `omega_source`, and `theory_mode`
- torque-driven resistance terms `A`, `B`, `D`, `A_total`, `D_total` and body drag terms
- final-window `force_residual_norm`, `torque_residual_norm`, and inferred `effective_rotational_resistance` before changing physical coefficients
- `C_t`
- `C_n`

## Smoke Test

The smoke test should verify imports, torque-driven analytical helper behavior, inertial-frame angular-velocity collection, steady-state classification, invalid-result classification, and CSV field persistence. It should not run a long simulation.

Default automated validation command:

- `.venv\Scripts\python.exe -m pytest tests`

Optional manual smoke runner:

- `.venv\Scripts\python.exe scripts\run_single.py`

The manual smoke runner uses very small simulation parameters and is not a substitute for full validation.

## Python Environment

- The project validation Python is `.venv\Scripts\python.exe`.
- Access to the Windows CPython base interpreter referenced by `.venv\Scripts\python.exe` is permanently allowed for this project.
- Run pytest validation with `.venv\Scripts\python.exe -m pytest tests`.
- Do not use bare `python`.
- Do not use `.venv\bin\python.exe`.
- Do not use `C:\msys64\ucrt64\bin\python.exe`.
- If `.venv\Scripts\python.exe` is missing, report an environment problem instead of falling back to MSYS Python.
- Do not route execution through MSYS Python.

## Stiffness Check

The current stiffness check monitors deformation metrics from simulation output, including position and curvature/shear data where available. If the stiffness check logic or thresholds change, update `docs/model_assumptions.md`.

## Future Test Plan

- Add unit tests for configuration loading after modularization.
- Add analytical formula regression tests with fixed parameters.
- Add path tests to ensure generated CSV and figure outputs go to the documented directories.
- Add short simulation regression tests only when runtime is acceptable in CI.
- Do not run long parameter sweeps, stiffness calibration sweeps, or convergence sweeps unless explicitly requested.
