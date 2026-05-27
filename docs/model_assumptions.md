# Model Assumptions

## Low-Reynolds-Number Regime

The project targets low-Reynolds-number propulsion where viscous forces dominate inertial effects. Propulsion is modeled through local drag relationships rather than high-Reynolds-number fluid dynamics.

## RFT Approximation

The current code uses Resistive Force Theory as a linear drag approximation. Local velocity is decomposed into tangential and normal components relative to the rod tangent, and separate drag coefficients are applied to those components.

The current implementation uses slender-body-style logarithmic coefficients in both the numerical forcing and analytical prediction. The torque-driven theory continues to use the same local `C_t` and `C_n` definitions as the numerical forcing.

## PyElastica / Cosserat Rod

The helical propeller is represented as a Cosserat rod through PyElastica, imported in the current code as `elastica`. The model includes rod elasticity, applied endpoint torque, damping, and RFT-based external forcing.

## Analytical Prediction vs Simulation

`V_theory` is now computed by a torque-driven RFT analytical approximation, not a Navier-Stokes or CFD result. The analytical model constructs an axial rigid-helix resistance relation:

```text
F_z = -A_total * V + B * omega = 0
T_z =  B * V - D_total * omega + applied_torque = 0
```

It solves these force-free and torque-balance equations simultaneously for `V_theory` and `omega_theory`. PyElastica simulation result comes from numerically integrating the deformable Cosserat rod with applied endpoint torque and RFT-based external forcing. The comparison remains "RFT analytical approximation vs RFT-forced Cosserat rod simulation"; differences between `V_theory` and `V_sim` do not validate RFT itself.

Reports must clearly distinguish:

- `analytical`: RFT prediction such as `V_theory`, `C_t`, and `C_n`.
- `simulation`: PyElastica output such as final velocity, time history, deformation, and stiffness status.

## Geometry Convention In Theory

- `pitch` is the axial advance per complete helix turn, matching `theta_tail = 2*pi*z/pitch` in `geometry.py`.
- `radius` is the helical centerline radius.
- `total_length` is the configured axial span used by the existing geometry and RFT coefficient call, not the helical contour length.
- `body_length_ratio * total_length` is the straight body's axial length; the remaining axial span is converted to continuous helical contour length for the resistance matrix.
- `helix_angle` is the pitch angle above the transverse plane. Low `P/R` therefore gives a low pitch angle; low-P/R rows are flagged with a theory warning rather than automatically rejected.

## Body Drag Approximation

- The analytical model adds axial body translation resistance as `C_t * body_length`.
- It adds rotational resistance as `C_n * body_length * body_radius^2`, representing the existing straight centerline offset from the swimming axis.
- This is a minimal RFT centerline/slender-cylinder-inspired approximation, not a resolved head or spheroid hydrodynamic model.
- The simulation body remains part of the deformable rod and is not an independently constrained rigid head, so quantitative body resistance agreement remains approximate.

## Analysis Metrics

- `pct_error` is retained as a compatibility alias for `pct_error_vs_sim`, using the simulated velocity magnitude as denominator where meaningful.
- `pct_error_vs_theory` uses the analytical prediction magnitude as denominator and is the primary percentage error for comparing a sweep against its prediction.
- Near-zero or nonfinite denominators are represented by `error_status` rather than interpreted as ordinary percent errors.
- `steady_state_status` is a diagnostic based on the final 20 percent velocity window relative to the preceding 20 percent window; `TRANSIENT_LIKELY` and `MEAN_NEAR_ZERO` flag interpretation limits rather than proving simulation failure.
- `force_residual_norm` and `torque_residual_norm` evaluate the steady analytical balance equations at final-window simulation averages. Nonzero values in a transient, damped, deformable run diagnose comparison limits; they are not themselves evidence that the RFT coefficient implementation is wrong.
- `effective_rotational_resistance` infers the rotational resistance needed to balance the measured `omega_sim` at the configured torque and axial coupling. It should be interpreted only after angular-velocity steady state is established.
- Torque balance diagnostics now expose `B * V_sim`, `D_total * omega_sim`, and applied torque separately, together with ratios referenced to the applied torque. This breakdown is diagnostic only and does not alter the resistance model.
- Rotational resistance diagnostics expose helix and body shares of the existing `D_total`, plus `effective_D_ratio`, so a persistent torque mismatch can be attributed before changing a drag formula.
- `torque_balance_with_damping_residual` subtracts an estimated resisting damper torque from the existing torque residual. It is an attribution diagnostic and is not included in `V_theory` or `omega_theory`.

