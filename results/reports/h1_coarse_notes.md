# H1 Coarse Sweep Notes

## Files

- Execution config: `configs/sweep_h1.yaml`
- Working summary: `data/processed/sweep_h1_summary.csv`
- Preserved summary: `results/tables/h1_coarse_summary.csv`
- Raw time-series files: `data/raw/sim_N80_pr*_T1e-08.csv`

## Run Scope

- Sweep type: H1 pitch/radius coarse sweep
- Total cases: 10
- OK cases: 9
- Non-OK cases: 1
- Non-OK condition: `P/R=0.5`, status `NAN/INF`

## Observations

- `P/R=0.5` produced `NAN/INF` and should be handled separately from the OK cases.
- `P/R=1.0` through `P/R=5.0` completed with status `OK`.
- All OK cases recorded `stiffness_status=OK`.
- All OK cases recorded `deformation_exceeded=False`.
- No final P/R selection is made from this coarse run.

## Candidate Groups

- `V_sim` candidate region: `P/R=2.5` to `P/R=3.5`, with `P/R=3.0` highest in this coarse table.
- `Eta_power` candidate region: `P/R=2.0` to `P/R=3.5`, with `P/R=3.0` highest in this coarse table.
- `Eta_slip` candidate region: `P/R=1.0` to `P/R=2.5`, decreasing over the sampled OK cases.
- `pct_error` lower-error candidate region: `P/R=1.0` to `P/R=3.0`, with smaller values on the lower P/R side.

## Do Not Conclude Yet

- The candidate regions differ depending on whether the priority is `V_sim`, `Eta_power`, `Eta_slip`, or `pct_error`.
- Steady-state behavior has not yet been checked from the raw CSV files.
- The last-window stability of `Vz_mean` and `Omega_z` has not yet been summarized.
- `P/R=0.5` has not been classified beyond `NAN/INF`.
- The reason for large `pct_error` values has not yet been separated into model, transient, or metric effects.
- The current H1 run is a first coarse pass, not a refined analysis.

## Follow-Up Checks Before Refined Sweep

- Check whether `Vz_mean` and `Omega_z` are stable in the final recorded segment of each raw CSV.
- Decide whether the refined sweep should prioritize `V_sim`, `Eta_power`, `Eta_slip`, or a multi-criteria filter.
- Decide whether `P/R=0.5` is excluded as a low-pitch invalid condition or rerun separately.
- Inspect why `pct_error` remains large across OK cases before using it as a primary filter.
- Confirm whether `total_steps=10000` is sufficient for steady behavior at the candidate P/R values.
