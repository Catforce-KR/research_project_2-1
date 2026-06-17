import numpy as np

from .analysis_metrics import build_common_result_summary
from .efficiency import compute_efficiency
from .logging_utils import log_sweep_summary
from .simulator import run_simulation


def _stiffness_summary(stiffness: dict) -> dict:
    if not stiffness:
        return {
            "stiffness_status": None,
            "deformation_exceeded": None,
            "worst_metric_pct": float("nan"),
        }
    return {
        "stiffness_status": stiffness.get("status"),
        "deformation_exceeded": stiffness.get("deformation_exceeded"),
        "worst_metric_pct": stiffness.get("worst_metric_pct", float("nan")),
    }


def _common_summary(sim_result: dict, status: str, torque_magnitude: float, raw_velocity=None):
    efficiency = sim_result.get("efficiency")
    if efficiency is None:
        efficiency = compute_efficiency(sim_result, torque_magnitude=torque_magnitude)
    common = build_common_result_summary(
        analytical=sim_result.get("analytical"),
        efficiency=efficiency,
        stiffness=sim_result.get("stiffness"),
        status=status,
        raw_velocity=raw_velocity,
    )
    return efficiency, common


def parameter_sweep_h1(
    radius: float = 0.01,
    total_length: float = 0.1,
    n_elem: int = 30,
    pr_values: list = None,
    torque_magnitude: float = 1e-8,
    dt: float = 1e-5,
    total_steps: int = 3000,
    step_skip: int = 30,
    fluid_viscosity: float = 0.1,
    density: float = 1000.0,
    E: float = 1e7,
    nu: float = 0.5,
    body_length_ratio: float = 0.5,
    damping_constant: float = 1e-3,
) -> dict:
    """
    Sweep over Pitch/Radius (P/R) ratios to test Hypothesis 1.
    
    Keeps radius fixed and varies pitch to achieve desired P/R ratios.
    Returns a dictionary keyed by P/R value with simulation results.
    
    Robustness features:
    - Detects NaN/Inf in velocity arrays and flags as 'UNSTABLE'
    - Computes both instantaneous final velocity and time-averaged velocity
      (average over last 20% of recorded steps to reduce transient noise)
    - Computes center-of-mass velocity for a more robust propulsion metric
    """
    if pr_values is None:
        # Default: 10 points from 0.5 to 5.0
        pr_values = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    
    # Pre-compute center-of-mass indices for each node (uniform mass distribution)
    # For a rod with n_nodes, the CoM velocity = mean of all node velocities
    
    results = {}
    print("=" * 70)
    print("Hypothesis 1: Pitch/Radius (P/R) Ratio Parameter Sweep")
    print("=" * 70)
    header = f"{'P/R':>8} {'Pitch':>12} {'Vz_final':>15} {'Vz_com':>15} {'Status':>10}"
    print(header)
    print("-" * 70)
    
    for pr in pr_values:
        pitch = pr * radius  # P/R = pitch / radius => pitch = P/R * radius
        
        status = "ERROR"
        has_nan = False
        has_inf = False
        try:
            sim_result = run_simulation(
                n_elem=n_elem,
                pitch=pitch,
                radius=radius,
                total_length=total_length,
                body_length_ratio=body_length_ratio,
                density=density,
                E=E,
                nu=nu,
                fluid_viscosity=fluid_viscosity,
                dt=dt,
                total_steps=total_steps,
                step_skip=step_skip,
                torque_magnitude=torque_magnitude,
                damping_constant=damping_constant,
            )
            
            if sim_result["final_velocity"] is not None:
                vz_final = sim_result["final_velocity"][2, :]  # z-velocity at all nodes
                
                # Check for NaN/Inf anywhere in the recorded velocity output.
                velocity_output = sim_result.get("velocity", [sim_result["final_velocity"]])
                has_nan = any(bool(np.any(np.isnan(v))) for v in velocity_output)
                has_inf = any(bool(np.any(np.isinf(v))) for v in velocity_output)
                
                if has_nan or has_inf:
                    vz_mean = float('nan')
                    vz_com = float('nan')
                    status = "NAN/INF"
                else:
                    # Metric 1: Mean of all node z-velocities at final time
                    vz_mean = float(vz_final.mean())
                    
                    # Metric 2: Time-averaged center-of-mass velocity
                    # Average over last 20% of recorded velocity history
                    vel_hist = sim_result["velocity"]
                    n_hist = len(vel_hist)
                    if n_hist >= 5:
                        # Average CoM velocity over last 20% of steps
                        last_20pct = vel_hist[max(0, n_hist - max(1, n_hist // 5)):]
                        com_z_velocities = [v[2, :].mean() for v in last_20pct]
                        vz_com = float(np.mean(com_z_velocities))
                    else:
                        vz_com = vz_mean  # fallback
                    
                    # Determine stability: if max |v_z| > 1.0 m/s, flag as unstable
                    # (reasonable propulsion should be < 0.1 m/s for torque=1e-8)
                    max_abs_vz = float(np.max(np.abs(vz_final)))
                    if max_abs_vz > 1.0:
                        status = "BUCKLING"
                    elif abs(vz_mean) > 0.5:
                        status = "UNSTABLE"
                    else:
                        status = "OK"
                
                stiffness = sim_result.get("stiffness")
                stiffness_summary = _stiffness_summary(stiffness)
                efficiency, common_summary = _common_summary(
                    sim_result, status, torque_magnitude, velocity_output
                )
                status = common_summary["status"]
                results[pr] = {
                    "pitch": pitch,
                    "vz_final_mean": vz_mean,
                    "vz_com_avg": vz_com,
                    "vz_array": vz_final,
                    "final_velocity": sim_result["final_velocity"],
                    "time": sim_result["time"],
                    "velocity_history": sim_result["velocity"],
                    "omega_history": sim_result.get("omega"),
                    "omega_z_history": sim_result.get("omega_z_history"),
                    "parameters": sim_result["parameters"],
                    "has_nan": has_nan,
                    "has_inf": has_inf,
                    "analytical": sim_result.get("analytical"),
                    "efficiency": efficiency,
                    "stiffness": stiffness,
                    **stiffness_summary,
                    **common_summary,
                }
                print(f"{pr:>8.1f} {pitch:>12.6f} {vz_mean:>15.6e} {vz_com:>15.6e} {status:>10}")
            else:
                results[pr] = {
                    "pitch": pitch,
                    "error": "No velocity data",
                    **build_common_result_summary(None, None, None, status="NO_DATA"),
                }
                print(f"{pr:>8.1f} {pitch:>12.6f} {'N/A':>15} {'N/A':>15} {'NO DATA':>10}")
                
        except Exception as e:
            results[pr] = {
                "pitch": pitch,
                "error": str(e),
                **build_common_result_summary(None, None, None, status="EXCEPTION"),
            }
            print(f"{pr:>8.1f} {pitch:>12.6f} {'ERR':>15} {'ERR':>15} {str(e)[:30]:>30}")
    
    print("=" * 70)
    
    # Export sweep summary to CSV
    try:
        log_sweep_summary(results, filepath="sweep_h1_summary.csv", sweep_type="h1")
    except Exception as e:
        print(f"  CSV sweep summary skipped: {e}")
    
    return results


# ============================================================
# Hypothesis 2: Body-to-Tail Length Ratio Parameter Sweep
# ============================================================
def parameter_sweep_h2(
    pitch: float = 0.02,
    radius: float = 0.01,
    total_length: float = 0.1,
    n_elem: int = 30,
    body_ratio_values: list = None,
    torque_magnitude: float = 1e-8,
    dt: float = 1e-5,
    total_steps: int = 3000,
    step_skip: int = 30,
    fluid_viscosity: float = 0.1,
    density: float = 1000.0,
    E: float = 1e7,
    nu: float = 0.5,
    damping_constant: float = 1e-3,
) -> dict:
    """
    Sweep over Body-to-Tail length ratios to test Hypothesis 2.
    
    Varies body_length_ratio from 0.1 to 0.9, keeping other parameters fixed.
    The body portion is a straight rod (no thrust), the tail is helical.
    This tests how body-to-tail length proportion affects propulsion.
    
    Returns a dictionary keyed by body_length_ratio with simulation results.
    """
    if body_ratio_values is None:
        # Default: 9 points from 0.1 to 0.9
        body_ratio_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    
    results = {}
    print("=" * 70)
    print("Hypothesis 2: Body-to-Tail Length Ratio Parameter Sweep")
    print("=" * 70)
    header = f"{'Body/Tail':>10} {'BodyLen(m)':>12} {'Vz_final':>15} {'Vz_com_avg':>15} {'Status':>10}"
    print(header)
    print("-" * 70)
    
    for br in body_ratio_values:
        body_len = br * total_length
        
        status = "ERROR"
        has_nan = False
        has_inf = False
        try:
            sim_result = run_simulation(
                n_elem=n_elem,
                pitch=pitch,
                radius=radius,
                total_length=total_length,
                body_length_ratio=br,
                density=density,
                E=E,
                nu=nu,
                fluid_viscosity=fluid_viscosity,
                dt=dt,
                total_steps=total_steps,
                step_skip=step_skip,
                torque_magnitude=torque_magnitude,
                damping_constant=damping_constant,
            )
            
            if sim_result["final_velocity"] is not None:
                vz_final = sim_result["final_velocity"][2, :]
                
                # Check for NaN/Inf anywhere in the recorded velocity output.
                velocity_output = sim_result.get("velocity", [sim_result["final_velocity"]])
                has_nan = any(bool(np.any(np.isnan(v))) for v in velocity_output)
                has_inf = any(bool(np.any(np.isinf(v))) for v in velocity_output)
                
                if has_nan or has_inf:
                    vz_mean = float('nan')
                    vz_com = float('nan')
                    status = "NAN/INF"
                else:
                    # Metric 1: Mean node z-velocity at final time
                    vz_mean = float(vz_final.mean())
                    
                    # Metric 2: Time-averaged CoM velocity over last 20% of history
                    vel_hist = sim_result["velocity"]
                    n_hist = len(vel_hist)
                    if n_hist >= 5:
                        last_20pct = vel_hist[max(0, n_hist - max(1, n_hist // 5)):]
                        com_z_velocities = [v[2, :].mean() for v in last_20pct]
                        vz_com = float(np.mean(com_z_velocities))
                    else:
                        vz_com = vz_mean
                    
                    # Stability classification
                    max_abs_vz = float(np.max(np.abs(vz_final)))
                    if max_abs_vz > 1.0:
                        status = "BUCKLING"
                    elif abs(vz_mean) > 0.5:
                        status = "UNSTABLE"
                    else:
                        status = "OK"
                
                stiffness = sim_result.get("stiffness")
                stiffness_summary = _stiffness_summary(stiffness)
                efficiency, common_summary = _common_summary(
                    sim_result, status, torque_magnitude, velocity_output
                )
                status = common_summary["status"]
                results[br] = {
                    "body_length_ratio": br,
                    "body_length": body_len,
                    "vz_final_mean": vz_mean,
                    "vz_com_avg": vz_com,
                    "vz_array": vz_final,
                    "final_velocity": sim_result["final_velocity"],
                    "time": sim_result["time"],
                    "velocity_history": sim_result["velocity"],
                    "omega_history": sim_result.get("omega"),
                    "omega_z_history": sim_result.get("omega_z_history"),
                    "parameters": sim_result["parameters"],
                    "has_nan": has_nan,
                    "has_inf": has_inf,
                    "analytical": sim_result.get("analytical"),
                    "efficiency": efficiency,
                    "stiffness": stiffness,
                    **stiffness_summary,
                    **common_summary,
                }
                print(f"{br:>8.1f}     {body_len:>12.6f} {vz_mean:>15.6e} {vz_com:>15.6e} {status:>10}")
            else:
                results[br] = {
                    "body_length_ratio": br,
                    "error": "No velocity data",
                    **build_common_result_summary(None, None, None, status="NO_DATA"),
                }
                print(f"{br:>8.1f}     {body_len:>12.6f} {'N/A':>15} {'N/A':>15} {'NO DATA':>10}")
                
        except Exception as e:
            results[br] = {
                "body_length_ratio": br,
                "error": str(e),
                **build_common_result_summary(None, None, None, status="EXCEPTION"),
            }
            print(f"{br:>8.1f}     {body_len:>12.6f} {'ERR':>15} {'ERR':>15} {str(e)[:30]:>30}")
    
    print("=" * 70)
    
    # Export sweep summary to CSV
    try:
        log_sweep_summary(results, filepath="sweep_h2_summary.csv", sweep_type="h2")
    except Exception as e:
        print(f"  CSV sweep summary skipped: {e}")
    
    return results


# ============================================================
# Efficiency Module (TAS-13)
# Compute and plot propulsive efficiency vs P/R ratio
# ============================================================

def n_convergence_test(
    pitch: float = 0.02,
    radius: float = 0.01,
    total_length: float = 0.1,
    body_length_ratio: float = 0.5,
    n_values: list = None,
    torque_magnitude: float = 1e-7,
    dt: float = 1e-5,
    total_steps: int = 10000,
    step_skip: int = 100,
    fluid_viscosity: float = 0.1,
    density: float = 1000.0,
    E: float = 1e7,
    nu: float = 0.5,
    convergence_threshold: float = 1.0,  # 1% threshold (in percentage units)
) -> dict:
    """
    Run simulations with increasing element counts to verify convergence
    of propulsion velocity.

    Standard N values: [10, 20, 40, 80] (doubling each step).
    Convergence is checked between the two highest N values.

    Returns a dictionary with:
        - results: dict keyed by N with simulation results
        - convergence_achieved: bool
        - convergence_error_pct: float (relative error between top 2 N values)
        - recommended_n: int (minimum N for <1% convergence)
    """
    if n_values is None:
        n_values = [10, 20, 40, 80]

    print("=" * 70)
    print("N-Convergence Test: Propulsion Velocity vs Element Count")
    print("=" * 70)
    header = f"{'N_elems':>10} {'Vz_final_mean':>18} {'Vz_com_avg':>18} {'Status':>12}"
    print(header)
    print("-" * 70)

    results = {}
    for N in n_values:
        status = "ERROR"
        vz_mean = float('nan')
        vz_com = float('nan')
        has_nan = False
        has_inf = False
        try:
            sim_result = run_simulation(
                n_elem=N,
                pitch=pitch,
                radius=radius,
                total_length=total_length,
                body_length_ratio=body_length_ratio,
                density=density,
                E=E,
                nu=nu,
                fluid_viscosity=fluid_viscosity,
                dt=dt,
                total_steps=total_steps,
                step_skip=step_skip,
                torque_magnitude=torque_magnitude,
            )

            if sim_result["final_velocity"] is not None:
                vz_final = sim_result["final_velocity"][2, :]

                velocity_output = sim_result.get("velocity", [sim_result["final_velocity"]])
                has_nan = any(bool(np.any(np.isnan(v))) for v in velocity_output)
                has_inf = any(bool(np.any(np.isinf(v))) for v in velocity_output)

                if has_nan or has_inf:
                    status = "NAN/INF"
                else:
                    vz_mean = float(vz_final.mean())

                    # Time-averaged CoM velocity over last 20% of history
                    vel_hist = sim_result["velocity"]
                    n_hist = len(vel_hist)
                    if n_hist >= 5:
                        last_20pct = vel_hist[max(0, n_hist - max(1, n_hist // 5)):]
                        com_z_velocities = [v[2, :].mean() for v in last_20pct]
                        vz_com = float(np.mean(com_z_velocities))
                    else:
                        vz_com = vz_mean

                    max_abs_vz = float(np.max(np.abs(vz_final)))
                    if max_abs_vz > 1.0:
                        status = "BUCKLING"
                    elif abs(vz_mean) > 0.5:
                        status = "UNSTABLE"
                    else:
                        # Tentatively OK — will check sign consistency below
                        status = "OK"

            analysis = sim_result.get("analytical")
            stiffness = sim_result.get("stiffness")
            stiffness_summary = _stiffness_summary(stiffness)
            eff, common_summary = _common_summary(
                sim_result, status, torque_magnitude, sim_result.get("velocity")
            )
            status = common_summary["status"]

            results[N] = {
                "n_elem": N,
                "vz_final_mean": vz_mean,
                "vz_com_avg": vz_com,
                "final_velocity": sim_result.get("final_velocity"),
                "velocity_history": sim_result.get("velocity"),
                "omega_history": sim_result.get("omega"),
                "omega_z_history": sim_result.get("omega_z_history"),
                "time": sim_result.get("time"),
                "final_time": sim_result.get("final_time"),
                "parameters": sim_result.get("parameters"),
                "has_nan": has_nan,
                "has_inf": has_inf,
                "analytical": analysis,
                "efficiency": eff,
                "stiffness": stiffness,
                **stiffness_summary,
                **common_summary,
            }
            print(f"{N:>10d} {vz_mean:>18.6e} {vz_com:>18.6e} {status:>12}")

        except Exception as e:
            results[N] = {
                "n_elem": N,
                "vz_final_mean": float("nan"),
                "vz_com_avg": float("nan"),
                "error": str(e),
                **build_common_result_summary(None, None, None, status="EXCEPTION"),
            }
            print(f"{N:>10d} {'EXCEPTION':>18} {'':>18} {str(e)[:30]:>30}")

    print("=" * 70)

    # Use vz_com_avg (time-averaged over last 20% of history) as the primary metric
    # for convergence comparison, because it is more robust than the instantaneous
    # vz_final_mean (which is noisy due to temporal oscillations).
    
    # Find the two highest N values that produced valid (non-NaN, non-exception) results
    valid_Ns = sorted([N for N, r in results.items()
                       if r.get("status") in ("OK",) and not np.isnan(r["vz_com_avg"])])
    
    # --- Sign consistency check ---
    # If lower-N results have opposite sign from the highest-N result, flag as INCONSISTENT
    if len(valid_Ns) >= 2:
        N_highest = valid_Ns[-1]
        sign_ref = np.sign(results[N_highest]["vz_com_avg"])
        for N in valid_Ns[:-1]:
            if np.sign(results[N]["vz_com_avg"]) != sign_ref and abs(results[N]["vz_com_avg"]) > 1e-20:
                results[N].update(
                    build_common_result_summary(
                        analytical=results[N].get("analytical"),
                        efficiency=results[N].get("efficiency"),
                        stiffness=results[N].get("stiffness"),
                        status="INCONSISTENT",
                        raw_velocity=results[N].get("velocity_history"),
                    )
                )
        # Re-filter valid_Ns after sign check (exclude INCONSISTENT)
        valid_Ns = sorted([N for N, r in results.items()
                           if r.get("status") in ("OK",) and not np.isnan(r["vz_com_avg"])])
        # Re-print status column with updated flags
        print("\n(Sign consistency check applied: INCONSISTENT = sign differs from highest-N result)")
        for N in sorted(results.keys()):
            r = results[N]
            print(f"  N={N:3d}: status={r.get('status','?'):15s}  Vz_com_avg={r['vz_com_avg']:12.6e}  Vz_final={r['vz_final_mean']:12.6e}")
        print()

    convergence_achieved = False
    convergence_error_pct = float('inf')
    recommended_n = n_values[-1] if n_values else 80

    if len(valid_Ns) >= 2:
        N_high = valid_Ns[-1]   # highest valid N
        N_low = valid_Ns[-2]    # second highest valid N
        v_high = results[N_high]["vz_com_avg"]
        v_low = results[N_low]["vz_com_avg"]

        if abs(v_high) > 1e-20:  # avoid division by zero
            convergence_error_pct = abs(v_high - v_low) / abs(v_high) * 100.0
            convergence_achieved = convergence_error_pct < convergence_threshold
            recommended_n = N_low if convergence_achieved else N_high

            print(f"\nConvergence Analysis (using Vz_com_avg, time-averaged over last 20% of steps):")
            print(f"  {N_low:3d} elems -> {N_high:3d} elems: |v({N_high}) - v({N_low})| / |v({N_high})| = {convergence_error_pct:.4f}%")
            print(f"  Threshold: {convergence_threshold:.1f}% -> {'CONVERGED' if convergence_achieved else 'NOT CONVERGED'}")
            if convergence_achieved:
                print(f"  Recommended minimum N for convergence: {N_low}")
            else:
                print(f"  Further refinement needed (N > {N_high} may be required)")
        else:
            print(f"\nConvergence Analysis: propulsion velocity near zero, skipping ratio check")
    else:
        print(f"\nConvergence Analysis: insufficient valid data points ({len(valid_Ns)}/2 valid N values)")

    print("=" * 70)

    return {
        "results": results,
        "convergence_achieved": convergence_achieved,
        "convergence_error_pct": convergence_error_pct,
        "recommended_n": recommended_n,
        "valid_Ns": valid_Ns,
    }

