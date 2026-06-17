# Project Structure For Research Plan

## 1. Project Overview

This project studies a low-Reynolds-number helical propeller / micro-swimmer with a PyElastica Cosserat-rod simulation and a torque-driven Resistive Force Theory (RFT) analytical comparison.

The research plan is organized around two hypotheses:

- H1: propulsion performance changes with helix pitch/radius ratio, `P/R`.
- H2: propulsion performance changes with body length ratio.

The simulation does not solve full computational fluid dynamics. Instead, PyElastica integrates the elastic rod dynamics, while RFT supplies local viscous drag forcing and an analytical comparison model.

## 2. Theory Structure

### Navier-Stokes And RFT

The Navier-Stokes equations are the general governing equations for fluid motion. In low-Reynolds-number swimming, viscous forces dominate inertial forces. Under this regime, the full fluid problem can often be approximated with local drag laws instead of full CFD.

RFT is used here as that low-Reynolds-number approximation. It decomposes local rod velocity into tangential and normal components and applies separate drag coefficients. This makes it suitable for a helical micro-swimmer study where the goal is to compare geometry trends, not to resolve the full surrounding flow field.

The limitation is important: RFT ignores long-range hydrodynamic interactions, wall effects, detailed head/body flow, and many nonlocal fluid effects. Therefore, agreement between the PyElastica simulation and analytical RFT result is a consistency check within the simplified model, not a validation of RFT against full Navier-Stokes physics.

### PyElastica Simulation vs Analytical RFT

The PyElastica simulation is a deformable Cosserat-rod time integration with endpoint torque, damping, stiffness, and RFT external forcing. Its outputs include `V_sim`, `omega_sim`, deformation metrics, time histories, and invalid-result flags.

The analytical RFT comparison is a rigid, torque-driven resistance-balance model. It computes resistance coefficients and solves a force-free and torque-driven system for `V_theory` and `omega_theory`:

```text
F_z = -A_total * V + B * omega = 0
T_z =  B * V - D_total * omega + applied_torque = 0
```

The comparison should be described as "torque-driven RFT analytical approximation vs RFT-forced PyElastica rod simulation."

### Damping Influence

Numerical damping is not part of the analytical RFT resistance model. Earlier diagnostics showed that damping can explain a large share of the torque residual. Therefore, damping must be reported as a numerical setting that affects theory/simulation mismatch. The current candidate for final experiments is `damping_constant=1.0e-5`, subject to the user's Colab medium-validation result.

## 3. Code Structure

| File | Research-plan role |
|---|---|
| `src/helical_propeller/geometry.py` | Builds the body-tail rod geometry. Tracks `pitch`, `radius`, `total_length`, `body_length_ratio`, and `n_elem`, which are the main H1/H2 design variables. |
| `src/helical_propeller/forces.py` | Applies RFT drag forcing and endpoint torque. This is the simulation-side low-Reynolds-number force model. |
| `src/helical_propeller/theory.py` | Implements RFT coefficients, helical resistance matrix, body drag approximation, torque-driven solution, and torque/damping diagnostics. This is the analytical comparison layer. |
| `src/helical_propeller/simulator.py` | Assembles the PyElastica system, geometry, RFT forcing, damping, endpoint torque, callbacks, analytical comparison, efficiency, stiffness, and CSV logging for a single run. |
| `src/helical_propeller/stiffness.py` | Checks deformation and stiffness validity. Its output supports excluding physically unreliable runs. |
| `src/helical_propeller/efficiency.py` | Computes slip efficiency and RFT useful-power efficiency from simulation outputs. These are H1/H2 performance metrics. |
| `src/helical_propeller/analysis_metrics.py` | Computes error metrics, steady-state diagnostics, invalid-result classification, and flattened summary fields. This supports post-experiment filtering. |

## 4. Execution Structure

| File | Experiment role |
|---|---|
| `configs/sweep_h1.yaml` | H1 sweep configuration for P/R variation. It now records `damping_constant=1.0e-5`, `total_steps=240000`, `step_skip=2400`, and the safer `P/R >= 2.0` range. |
| `configs/sweep_h2.yaml` | H2 sweep configuration for body length ratio variation. It records the same damping and duration settings, but its `pitch/radius` should still be updated after H1 selects the representative P/R. |
| `configs/h1_pr3_damping_check.yaml` | P/R=3.0 damping comparison configuration. Used before final H1/H2 data generation. |
| `scripts/run_sweep_h1.py` | Guarded H1 runner. It can dry-run configs and requires explicit permission for larger configs. |
| `scripts/run_sweep_h2.py` | Guarded H2 runner. It can dry-run configs and requires explicit permission for larger configs. |
| `scripts/run_damping_check.py` | Damping comparison runner. For final workflow, Colab executes simulations and Codex analyzes returned CSVs. |
| `scripts/check_sweep_config.py` | Preflight checker. It reads sweep YAML files and warns about missing damping, short duration, risky P/R values, and H2 P/R mismatch. It does not run simulations. |
| `scripts/analyze_damping_results.py` | Analyzes damping summary CSVs and recommends a primary and secondary damping candidate. It does not run simulations. |
| `scripts/analyze_sweep_results.py` | Analyzes H1/H2 summary CSVs, lists invalid/stiffness problem rows, and ranks valid candidate conditions. |

