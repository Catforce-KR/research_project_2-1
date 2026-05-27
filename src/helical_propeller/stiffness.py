import numpy as np

def stiffness_check(
    sim_result: dict,
    deformation_threshold: float = 2.0,  # % threshold for warning
) -> dict:
    """
    Check the structural integrity of the helical tail by comparing
    initial vs. final states. Computes:

    1. Max node displacement as % of total_length
    2. Pitch deformation in the tail region (change in z-spacing between nodes
       that correspond to one full helical turn)
    3. Max curvature (kappa) deviation: ||kappa - rest_kappa|| / ||rest_kappa||
       (if kappa data is available)

    If any deformation metric exceeds `deformation_threshold`%, the function
    flags the result and recommends increasing bending stiffness (E).

    Returns a dict with:
        - max_displacement_pct: float
        - pitch_deformation_pct: float or None
        - max_pitch_deviation_pct: float or None
        - kappa_deformation_pct: float or None (kappa strain metric)
        - worst_metric_pct: float
        - deformation_exceeded: bool (True if any metric > threshold)
        - recommendation: str
        - status: str ("OK", "DEFORMED", or "N/A" if insufficient data)
    """
    positions = sim_result.get("position", [])
    if len(positions) < 2:
        return {
            "max_displacement_pct": float('nan'),
            "pitch_deformation_pct": None,
            "max_pitch_deviation_pct": None,
            "kappa_deformation_pct": None,
            "worst_metric_pct": float('nan'),
            "deformation_exceeded": False,
            "recommendation": "Insufficient position data for stiffness check.",
            "status": "N/A",
        }

    pos0 = positions[0]  # initial positions (3, n_nodes)
    pos1 = positions[-1]  # final positions (3, n_nodes)
    params = sim_result.get("parameters", {})
    total_length = params.get("total_length", 0.1)
    n_elem = params.get("n_elem", 30)
    body_length_ratio = params.get("body_length_ratio", 0.5)

    # ---- Metric 1: Max node displacement ----
    displacements = np.linalg.norm(pos1 - pos0, axis=0)
    max_disp = float(displacements.max())
    max_disp_pct = max_disp / total_length * 100.0

    # ---- Metric 2: Pitch deformation in tail ----
    n_nodes = pos0.shape[1]
    n_elem_local = n_nodes - 1
    n_body_nodes = max(1, min(n_elem_local, int(round(body_length_ratio * n_elem_local)))) + 1

    pitch_deformation_pct = None
    max_pitch_deviation_pct = None

    if n_body_nodes < n_nodes:
        tail_init_z = pos0[2, n_body_nodes:]
        tail_final_z = pos1[2, n_body_nodes:]

        dz_init = np.diff(tail_init_z)
        dz_final = np.diff(tail_final_z)

        mean_dz_init = float(np.mean(dz_init)) if len(dz_init) > 0 else 0.0
        if abs(mean_dz_init) > 1e-15 and len(dz_final) > 0:
            mean_dz_final = float(np.mean(dz_final))
            pitch_deformation_pct = abs(mean_dz_final - mean_dz_init) / abs(mean_dz_init) * 100.0

            local_deviations = np.abs(dz_final - dz_init) / (np.abs(dz_init) + 1e-30)
            max_pitch_deviation_pct = float(local_deviations.max() * 100.0)
        else:
            pitch_deformation_pct = 0.0
            max_pitch_deviation_pct = 0.0

    # ---- Metric 3: Kappa (curvature) deformation ----
    kappa_data = sim_result.get("kappa", [])
    kappa_deformation_pct = None
    if len(kappa_data) >= 2:
        try:
            kappa_init = kappa_data[0]  # (3, n_voronoi)
            kappa_final = kappa_data[-1]
            norm_init = float(np.linalg.norm(kappa_init))
            if norm_init > 1e-15:
                kappa_diff = float(np.linalg.norm(kappa_final - kappa_init))
                kappa_deformation_pct = kappa_diff / norm_init * 100.0
            else:
                kappa_deformation_pct = 0.0
        except Exception:
            kappa_deformation_pct = None

    # ---- Decision ----
    metrics = [max_disp_pct]
    if pitch_deformation_pct is not None:
        metrics.append(pitch_deformation_pct)
    if max_pitch_deviation_pct is not None:
        metrics.append(max_pitch_deviation_pct)
    if kappa_deformation_pct is not None:
        metrics.append(kappa_deformation_pct)

    worst_metric = max(metrics)
    deformation_exceeded = worst_metric > deformation_threshold

    if deformation_exceeded:
        current_E = params.get("E", 1e7)
        recommended_E = current_E * max(2.0, worst_metric / deformation_threshold)
        recommendation = (
            f"Deformation detected: worst metric = {worst_metric:.3f}% "
            f"(threshold={deformation_threshold:.1f}%). "
            f"Increase Young's Modulus from E={current_E:.1e} to ~{recommended_E:.1e}."
        )
        status = "DEFORMED"
    else:
        recommendation = (
            f"Structural integrity OK: max displacement = {max_disp_pct:.6f}% "
            f"of total length, within {deformation_threshold:.1f}% threshold."
        )
        status = "OK"

    return {
        "max_displacement_pct": max_disp_pct,
        "pitch_deformation_pct": pitch_deformation_pct,
        "max_pitch_deviation_pct": max_pitch_deviation_pct,
        "kappa_deformation_pct": kappa_deformation_pct,
        "worst_metric_pct": worst_metric,
        "deformation_exceeded": deformation_exceeded,
        "recommendation": recommendation,
        "status": status,
    }


