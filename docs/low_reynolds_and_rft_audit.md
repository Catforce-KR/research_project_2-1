# Low Reynolds Number And RFT Audit

## Audit Purpose

This document checks whether the completed H1/H2 result summaries remain in a low-Reynolds-number regime and whether the project documentation can support the use of RFT as the analytical comparison model. No simulation is executed by this audit.

## Data Sources

- H1 summary: `C:\Users\LG\research_project_2-1\data\helical_results\helical_results\h1_final_fixed\processed\sweep_h1_summary.csv + C:\Users\LG\research_project_2-1\data\helical_results\helical_results\h1_extended_high_pr\processed\sweep_h1_summary.csv`
- H2 summary: `C:\Users\LG\research_project_2-1\data\helical_results\helical_results\h2_final_pr5\processed\sweep_h2_summary.csv`
- Config fallback: `configs/sweep_h1.yaml`, `configs/sweep_h2.yaml`

## Existing Documentation Check

| File | Existing content | Quantitative Re included | Gap |
| --- | --- | --- | --- |
| `docs/project_structure_for_research_plan.md` | Conceptual Navier-Stokes/RFT relationship, PyElastica-RFT role, torque-driven comparison, damping influence. | No | Needs final data Reynolds number audit. |
| `docs/research_plan_gap_check.md` | Checklist-level low-Re/RFT assumptions, limitations, damping and analytical-theory distinction. | No | Needs numerical Re ranges for final H1/H2 data. |
| `docs/final_results_summary.md` | Final H1/H2 conclusions, damping rationale, conceptual Navier-Stokes/RFT section. | Partial after this audit | Add explicit Re ranges and exclusion of damping_constant from Re. |
| `docs/final_data_generation_plan.md` | Execution/analysis workflow and damping decision flow. | No | Not intended to be the low-Re audit document. |
| `docs/model_assumptions.md` | Low-Re regime, RFT approximation, torque-driven RFT equations, body drag approximation, damping diagnostics. | No | Could cite the final audit for numeric Re support. |
| `docs/validation.md` | Analytical comparison metrics and damping diagnostics. | No | No Reynolds number validation criterion. |

## Navier-Stokes And RFT Relationship

The Navier-Stokes equations are the general continuum equations for fluid motion. This project does not solve the full Navier-Stokes equations or run CFD. Instead, it models the elastic helical swimmer with PyElastica and applies RFT-style local drag forces as the low-Reynolds-number hydrodynamic approximation.

At low Reynolds number, viscous effects dominate over inertial effects. Under slender-body/local-drag assumptions, RFT approximates the force per unit length using tangential and normal resistance coefficients. The analytical comparison used here is therefore torque-driven RFT, not a full CFD benchmark.

## Reynolds Number Formula

The audit uses:

`Re = density * abs(V) * L / fluid_viscosity`

Velocity scales use both `V_sim` and `V_theory`. Length scales use `radius` and `total_length`. When these columns are absent from the summary CSV, the values are read from the corresponding sweep config. `damping_constant` is not part of the Reynolds number because it is a PyElastica numerical damping parameter, not the fluid viscosity.

Operational status thresholds:

- `LOW_RE_CONFIRMED`: maximum evaluated Re < 0.01.
- `LOW_RE_REASONABLE`: 0.01 <= maximum evaluated Re < 1.
- `LOW_RE_VIOLATION`: maximum evaluated Re >= 1.
- `UNKNOWN`: required parameters are unavailable.

## Computed Re Ranges

| Sweep | max Re(radius, V_sim) | max Re(total_length, V_sim) | max Re(radius, V_theory) | max Re(total_length, V_theory) | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| H1 | 0.000255953 | 0.00255953 | 0.000285479 | 0.00285479 | LOW_RE_CONFIRMED |
| H2 | 0.000248293 | 0.00248293 | 0.000349329 | 0.00349329 | LOW_RE_CONFIRMED |

## RFT Applicability Assessment

- The final H1/H2 data remain below `Re=1` for both radius and total-length scales, using both simulation and theory velocities.
- The total-length scale is the conservative larger length scale in this audit; it still remains in the low-Re range.
- The geometry uses a finite helical radius and pitch sweep. RFT remains a local slender-body approximation, so very loose helices at high P/R should be interpreted with more caution than mid-range P/R cases.
- `fluid_viscosity=0.1` and `density=1000.0` produce a computational low-Re regime for the observed micrometer-per-second-scale velocities. These parameters should be described as simulation/model parameters rather than as a claim of direct water-like experimental matching.

## fluid_viscosity Versus damping_constant

- `fluid_viscosity` enters the RFT hydrodynamic resistance model and the Reynolds number calculation.
- `damping_constant=1e-5` is an internal PyElastica damping/stabilization parameter.
- The damping parameter can affect the theory/simulation comparison by absorbing part of the applied torque, but it is not a physical fluid viscosity and must not be used in the Reynolds number.

## Report-Ready Sentences

- In the final simulation data, the Reynolds numbers computed from both the swimmer radius and total length remain well below 1, supporting a low-Reynolds-number interpretation.
- The study does not solve the full Navier-Stokes equations; it combines PyElastica rod dynamics with an RFT local drag approximation and compares the simulation with torque-driven analytical RFT.
- The numerical `damping_constant` is distinct from `fluid_viscosity` and is excluded from the Reynolds number calculation.

## Remaining Limitations

- RFT is a local drag approximation and does not capture all nonlocal hydrodynamic interactions.
- High P/R cases may be less representative of a compact helical propeller geometry.
- The density/viscosity settings support the computational low-Re condition, but they should not be over-interpreted as a full experimental fluid match.
