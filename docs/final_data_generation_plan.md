# Final Data Generation Plan

This workflow assumes long simulations run in Colab. Codex only prepares configs, checks inputs, and analyzes returned CSV files.

## 1. Decide Damping

1. Run damping validation in Colab with the chosen damping config.
2. Bring the summary CSV back to this repository, usually as `data/processed/h1_pr3_damping_check_summary.csv`.
3. Analyze it locally:

```powershell
.venv\Scripts\python.exe scripts\analyze_damping_results.py data\processed\h1_pr3_damping_check_summary.csv
```

Use only rows with `invalid_result=False`, `stiffness_status=OK`, and `deformation_exceeded=False`. Prefer rows where `omega_theory_over_omega_sim` is closest to 1, `V_theory_over_V_sim` is smaller, and `damping_torque_to_applied_ratio` is not dominating the applied torque. If multiple low-damping rows are stable, keep one primary damping value and at most one backup.

## 2. Apply Damping To H1

After choosing the damping value, record it in the H1 sweep configuration or in the Colab execution cell that calls the sweep. The current final-candidate setting is `damping_constant=1.0e-5`, and the local H1/H2 runners now pass that config value through to `run_simulation`. Before running H1, inspect the config:

```powershell
.venv\Scripts\python.exe scripts\check_sweep_config.py configs\sweep_h1.yaml --kind h1
```

H1 is run first because the pitch/radius ratio controls the helical tail geometry and propulsion trend. H2 should not be interpreted until H1 identifies a representative P/R.

Important: if a Colab copy of the runner is used, confirm that its code also passes `damping_constant` into `run_simulation`.

## 3. Analyze H1 Results

Run the H1 full sweep in Colab only. Copy the returned summary CSV to `data/processed/`, then analyze:

```powershell
.venv\Scripts\python.exe scripts\analyze_sweep_results.py data\processed\sweep_h1_summary.csv --kind h1
```

Review invalid/failure rows, stiffness/deformation rows, `V_sim`, `Eta_power`, `Eta_slip`, `omega_sim`, steady-state status, and error ratios. Pick one or two P/R candidates, not a dense refined sweep, unless the returned results are ambiguous.

## 4. Fix H2 Geometry

Use the selected H1 P/R to set H2 geometry:

```text
pitch = selected_P_over_R * radius
```

For example, with `radius=0.01` and `P/R=3.0`, set `pitch=0.03`. Inspect H2 before Colab execution:

```powershell
.venv\Scripts\python.exe scripts\check_sweep_config.py configs\sweep_h2.yaml --kind h2 --expected-pr 3.0
```

## 5. Analyze H2 Results

Run H2 in Colab only. Copy the returned summary CSV, then analyze:

```powershell
.venv\Scripts\python.exe scripts\analyze_sweep_results.py data\processed\sweep_h2_summary.csv --kind h2
```

Review the body-length-ratio table, invalid/failure rows, stiffness/deformation rows, `V_sim`, `Eta_power`, `Eta_slip`, and `omega_sim`. Select the body ratio from valid rows only.

## Execution Boundary

Codex must not execute H1/H2 full sweeps, 480000-step runs, damping validation simulations, or convergence sweeps. Colab runs simulations; Codex analyzes returned CSVs.