# ============================================================
# Stiffness Calibration Module (TAS-4)
# Systematically find minimum E for elastic integrity
# ============================================================
def stiffness_calibration(
    pitch: float = 0.02,
    radius: float = 0.01,
    total_length: float = 0.1,
    body_length_ratio: float = 0.5,
    n_elem: int = 40,
    torque_magnitude: float = 1e-6,
    E_values: list = None,
    nu: float = 0.5,
    fluid_viscosity: float = 0.1,
    density: float = 1000.0,
    dt: float = 1e-5,
    total_steps: int = 5000,
    step_skip: int = 50,
    deformation_threshold: float = 2.0,
) -> dict:
    """
    Systematic stiffness calibration: sweep over Young's Modulus (E)
    values to find the minimum stiffness that keeps helical tail
    deformation below the threshold.

    The function:
    1. Runs a simulation for each E value
    2. Computes stiffness_check metrics for each run
    3. Identifies the transition point where deformation drops below threshold
    4. Reports recommended E (with safety margin)

    Parameters
    ----------
    E_values : list, optional
        Young's Modulus values to test (Pa). Default:
        [1e4, 2e4, 5e4, 1e5, 2e5, 5e5, 1e6, 2e6, 5e6, 1e7, 2e7, 5e7, 1e8]

    Returns
    -------
    dict with:
        - results: dict keyed by E value with stiffness metrics
        - recommended_E: float (minimum E that passes + 2x safety margin)
        - threshold_crossed: float (E value where deformation first drops below threshold)
        - all_deformed: bool (True if even highest E is deformed)
        - all_ok: bool (True if even lowest E is OK)
    """
    from .simulator import run_simulation

    if E_values is None:
        E_values = [1e4, 2e4, 5e4, 1e5, 2e5, 5e5, 1e6, 2e6, 5e6, 1e7, 2e7, 5e7, 1e8]

    print("=" * 70)
    print("Stiffness Calibration: Sweep over Young's Modulus (E)")
    print("=" * 70)
    print(f"  Torque: {torque_magnitude:.1e} Nm,  Threshold: {deformation_threshold:.1f}%")
    print("-" * 70)
    header = f"{'E (Pa)':>12} {'MaxDisp%':>12} {'PitchDef%':>12} {'KappaDef%':>12} {'Status':>12}"
    print(header)
    print("-" * 70)

    results = {}
    for E in E_values:
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
            )

            stiffness = sim_result.get("stiffness")
            if stiffness is None:
                results[E] = {
                    "status": "NO_STIFFNESS_DATA",
                    "max_displacement_pct": float('nan'),
                    "pitch_deformation_pct": None,
                    "kappa_deformation_pct": None,
                    "worst_metric_pct": float('nan'),
                    "deformation_exceeded": True,
                }
                print(f"{E:>12.1e} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'NO DATA':>12}")
                continue

            max_disp = stiffness["max_displacement_pct"]
            pitch_def = stiffness.get("pitch_deformation_pct")
            kappa_def = stiffness.get("kappa_deformation_pct")
            deformed = stiffness["deformation_exceeded"]
            worst = stiffness["worst_metric_pct"]

            status = "DEFORMED" if deformed else "OK"

            results[E] = {
                "status": status,
                "max_displacement_pct": max_disp,
                "pitch_deformation_pct": pitch_def,
                "kappa_deformation_pct": kappa_def,
                "worst_metric_pct": worst,
                "deformation_exceeded": deformed,
                "stiffness": stiffness,
                "sim_result": sim_result,
            }

            pdef_str = f"{pitch_def:.4f}" if pitch_def is not None else "N/A"
            kdef_str = f"{kappa_def:.4f}" if kappa_def is not None else "N/A"
            print(f"{E:>12.1e} {max_disp:>12.6f} {pdef_str:>12} {kdef_str:>12} {status:>12}")

        except Exception as e:
            results[E] = {"status": "EXCEPTION", "error": str(e)}
            print(f"{E:>12.1e} {'EXCEPTION':>12} {'':>12} {'':>12} {str(e)[:30]:>30}")

    print("=" * 70)

    # ---- Analysis: find the transition point ----
    sorted_E = sorted(E_values)
    ok_E_values = [E for E in sorted_E
                   if results.get(E, {}).get("status") == "OK"
                   and not results[E].get("deformation_exceeded", True)]

    deformed_E_values = [E for E in sorted_E
                         if results.get(E, {}).get("status") != "OK"
                         or results.get(E, {}).get("deformation_exceeded", True)]

    all_deformed = len(ok_E_values) == 0
    all_ok = len(deformed_E_values) == 0

    if not all_deformed:
        # First E that passes
        threshold_crossed = ok_E_values[0]
        # Recommended E: 2x safety margin over the passing E
        recommended_E = threshold_crossed * 2.0
        # If 2x exceeds the maximum tested, cap at max
        if recommended_E > sorted_E[-1]:
            recommended_E = sorted_E[-1]
    else:
        threshold_crossed = None
        # Even the highest E is deformed - recommend going higher
        recommended_E = sorted_E[-1] * 10.0 if sorted_E else 1e9

    # ---- Print summary ----
    print("\n")
    print("=" * 70)
    print("CALIBRATION RESULTS")
    print("=" * 70)
    print(f"  Applied torque:                 {torque_magnitude:.1e} Nm")
    print(f"  Deformation threshold:          {deformation_threshold:.1f}%")
    if threshold_crossed is not None:
        print(f"  Minimum E for <{deformation_threshold:.0f}% deformation: {threshold_crossed:.2e} Pa")
        print(f"  Recommended E (2x safety margin): {recommended_E:.2e} Pa")
    else:
        print(f"  [!] All E values produced >{deformation_threshold:.0f}% deformation")
        print(f"  [!] Need E > {sorted_E[-1]:.2e} Pa (extrapolated: ~{recommended_E:.2e} Pa)")
    if all_ok:
        print(f"  Note: Even the lowest E ({sorted_E[0]:.2e}) produced <{deformation_threshold:.0f}% deformation")
    print(f"  G (derived):                    {recommended_E / (2.0 * (1.0 + 0.5)):.2e} Pa")
    print("=" * 70)

    return {
        "results": results,
        "recommended_E": recommended_E,
        "recommended_G": recommended_E / (2.0 * (1.0 + 0.5)),
        "threshold_crossed": threshold_crossed,
        "all_deformed": all_deformed,
        "all_ok": all_ok,
    }

