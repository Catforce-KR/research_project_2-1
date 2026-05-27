# Experiment Plan

## H1: Pitch/Radius Ratio Sweep

Goal: estimate how pitch/radius ratio affects propulsion velocity, analytical error, and efficiency.

Analytical comparison now uses the torque-driven RFT model with approximate body drag. Low-P/R rows carrying `theory_warning=LOW_PITCH_RATIO` should be reviewed with their numerical validity fields before interpretation.

Inputs:

- `pitch`
- `radius`
- `total_length`
- `n_elem`
- `torque_magnitude`
- fluid and material parameters

Outputs:

- simulation velocity summaries
- analytical comparison values
- efficiency metrics
- stability or deformation flags
- summary CSV fields include `V_sim`, `V_theory`, `absolute_error`, `signed_error`, `pct_error`, `pct_error_vs_theory`, `pct_error_vs_sim`, `error_status`, steady-state metrics/status, `Eta_slip`, `Eta_power`, `stiffness_status`, `deformation_exceeded`, `worst_metric_pct`, `failure_reason`, and `invalid_result`
- torque-driven columns additionally include `omega_theory`, `omega_sim`, `omega_used`, `omega_source`, `theory_mode`, `efficiency_model`, `A`, `B`, `D`, `A_total`, `D_total`, and body drag coefficients

Storage:

- raw sweep CSV in `data/raw/`
- processed summary CSV in `data/processed/` or `results/tables/`
- figures in `results/figures/`

Smoke execution:

- Use `.venv\Scripts\python.exe scripts\run_sweep_h1.py --dry-run` to inspect the default smoke config without running simulations.
- Use `.venv\Scripts\python.exe scripts\run_sweep_h1.py` only for the guarded smoke sweep in `configs/sweep_h1_smoke.yaml`.
- Longer H1 sweep configs must be passed explicitly with `--config` and require `--allow-long` to execute.
- The first coarse H1 config is `configs/sweep_h1.yaml` with `n_elem=80`, `E=1e7`, `total_steps=10000`, and 10 P/R values. These are conservative first-pass settings, not final validated constants.

Representative transient check:

- Before interpreting the torque-driven theory mismatch, use `.venv\Scripts\python.exe scripts\run_transient_check.py --tag <label>` with `configs/h1_pr3_transient_check.yaml`.
- This check fixes `P/R=3.0`, `n_elem=80`, and the physical parameters while comparing `total_steps=[10000, 30000, 60000]` with approximately 1 percent logging intervals.
- If velocity remains transient after the initial duration series, use `configs/h1_pr3_transient_check_120000.yaml` for the single `total_steps=120000` follow-up before changing physical formulas.
- For the final duration-only diagnosis, use `configs/h1_pr3_transient_check_480000.yaml` once and run `scripts/analyze_transient_prefixes.py` on its raw time-series to evaluate checkpoints without repeated simulations.
- Interpret `V_sim`, `omega_sim`, steady-state classifications, force/torque balance residuals, and effective rotational resistance together. It is a duration-sensitivity diagnostic, not an H1 sweep or a basis for tuning RFT coefficients.
- When torque residual persists after `V_sim` and `omega_sim` stabilize, use the prefix analyzer's torque-term ratios, rotational-resistance fractions, and frame metadata before considering any RFT or body-drag formula change.
- Use the damping-adjusted residual only as attribution evidence: legacy raw output uses a mean-axis estimate, while a future targeted run can write projected torque and elementwise damping-equivalent histories directly.

## H2: Body-To-Tail Length Ratio Sweep

Goal: estimate how body-to-tail length ratio affects propulsion and stability while keeping the model assumptions fixed.

Inputs:

- `body_length_ratio`
- helix geometry parameters
- material parameters
- torque and time stepping parameters

Outputs:

- final and averaged propulsion velocities
- analytical comparison values
- stiffness status
- efficiency metrics
- summary CSV fields include `V_sim`, `V_theory`, both percentage-error references, steady-state metrics/status, efficiency metrics, stiffness metrics, `failure_reason`, and `invalid_result`
- torque-driven columns include `omega_theory`, `omega_sim`, `omega_used`, `omega_source`, `theory_mode`, `efficiency_model`, resistance terms, and approximate body drag terms

