# Final Results Summary

## Final Data Files

- H1 summary: `data/helical_results/helical_results/h1_final_fixed/processed/sweep_h1_summary.csv + data/helical_results/helical_results/h1_extended_high_pr/processed/sweep_h1_summary.csv`
- H2 summary: `data/helical_results/helical_results/h2_final_pr5/processed/sweep_h2_summary.csv`

## H1 Result Summary

- In the final H1 range, `V_sim` is largest at `P/R=6.0`.
- `Eta_power` is largest at `P/R=5.0`.
- Across the high-P/R side, both propulsion speed and efficiency decrease after their peak region.
- `V_theory` and `V_sim` are reported separately because the analytical result is a torque-driven RFT approximation while the simulation is a PyElastica-RFT rod result.

## H2 Result Summary

- H2 uses the representative `P/R=5.0` condition.
- `V_sim` is largest at `body_length_ratio=0.5`.
- `Eta_power` is largest at `body_length_ratio=0.5`.
- Performance decreases when the body becomes too long relative to the tail.

## Why damping_constant=1e-5 Was Used

- `damping_constant` is a PyElastica numerical damping / stabilization setting, not the physical fluid viscosity.
- Fluid resistance is represented by `fluid_viscosity` and the RFT forcing model.
- Earlier `1e-3` and `1e-4` runs showed damping torque could absorb a large fraction of the applied torque and distort the theory comparison.
- `1e-5` reduced damping influence while remaining stable enough for the final data generation.

## Navier-Stokes And RFT

- This project does not solve the Navier-Stokes equations directly.
- Navier-Stokes equations are the general equations of fluid motion.
- In low-Reynolds-number propulsion, viscous effects dominate inertial effects.
- RFT approximates local drag around a slender body using tangential and normal resistance coefficients.
- The project combines PyElastica rod dynamics with RFT forcing, then compares the result with torque-driven analytical RFT.
- Therefore the comparison is not full CFD vs simulation; it is analytical RFT vs PyElastica-RFT simulation.

## Limitations

- Full Navier-Stokes / CFD is not solved.
- RFT relies on local-resistance and slender-body assumptions.
- Numerical damping affects the simulation-theory comparison.
- Theory-simulation differences can grow at high P/R or extreme body ratios.
- Efficiency metrics are model-based indicators, not complete hydrodynamic efficiency.

## Final Conclusion

- H1 speed optimum: `P/R=6.0`.
- H1 power-efficiency optimum: `P/R=5.0`.
- H2 optimum at `P/R=5.0`: `body_length_ratio=0.5` for both speed and power efficiency.
- The balanced final design candidate is `P/R=5.0`, `body_length_ratio=0.5`.

## Raw Time-Series Files Used

- `h1_pr6_velocity`: data/helical_results/helical_results/h2_final_pr5/raw/sim_N80_pr6.00_T1e-08.csv (Vz_mean)
- `h1_pr6_omega`: data/helical_results/helical_results/h2_final_pr5/raw/sim_N80_pr6.00_T1e-08.csv (Omega_z)
- `h1_pr5_velocity`: data/helical_results/helical_results/h2_final_pr5/raw/sim_N80_pr5.00_T1e-08.csv (Vz_mean)
- `h1_pr5_omega`: data/helical_results/helical_results/h2_final_pr5/raw/sim_N80_pr5.00_T1e-08.csv (Omega_z)
- `h2_body_ratio_0p5_velocity`: data/helical_results/helical_results/h2_final_pr5/raw/sweep_h2_br0.50_timeseries.csv (Vz_mean)
- `h2_body_ratio_0p5_omega`: data/helical_results/helical_results/h2_final_pr5/raw/sweep_h2_br0.50_timeseries.csv (Omega_z)