## 5. Data Flow

1. Set config values for damping, H1, or H2.
2. Run simulation in Colab only for final experiments.
3. Save raw time-series CSV files under `data/raw/`.
4. Save processed summary CSV files under `data/processed/`.
5. Analyze damping summaries with `scripts/analyze_damping_results.py`.
6. Choose final damping value, currently expected to be near `1.0e-5` if medium validation confirms stability.
7. Run H1 in Colab and analyze `sweep_h1_summary.csv` with `scripts/analyze_sweep_results.py`.
8. Choose H1 P/R candidate and set H2 `pitch = selected_P_over_R * radius`.
9. Run H2 in Colab and analyze `sweep_h2_summary.csv`.
10. Interpret final results using velocity, efficiency, stiffness, invalid-result status, steady-state status, damping influence, and RFT assumptions.

## 6. Research Plan Coverage Table

| Research-plan requirement | Current status | Related files | Needed supplement |
|---|---|---|---|
| H1 P/R performance analysis | Satisfied | `configs/sweep_h1.yaml`, `scripts/run_sweep_h1.py`, `scripts/analyze_sweep_results.py`, `src/helical_propeller/sweeps.py` | Confirm Colab copy uses the updated runner that passes `damping_constant`. |
| H2 body ratio performance analysis | Satisfied | `configs/sweep_h2.yaml`, `scripts/run_sweep_h2.py`, `scripts/analyze_sweep_results.py`, `src/helical_propeller/sweeps.py` | Update `pitch/radius` after H1 selects final P/R. |
| RFT theoretical background | Satisfied | `docs/model_assumptions.md`, `src/helical_propeller/theory.py`, `src/helical_propeller/forces.py` | Research plan should explicitly state RFT assumptions and limitations. |
| Navier-Stokes vs RFT explanation | Partially satisfied | `docs/model_assumptions.md`, this document | Existing docs mention low-Re/RFT, but the research plan should add a clear paragraph comparing full Navier-Stokes and RFT. |
| PyElastica simulation method | Satisfied | `docs/architecture.md`, `src/helical_propeller/simulator.py`, `src/helical_propeller/geometry.py` | Include a diagram or short method paragraph in the research plan. |
| Torque-driven analytical comparison | Satisfied | `docs/model_assumptions.md`, `src/helical_propeller/theory.py` | Explain that `V_theory` and `omega_theory` are analytical RFT outputs, not CFD outputs. |
| Damping control and interpretation | Satisfied | `src/helical_propeller/simulator.py`, `src/helical_propeller/sweeps.py`, `configs/sweep_h1.yaml`, `configs/sweep_h2.yaml`, `scripts/analyze_damping_results.py` | Confirm any Colab-side copied scripts match the local runner changes. |
| Stiffness/deformation filtering | Satisfied | `src/helical_propeller/stiffness.py`, `analysis_metrics.py`, `analyze_sweep_results.py` | State exclusion criteria in the research plan. |
| Data storage structure | Satisfied | `README.md`, `docs/experiment_plan.md`, `src/helical_propeller/logging_utils.py` | Keep raw and summary CSV filenames traceable after Colab runs. |
| Post-experiment analysis tools | Satisfied | `scripts/analyze_damping_results.py`, `scripts/analyze_sweep_results.py`, `scripts/check_sweep_config.py` | Use returned Colab CSVs; do not re-run long simulations locally. |
| Automated validation | Satisfied | `tests/`, `docs/validation.md` | Tests are lightweight by design and do not replace final simulation validation. |
| Final Colab workflow | Satisfied | `docs/final_data_generation_plan.md` | Keep Colab notebooks/cells consistent with local config values. |

## 7. Remaining Supplements

### Before Final Experiments

- Confirm that final Colab execution uses the updated runner path with `damping_constant=1.0e-5`.
- Confirm H1/H2 final `total_steps=240000` and `step_skip=2400` are acceptable for final interpretation.
- Confirm H2 `pitch/radius` matches the selected H1 P/R.
- Preserve summary CSVs with distinct names if multiple attempts are run.

### After Final Experiments

- Exclude rows with `invalid_result=True`, non-OK stiffness, or `deformation_exceeded=True`.
- Report transient rows as diagnostic, not final physical conclusions.
- Compare `V_sim`, `omega_sim`, `V_theory/V_sim`, `omega_theory/omega_sim`, `Eta_power`, and `Eta_slip`.
- Interpret damping influence and RFT limitations together.

### Limitations To Explain

- RFT is a local drag approximation, not a full Navier-Stokes solver.
- The body drag model is approximate and centerline-based.
- Numerical damping affects the torque balance and theory/simulation mismatch.
- The PyElastica rod is deformable, while the analytical RFT model is a simplified rigid resistance balance.
- Efficiency metrics are model-based indicators, not complete hydrodynamic efficiency.