## Torque And Angular-Velocity Frame Convention

- `EndpointTorques` adds the configured vector `[0, 0, torque_magnitude]` to `system.external_torques[:, 0]`.
- PyElastica's rotational evolution combines `external_torques` with material angular quantities; the diagnostic metadata therefore records the applied torque convention conservatively as `ASSUMED_MATERIAL_COMPONENT_2` until that interpretation is separately validated.
- The callback explicitly converts stored material-frame angular velocity through `director_collection` and records `omega_sim` as `INERTIAL_GLOBAL_Z`.
- A comparison between an assumed material-component endpoint torque and an inertial global-z averaged angular velocity may contribute to torque-balance residuals; the frame labels must be retained with diagnostic output.
- New simulations record `applied_torque_global_z_projection` and `applied_torque_axis_alignment` through the callback. Previously saved raw CSV files do not contain director histories or projected torque and are explicitly classified as `PROJECTION_UNAVAILABLE`.

## Numerical Damping Diagnostic

- The simulation currently uses PyElastica `AnalyticalLinearDamper` with the deprecated `damping_constant=1e-3` protocol.
- In that protocol, rotational rates are multiplied elementwise by an exponential factor derived from `damping_constant`, element mass, inverse rotational inertia, and dilatation. Its equivalent resisting material torque is proportional to `damping_constant * element_mass * omega_material`.
- For new simulations, the callback forms that elementwise equivalent torque and projects its sum onto inertial global-z, consistent with the stored `omega_sim` axis.
- For legacy raw CSV reanalysis, elementwise material omega and director history are unavailable. The stored diagnostic therefore estimates `damping_torque_estimate` as `damping_constant * rotational_damping_mass * omega_sim`, using the implemented rod mass and a uniform global-z rotation assumption; it is labeled `ESTIMATED_FROM_MEAN_GLOBAL_Z_OMEGA_LEGACY_RAW`.
- The numerical damper is not part of the RFT analytical resistance model. If its estimated torque explains a large residual, the next comparison must separate numerical relaxation from intended hydrodynamic resistance before modifying RFT coefficients or body drag.

## Efficiency Interpretation

- `Eta_power` is an RFT-based useful power ratio estimate using body axial drag power divided by `applied_torque * omega_used`. It is not a measure of total fluid dissipation efficiency.
- `Eta_slip` is a kinematic/slip indicator of how rotation is converted into forward motion, referenced to the no-slip screw speed computed from `omega_used` and pitch.
- `omega_used` preferentially uses inertial-frame simulation axis rate `omega_sim`; `omega_theory` is used only when a simulated rate is unavailable.
- Final interpretation must consider `V_sim`, `Eta_power`, `Eta_slip`, stiffness metrics, and `steady_state_status` together.

## Current Code Assumptions

- The body portion is represented as a straight section.
- The tail portion is represented as a helix.
- RFT forcing is applied through the current `ResistiveForceTheoryForcing` class.
- Endpoint torque drives rotation.
- Callback angular velocity is converted from PyElastica material coordinates into inertial-frame global-z `omega_sim` before analytical and efficiency use.
- Stiffness validity is checked from recorded position, curvature, and shear/stretch data where available.
- Stiffness calculation definitions are unchanged from the current implementation.
