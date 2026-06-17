# Research Plan Gap Check

## Satisfied Items

- H1 can analyze propulsion and efficiency as a function of pitch/radius ratio through `configs/sweep_h1.yaml`, `scripts/run_sweep_h1.py`, and `scripts/analyze_sweep_results.py`.
- H2 can analyze propulsion and efficiency as a function of body length ratio through `configs/sweep_h2.yaml`, `scripts/run_sweep_h2.py`, and `scripts/analyze_sweep_results.py`.
- The PyElastica rod model is modularized in `src/helical_propeller/`.
- RFT forcing and endpoint torque are implemented in `src/helical_propeller/forces.py`.
- Torque-driven RFT analytical comparison is implemented in `src/helical_propeller/theory.py`.
- The project records validity fields: `invalid_result`, `failure_reason`, `stiffness_status`, and `deformation_exceeded`.
- Efficiency metrics `Eta_power` and `Eta_slip` are computed and exported.
- Damping diagnostics and damping-result analysis tools are available.
- Raw and processed data directories are defined: `data/raw/` and `data/processed/`.
- Colab simulation / local analysis workflow is documented in `docs/final_data_generation_plan.md`.
- Lightweight pytest tests exist and avoid long parameter sweeps.

## Partially Satisfied Items

- Navier-Stokes and RFT relationship is explainable from existing docs, but the research plan should contain a clearer standalone paragraph.
- RFT assumptions and limitations are documented, but the research plan should explicitly state that this is not full CFD.
- Damping can be configured in `run_simulation`, H1/H2 configs, and the local H1/H2 runner path, but any Colab-side copied scripts must be kept in sync.
- H1/H2 scripts are separated, and the local sweep orchestration now passes `damping_constant`; Colab execution should use this updated version.
- H2 config currently has `pitch=0.02`, `radius=0.01`, so `P/R=2.0`; it must be updated after H1 chooses the final P/R.
- H1/H2 configs now use `total_steps=240000`; final interpretation still needs returned steady-state diagnostics.

## Insufficient Items

- Final output naming convention has not yet been frozen for repeated Colab runs.
- Final medium-validation result for `damping_constant=1.0e-5` has not yet been analyzed locally.
- There is no committed final H1/H2 results table yet because final simulations are intentionally run in Colab by the user.
- A research-plan-ready figure/table template is not yet generated from final data.

## Theory That Must Be Explained In The Research Plan

- Navier-Stokes equations are the general fluid motion equations.
- At low Reynolds number, viscous forces dominate inertial forces.
- Under low-Re conditions, RFT approximates local drag by tangential and normal resistance coefficients.
- This project does not solve full Navier-Stokes CFD; it uses PyElastica rod dynamics with RFT forcing and an analytical RFT comparison.
- RFT is local and approximate; it omits nonlocal hydrodynamic interactions, wall effects, detailed head/body flow, and full fluid-structure coupling.
- Damping is a numerical simulation setting, not part of the analytical RFT resistance model.
- PyElastica simulation is deformable and time-dependent, while analytical RFT comparison is a simplified torque-driven resistance balance.

## Before Final Experiment Checklist

- Analyze Colab medium damping validation CSV with `scripts/analyze_damping_results.py`.
- Confirm final damping value, currently expected to be `1.0e-5` if medium validation is stable.
- Confirm final H1 config or Colab execution cell uses the selected damping value and updated runner code.
- Run `scripts/check_sweep_config.py configs/sweep_h1.yaml --kind h1`.
- Confirm the H1 final range starts at `P/R=2.0` unless intentionally testing failure cases.
- Confirm H1 `total_steps`, `step_skip`, `n_elem`, and `torque_magnitude`.
- Confirm H1 output summary CSV will not overwrite important prior results.
- After H1, choose final P/R before running H2.
- Set H2 `pitch = selected_P_over_R * radius`.
- Run `scripts/check_sweep_config.py configs/sweep_h2.yaml --kind h2 --expected-pr <selected_pr>`.

## After Final Experiment Checklist

- Copy Colab raw CSVs to `data/raw/` and summary CSVs to `data/processed/`.
- Analyze H1 summary with `scripts/analyze_sweep_results.py --kind h1`.
- Exclude invalid, failed, non-OK stiffness, and deformation-exceeded rows before interpreting trends.
- Report transient rows separately from final physical conclusions.
- Select 1-2 H1 P/R candidates using `V_sim`, `Eta_power`, `Eta_slip`, `omega_sim`, and validity flags.
- Analyze H2 summary with `scripts/analyze_sweep_results.py --kind h2`.
- Select body ratio candidates from valid rows only.
- In the research report, discuss damping influence, transient status, RFT approximation limits, and body drag approximation limits.
