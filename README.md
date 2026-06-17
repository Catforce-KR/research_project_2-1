# Helical Propeller RFT

Low-Reynolds-number helical propeller simulation research using PyElastica and Resistive Force Theory (RFT).

The project compares a torque-driven analytical RFT approximation with a PyElastica/Cosserat-rod simulation using local RFT drag. Analytical predictions and simulation outputs should be reported separately.

## Research Questions

- H1: How does helix pitch/radius ratio (`P/R`) affect propulsion velocity and efficiency?
- H2: How does body-to-tail length ratio affect propulsion velocity, efficiency, and stability?
- Do the final simulation conditions remain in a low-Reynolds-number regime where RFT is a reasonable analytical comparison?

## Repository Layout

- `research_code.py`: compatibility wrapper for older `import research_code` usage.
- `src/helical_propeller/`: active package implementation.
- `scripts/`: runnable helpers for smoke runs, sweeps, analysis, audits, and figure generation.
- `configs/`: YAML configs for smoke checks, sweeps, damping checks, and diagnostics.
- `docs/`: model assumptions, architecture, experiment plan, validation notes, and final summaries.
- `data/helical_results/`: committed final/diagnostic CSV result data used by the report figures.
- `results/figures/`: committed report-ready PNG figures.
- `results/tables/`: committed summary CSV tables.
- `tests/`: lightweight pytest test suite.

## Environment

Use the Windows CPython virtual environment:

```bash
.venv\Scripts\python.exe
```

The confirmed project interpreter version is Python 3.13.3. Do not use bare `python`, `.venv\bin\python.exe`, or MSYS Python for project commands.

Install dependencies:

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PyElastica is listed as `pyelastica` in `requirements.txt`, while the code imports it as:

```python
import elastica as ea
```

## Quick Validation

Run the lightweight test suite:

```bash
.venv\Scripts\python.exe -m pytest tests
```

Run a short smoke simulation:

```bash
.venv\Scripts\python.exe scripts\run_single.py
```

The smoke run uses small `n_elem`, `total_steps`, and `step_skip` values. It is for import/execution validation, not final physical conclusions.

## Model Figures

Generate report-ready model geometry figures without time integration:

```bash
.venv\Scripts\python.exe scripts\generate_model_figures.py
```

Outputs are written to `results/figures/` and include perspective, side, top, director close-up, and multi-view physics-panel figures.

## Final Analysis Outputs

Regenerate final tables, figures, and summary text from completed CSV files:

```bash
.venv\Scripts\python.exe scripts\generate_final_analysis_outputs.py --h1 data\helical_results\processed\sweep_h1_summary_combined.csv --h2 data\helical_results\processed\sweep_h2_summary.csv --raw-dir data\helical_results\raw
```

If those short paths are not present locally, the script searches the committed `data/helical_results/` tree. It only reads existing CSV files and does not run simulations.

Audit Reynolds-number ranges for the final data:

```bash
.venv\Scripts\python.exe scripts\audit_low_reynolds_params.py --h1 data\helical_results\processed\sweep_h1_summary_combined.csv --h2 data\helical_results\processed\sweep_h2_summary.csv --config-h1 configs\sweep_h1.yaml --config-h2 configs\sweep_h2.yaml
```

Check final sweep configs without launching long runs:

```bash
.venv\Scripts\python.exe scripts\check_sweep_config.py configs\sweep_h1.yaml --kind h1
.venv\Scripts\python.exe scripts\check_sweep_config.py configs\sweep_h2.yaml --kind h2 --expected-pr 5.0
```

## Sweep Execution

Inspect guarded smoke configs:

```bash
.venv\Scripts\python.exe scripts\run_pilot_single.py --dry-run
.venv\Scripts\python.exe scripts\run_sweep_h1.py --dry-run
.venv\Scripts\python.exe scripts\run_sweep_h2.py --dry-run
.venv\Scripts\python.exe scripts\run_stiffness_calibration.py --dry-run
.venv\Scripts\python.exe scripts\run_n_convergence.py --dry-run
```

Run only guarded smoke checks:

```bash
.venv\Scripts\python.exe scripts\run_pilot_single.py
.venv\Scripts\python.exe scripts\run_sweep_h1.py
.venv\Scripts\python.exe scripts\run_sweep_h2.py
.venv\Scripts\python.exe scripts\run_stiffness_calibration.py
.venv\Scripts\python.exe scripts\run_n_convergence.py
```

Longer H1/H2 sweeps and calibration/convergence sweeps must be passed explicitly with `--config`; long configs require `--allow-long`.

## Final Report Data

Primary final summary CSVs:

- `data/helical_results/helical_results/h1_final_fixed/processed/sweep_h1_summary.csv`
- `data/helical_results/helical_results/h1_extended_high_pr/processed/sweep_h1_summary.csv`
- `data/helical_results/helical_results/h2_final_pr5/processed/sweep_h2_summary.csv`

Representative time-series CSVs used in report figures:

- `data/helical_results/helical_results/h2_final_pr5/raw/sim_N80_pr5.00_T1e-08.csv`
- `data/helical_results/helical_results/h2_final_pr5/raw/sim_N80_pr6.00_T1e-08.csv`
- `data/helical_results/helical_results/h2_final_pr5/raw/sweep_h2_br0.50_timeseries.csv`

Derived report outputs:

- Figures: `results/figures/`
- Tables: `results/tables/`
- Final summary: `docs/final_results_summary.md`
- Low-Re/RFT audit: `docs/low_reynolds_and_rft_audit.md`

## Result Summary

- H1 speed optimum in the final data: `P/R=6.0`.
- H1 power-efficiency optimum: `P/R=5.0`.
- H2 uses representative `P/R=5.0`.
- H2 optimum in the final data: `body_length_ratio=0.5`.
- The balanced final design candidate is `P/R=5.0`, `body_length_ratio=0.5`.

## Repository Hygiene

- `.env` and `.env.*` files are ignored and should not be committed.
- API keys, secrets, passwords, and personal machine paths should not be committed.
- Python caches, pytest caches, logs, temp files, backup files, and zip bundles are ignored.
- Generated result files are normally ignored by pattern, but the final report figures/tables in this repository were committed intentionally for report reproducibility.

## Notes

- This project does not solve full Navier-Stokes/CFD.
- RFT is a local drag approximation under low-Reynolds-number assumptions.
- `damping_constant` is a PyElastica numerical damping/stabilization setting, not the physical fluid viscosity.
- `fluid_viscosity` is the viscosity used by the RFT force model and Reynolds-number audit.