Storage:

- raw sweep CSV in `data/raw/`
- processed summary CSV in `data/processed/` or `results/tables/`
- figures in `results/figures/`

Smoke execution:

- Use `.venv\Scripts\python.exe scripts\run_sweep_h2.py --dry-run` to inspect the default smoke config without running simulations.
- Use `.venv\Scripts\python.exe scripts\run_sweep_h2.py` only for the guarded smoke sweep in `configs/sweep_h2_smoke.yaml`.
- Longer H2 sweep configs must be passed explicitly with `--config` and require `--allow-long` to execute.
- The first coarse H2 config is `configs/sweep_h2.yaml` with `n_elem=80`, `E=1e7`, `total_steps=10000`, and 9 body-ratio values. These are conservative first-pass settings, not final validated constants.

## Stiffness Calibration

Goal: identify a Young's modulus range where tail deformation remains within the configured threshold.

Inputs:

- `E`
- deformation threshold
- base geometry
- torque magnitude

Outputs:

- stiffness status
- deformation metrics
- recommended stiffness range

Storage:

- calibration tables in `results/tables/`
- any diagnostic figures in `results/figures/`

Smoke-safe execution:

- Use `.venv\Scripts\python.exe scripts\run_stiffness_calibration.py --dry-run` to inspect `configs/stiffness_calibration_smoke.yaml` without running calibration.
- Use `.venv\Scripts\python.exe scripts\run_stiffness_calibration.py` only after reviewing the smoke config.
- Larger calibration configs must be passed explicitly with `--config`.

## Pilot Single Run

Goal: run one representative condition before full H1/H2 sweeps to check simulation readiness, analytical comparison, efficiency summary, and stiffness status.

Smoke-safe execution:

- Use `.venv\Scripts\python.exe scripts\run_pilot_single.py --dry-run` to inspect `configs/pilot_single.yaml` without running the simulation.
- Use `.venv\Scripts\python.exe scripts\run_pilot_single.py` only when the pilot config has been reviewed.
- Larger pilot configs must be passed explicitly with `--config`.

## Discretization / n_elem Validation

Goal: check whether propulsion metrics are stable under increased discretization.

Inputs:

- `n_elem`
- fixed geometry and physical parameters

Outputs:

- velocity convergence trend
- analytical error trend
- steady-state and invalid-result diagnostics for each discretization candidate
- recommended `n_elem`

Storage:

- validation tables in `results/tables/`
- validation figures in `results/figures/`

Smoke-safe execution:

- Use `.venv\Scripts\python.exe scripts\run_n_convergence.py --dry-run` to inspect `configs/n_convergence_smoke.yaml` without running convergence.
- Use `.venv\Scripts\python.exe scripts\run_n_convergence.py` only after reviewing the smoke config.
- Larger convergence configs must be passed explicitly with `--config`.
- The smoke candidate set is `[20, 40, 80]`; `N=10` is excluded as too low for the current geometry/discretization.
- `N=80` is used as the first coarse H1/H2 sweep basis after excluding `N=10` and observing that short pilot convergence did not produce a final recommendation.

## Execution Rule

H1/H2 sweeps, stiffness calibration sweeps, and `n_elem` convergence runs are long-running experiments. Do not execute them unless the user explicitly requests them.

## Interpretation Rule

- Treat `pct_error_vs_theory` as the primary percentage comparison; retain `pct_error` only for compatibility with earlier simulated-velocity-referenced outputs.
- Exclude rows with `invalid_result=True` from physical conclusions until their `failure_reason` has been reviewed.
- A row with `steady_state_status=TRANSIENT_LIKELY` or `MEAN_NEAR_ZERO` remains diagnostic output, but is not sufficient for a final physical conclusion.
- Read `V_sim`, `Eta_power`, `Eta_slip`, stiffness validity, and steady-state status together.
