# Helical Propeller RFT

Low-Reynolds-number helical propeller simulation research using PyElastica and Resistive Force Theory (RFT).

## Research Question

How do helix pitch/radius ratio and body-to-tail length ratio affect propulsion velocity, efficiency, and structural stability in a low-Reynolds-number helical swimmer model?

The project compares analytical RFT predictions with PyElastica / Cosserat rod simulation results. Analytical predictions and simulation outputs should always be reported separately.

## Current Status

- The active implementation has been moved into `src/helical_propeller/`.
- `research_code.py` remains at the repository root as a compatibility wrapper for existing imports and script usage.
- `research_code_legacy.py` preserves the pre-modularization single-file implementation.
- `scripts/run_single.py` is a short smoke runner only. It is not intended for production-quality parameter studies.
- H1/H2 sweep helpers are available in `helical_propeller.sweeps`, but long parameter sweeps, stiffness calibration sweeps, and convergence sweeps should only be run when explicitly requested.
- Result summaries now report theory- and simulation-referenced errors, steady-state diagnostics, and invalid-result reasons for analysis filtering.
- `V_theory` now uses a torque-driven RFT resistance balance with approximate body translation and rotation drag, matching the endpoint-torque experiment type more closely than the former prescribed-omega comparison.

## Installation

This project uses a Windows CPython virtual environment only. The expected interpreter is:

```bash
.venv\Scripts\python.exe
```

The current confirmed interpreter version is Python 3.13.3. Do not use bare `python`, `.venv\bin\python.exe`, or `C:\msys64\ucrt64\bin\python.exe` for this project. If `.venv\Scripts\python.exe` is missing, report it as an environment problem instead of falling back to MSYS Python.

Install dependencies through the Windows CPython venv:

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PyElastica may have a different package name and import name depending on the installed version. This repository lists `pyelastica` in `requirements.txt`, while the current code imports it as:

```python
import elastica as ea
```

## Single Smoke Simulation

Run a short smoke simulation:

```bash
.venv\Scripts\python.exe scripts\run_single.py
```

This uses small `n_elem`, `total_steps`, and `step_skip` values to avoid long simulation runs. It prints a compact summary including velocities, both percentage-error references, steady-state status, invalid-result status, and stiffness check status.

The smoke script imports `run_simulation` from:

```python
from helical_propeller.simulator import run_simulation
```

## Smoke Sweeps

Inspect guarded smoke sweep configs without running simulations:

```bash
.venv\Scripts\python.exe scripts\run_pilot_single.py --dry-run
.venv\Scripts\python.exe scripts\run_sweep_h1.py --dry-run
.venv\Scripts\python.exe scripts\run_sweep_h2.py --dry-run
.venv\Scripts\python.exe scripts\run_stiffness_calibration.py --dry-run
.venv\Scripts\python.exe scripts\run_n_convergence.py --dry-run
```

Run only the guarded pilot/smoke checks:

```bash
.venv\Scripts\python.exe scripts\run_pilot_single.py
.venv\Scripts\python.exe scripts\run_sweep_h1.py
.venv\Scripts\python.exe scripts\run_sweep_h2.py
.venv\Scripts\python.exe scripts\run_stiffness_calibration.py
.venv\Scripts\python.exe scripts\run_n_convergence.py
```

Longer sweep configs must be passed explicitly with `--config`.
Actual coarse sweep configs such as `configs/sweep_h1.yaml` and `configs/sweep_h2.yaml` require `--allow-long` to execute. They use `n_elem=80`, `E=1e7`, and `total_steps=10000` as conservative first-pass settings, not final validated constants.

## Results And Data

- Single simulation time-series CSV: `data/raw/`
- Sweep detail/time-series CSV: `data/raw/`
- Sweep summary CSV: `data/processed/`
- Other processed generated CSV: `data/processed/`
- Figures: `results/figures/`
- Summary tables: `results/tables/`
- Reports: `results/reports/`

Large generated result files should not be committed unless explicitly requested.

Sweep summaries preserve the legacy `pct_error` column as the simulation-referenced alias and add torque-driven theory terms, simulated/theoretical angular velocity, efficiency source/model fields, error/steady-state status fields, and `failure_reason`/`invalid_result` for analysis filtering.

## Tests

Run the lightweight tests:

```bash
.venv\Scripts\python.exe -m pytest tests
```

These tests do not run long simulations or parameter sweeps. The default validation commands are:

```bash
.venv\Scripts\python.exe -m pytest tests
.venv\Scripts\python.exe scripts\run_single.py
```
