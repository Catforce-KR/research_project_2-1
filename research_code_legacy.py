import numpy as np
import elastica as ea

# 시스템 컬렉션 정의
class SpiralRodSimulator(
    ea.BaseSystemCollection, 
    ea.Forcing, 
    ea.Constraints, 
    ea.CallBacks, 
    ea.Connections, 
    ea.Damping
):
    pass

# 2. 정제된 RFT (Resistive Force Theory) 클래스 - Purcell Slender Body Theory 기반
class ResistiveForceTheoryForcing(ea.NoForces):
    def __init__(self, fluid_viscosity, radius, rod_total_length=None):
        super().__init__()
        self.fluid_viscosity = fluid_viscosity
        self.radius = radius
        self.rod_total_length = rod_total_length  # 로그 항에 사용할 전체 막대 길이
        
    def apply_forces(self, system, time=0.0):
        # 나선형 추진체(CosseratRod)에 대한 항력
        if hasattr(system, 'velocity_collection') and hasattr(system, 'tangents'):
            velocity = system.velocity_collection
            tangents = system.tangents
            radius = self.radius
            
            # 전체 막대 길이 계산 (슬렌더 바디 이론의 특성 길이)
            if self.rod_total_length is not None:
                L_total = self.rod_total_length
            else:
                L_total = np.sum(system.rest_lengths)
            
            # Purcell/Lighthill Slender Body Theory 계수
            # 점근적으로 Cn/Ct → 2 (slender limit)
            # ξ_∥ = 2πμ / (ln(2L_total/a) - 0.5)  접선 저항 계수 (단위 길이당)
            # ξ_⊥ = 4πμ / (ln(2L_total/a) + 0.5)  법선 저항 계수 (단위 길이당)
            log_arg = 2.0 * L_total / radius
            log_term = np.log(log_arg) if log_arg > 1.0 else 0.0
            
            C_t = 2.0 * np.pi * self.fluid_viscosity / (log_term - 0.5)  # ξ_∥
            C_n = 4.0 * np.pi * self.fluid_viscosity / (log_term + 0.5)  # ξ_⊥
            
            for i in range(system.n_elems):
                v_elem = 0.5 * (velocity[:, i] + velocity[:, i+1])
                t = tangents[:, i]
                L_elem = system.rest_lengths[i]
                
                v_t = np.dot(v_elem, t) * t
                v_n = v_elem - v_t
                
                # 요소 길이를 곱하여 요소 전체 항력 계산
                drag_force = -(C_t * v_t + C_n * v_n) * L_elem
                
                system.external_forces[:, i] += 0.5 * drag_force
                system.external_forces[:, i+1] += 0.5 * drag_force
                
        # 원통형 몸체(Cylinder)에 대한 항력 - tangents가 없으면 Cylinder로 판별
        elif hasattr(system, 'velocity_collection') and not hasattr(system, 'tangents'):
            vel = system.velocity_collection.flatten()
            body_len = system.length  # 실린더 길이
            C_drag = 4.0 * np.pi * self.fluid_viscosity  # Stokes 항력 계수 (단위 길이당)
            system.external_forces += (-C_drag * vel * body_len).reshape(3, 1)


class EndpointTorques(ea.NoForces):
    def __init__(self, start_torque):
        super().__init__()
        self.start_torque = start_torque
        
    def apply_torques(self, system, time=0.0):
        system.external_torques[:, 0] += self.start_torque


# 6. 콜백 기반 데이터 수집 (간소화)
class BasicDataCollector(ea.CallBackBaseClass):
    def __init__(self, step_skip: int, callback_params: dict):
        super().__init__()
        self.step_skip = step_skip
        self.callback_params = callback_params

    def make_callback(self, system, time, current_step: int):
        if current_step % self.step_skip == 0:
            self.callback_params["time"].append(time)
            self.callback_params["position"].append(system.position_collection.copy())
            self.callback_params["velocity"].append(system.velocity_collection.copy())
            # Record angular velocity for analytical comparison
            if hasattr(system, 'omega_collection'):
                self.callback_params["omega"].append(system.omega_collection.copy())
            # Record curvature (kappa) and shear-stretch (sigma) for stiffness check
            if hasattr(system, 'kappa'):
                self.callback_params["kappa"].append(system.kappa.copy())
            if hasattr(system, 'sigma'):
                self.callback_params["sigma"].append(system.sigma.copy())


# ============================================================
# Analytical Comparison Module (TAS-10)
# Purcell Slender Body Theory for helical propeller
# ============================================================
def compute_theoretical_velocity(
    pitch: float,
    radius: float,
    total_length: float,
    angular_velocity: float,
    filament_radius: float = None,
    fluid_viscosity: float = 0.1,
) -> dict:
    """
    Compute the theoretical steady-state propulsion velocity for a helix
    using Purcell's Slender Body Theory (Resistive Force Theory).

    The formula derived from RFT force balance on a rotating helix:

        V_theory = (C_n - C_t) * ω * 2π * R² * P
                   ──────────────────────────────────
                      4π² * R² * C_n + P² * C_t

    where:
        C_t = 2πμ / (ln(2L/a) - 0.5)   [tangential drag per unit length]
        C_n = 4πμ / (ln(2L/a) + 0.5)   [normal drag per unit length]
        ω = angular velocity (rad/s) about helix axis
        R = helix radius (m)
        P = helix pitch (m)
        L = total filament length (m)
        a = filament radius (m)

    Reference: Purcell (1977) "Life at Low Reynolds Number",
               Lauga & Powers (2009) Rep. Prog. Phys. 72 096601
    """
    if filament_radius is None:
        filament_radius = radius  # default: same as helix radius

    # Slender body log term
    log_arg = 2.0 * total_length / filament_radius
    log_term = np.log(log_arg) if log_arg > 1.0 else 0.0

    # RFT coefficients (same as ResistiveForceTheoryForcing)
    C_t = 2.0 * np.pi * fluid_viscosity / (log_term - 0.5)
    C_n = 4.0 * np.pi * fluid_viscosity / (log_term + 0.5)

    # Pitch angle geometry
    # cosφ = P / sqrt(P² + 4π²R²)
    # sinφ = 2πR / sqrt(P² + 4π²R²)
    denom = pitch**2 + 4.0 * np.pi**2 * radius**2
    cos_phi_sq = pitch**2 / denom
    sin_phi_sq = 4.0 * np.pi**2 * radius**2 / denom
    sin_phi_cos_phi = 2.0 * np.pi * radius * pitch / denom

    # RFT force balance: net z-force on free-swimming helix = 0
    # V_theory = -(C_t - C_n) * ω * R * sinφ * cosφ / [C_n + (C_t - C_n) * cos²φ]
    numerator = (C_n - C_t) * angular_velocity * 2.0 * np.pi * radius**2 * pitch
    denominator = 4.0 * np.pi**2 * radius**2 * C_n + pitch**2 * C_t

    if abs(denominator) < 1e-30:
        V_theory = 0.0
    else:
        V_theory = numerator / denominator

    # Also compute the simpler slender body limit (Cn = 2Ct):
    # V_slender = ω * 2π * R² * P / (8π² * R² + P²)
    V_slender = angular_velocity * 2.0 * np.pi * radius**2 * pitch / (
        8.0 * np.pi**2 * radius**2 + pitch**2
    )

    Cn_over_Ct = C_n / C_t if C_t != 0 else float('inf')

    return {
        "V_theory": V_theory,
        "V_slender_limit": V_slender,
        "C_t": C_t,
        "C_n": C_n,
        "Cn_over_Ct": Cn_over_Ct,
        "log_term": log_term,
        "angular_velocity": angular_velocity,
        "pitch": pitch,
        "radius": radius,
    }


def analytical_comparison(
    sim_result: dict,
    fluid_viscosity: float = 0.1,
) -> dict:
    """
    Compare simulation results with theoretical prediction.
    Computes V_theory from the measured angular velocity and geometry,
    then calculates percentage error relative to simulated V.

    Returns a dict with theoretical velocity, simulated velocity,
    percentage error, and intermediate quantities.
    """
    params = sim_result.get("parameters", {})
    pitch = params.get("pitch", 0.02)
    radius = params.get("radius", 0.01)
    total_length = params.get("total_length", 0.1)

    # Get angular velocity from simulation (steady-state average)
    omega_history = sim_result.get("omega_history", [])
    if omega_history and len(omega_history) > 0:
        # Use last 20% of omega history for steady-state average
        n_omega = len(omega_history)
        steady_omega = omega_history[max(0, n_omega - max(1, n_omega // 5)):]
        # omega is shape (3, n_elems) — take z-component mean
        omega_z_mean = float(np.mean([o[2, :].mean() for o in steady_omega]))
    else:
        omega_z_mean = 0.0

    # Compute theoretical velocity
    theory = compute_theoretical_velocity(
        pitch=pitch,
        radius=radius,
        total_length=total_length,
        angular_velocity=omega_z_mean,
        filament_radius=radius,  # same as helix radius
        fluid_viscosity=fluid_viscosity,
    )

    # Get simulated velocity
    vz_history = sim_result.get("vz_history", [])
    if vz_history and len(vz_history) > 0:
        n_vz = len(vz_history)
        steady_vz = vz_history[max(0, n_vz - max(1, n_vz // 5)):]
        V_sim = float(np.mean(steady_vz))
    else:
        V_sim = 0.0

    # Percentage error relative to simulated value
    V_theory = theory["V_theory"]
    if abs(V_sim) > 1e-30:
        pct_error = (V_theory - V_sim) / abs(V_sim) * 100.0
    elif abs(V_theory) > 1e-30:
        pct_error = float('inf')
    else:
        pct_error = 0.0

    return {
        "V_sim": V_sim,
        "V_theory": V_theory,
        "V_slender_limit": theory["V_slender_limit"],
        "pct_error": pct_error,
        "omega_z": omega_z_mean,
        "C_t": theory["C_t"],
        "C_n": theory["C_n"],
        "Cn_over_Ct": theory["Cn_over_Ct"],
        "log_term": theory["log_term"],
    }


# ============================================================
# Stiffness Check Module (TAS-11)
# Monitor helical pitch deformation during rotation
# ============================================================
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


def run_simulation(
    # --- Helix geometry ---
    n_elem: int = 30,
    pitch: float = 0.02,
    radius: float = 0.01,
    total_length: float = 0.1,
    # --- Body (head) parameters ---
    body_length_ratio: float = 0.5,
    body_radius: float = None,
    # --- Material properties ---
    density: float = 1000.0,
    E: float = 1e7,
    nu: float = 0.5,
    # --- Fluid ---
    fluid_viscosity: float = 0.1,
    # --- Numerical ---
    dt: float = 1e-5,
    total_steps: int = 10000,
    step_skip: int = 100,
    # --- Applied torque ---
    torque_magnitude: float = 1e-8,
) -> dict:
    """
    Run a helical propeller simulation using Elastica (PyElastica).

    The rod consists of two sections:
      - Body (straight rod offset from axis by body_radius, provides rotational resistance)
      - Tail (helical section, generates propulsion)

    Parameters
    ----------
    body_radius : float, optional
        Offset distance of body from z-axis. Controls rotational drag moment arm.
        If None (default), uses same value as `radius` (helix radius).
        Larger values increase rotational resistance, reducing counter-rotation.

    Returns a dictionary containing simulation results:
        - time: list of time points (from callback)
        - position: list of position arrays (from callback)
        - velocity: list of velocity arrays (from callback)
        - final_velocity: steady-state propulsion velocity (last recorded)
        - final_time: final simulation time
        - parameters: dict of input parameters used
    """
    # Derived quantities
    n_nodes = n_elem + 1
    n_voronoi = n_elem - 1
    G = E / (2.0 * (1.0 + nu))
    body_length = body_length_ratio * total_length
    if body_radius is None:
        body_radius = 1.0 * radius  # default: same radius as tail

    # 1. 시스템 컬렉션 생성
    spiral_sim = SpiralRodSimulator()

    # 2. 하이브리드 형상 (Body + Tail) 계산
    # Body 부분: z축에서 body_radius만큼 떨어진 직선 막대 (추진력 없음, 회전 저항 제공)
    #   - body_radius: body offset from z-axis (moment arm for rotational drag)
    #   - Larger body_radius -> greater rotational resistance -> less counter-rotation
    # Tail 부분: 반지름 radius의 나선형 (추진력 생성)
    n_body_elems = max(1, min(n_elem - 1, int(round(body_length_ratio * n_elem))))
    n_tail_elems = n_elem - n_body_elems

    positions = np.zeros((3, n_nodes))

    # Body: z축과 평행한 직선, (body_radius, 0, z) 위치
    z_body = np.linspace(0, body_length, n_body_elems + 1)
    positions[0, :n_body_elems + 1] = body_radius
    positions[1, :n_body_elems + 1] = 0.0
    positions[2, :n_body_elems + 1] = z_body

    # Tail: 나선형
    z_tail = np.linspace(body_length, total_length, n_tail_elems + 1)
    theta_tail = 2 * np.pi * (z_tail - body_length) / pitch
    positions[0, n_body_elems:] = radius * np.cos(theta_tail)
    positions[1, n_body_elems:] = radius * np.sin(theta_tail)
    positions[2, n_body_elems:] = z_tail

    tangents = np.diff(positions, axis=1)
    rest_lengths = np.linalg.norm(tangents, axis=0)
    tangents /= rest_lengths

    # 로컬 프레임(Directors) 계산
    directors = np.zeros((3, 3, n_elem))
    for i in range(n_elem):
        t = tangents[:, i]
        if i < n_body_elems:
            # Body 영역: 직선 막대 - z방향 접선, d1=x, d2=y 방향
            # (body가 x=body_radius, y=0 선을 따라 z방향으로 진행)
            d1 = np.array([0.0, 1.0, 0.0])
            d2 = np.cross(t, d1)
            d2 /= np.linalg.norm(d2)
            d1 = np.cross(d2, t)
        else:
            # Tail 영역: 나선형 - 중심을 향하는 방향
            d2 = np.array([-positions[0, i], -positions[1, i], 0.0])
            d2_norm = np.linalg.norm(d2)
            d2 = d2 / d2_norm if d2_norm > 1e-10 else np.array([1.0, 0.0, 0.0])
            d1 = np.cross(d2, t)
            d1 /= np.linalg.norm(d1)
            d2 = np.cross(t, d1)
        
        directors[0, :, i] = d1
        directors[1, :, i] = d2
        directors[2, :, i] = t

    # 단면 물리 속성 계산
    A = np.pi * radius**2
    I = (np.pi * radius**4) / 4.0
    J = 2.0 * I

    shear_matrix = np.zeros((3, 3, n_elem))
    bend_matrix = np.zeros((3, 3, n_voronoi))
    for i in range(n_elem):
        shear_matrix[:, :, i] = np.diag([G*A, G*A, E*A])
    for i in range(n_voronoi):
        bend_matrix[:, :, i] = np.diag([E*I, E*I, G*J])

    volumes = np.full(n_elem, A * total_length / n_elem)
    mass = np.zeros(n_nodes)
    mass[:-1] += 0.5 * density * volumes
    mass[1:] += 0.5 * density * volumes

    mass_inertia = np.zeros((3, 3, n_elem))
    inv_mass_inertia = np.zeros((3, 3, n_elem))
    for i in range(n_elem):
        mass_inertia[:, :, i] = np.diag([I, I, J]) * density * rest_lengths[i]
        inv_mass_inertia[:, :, i] = np.linalg.inv(mass_inertia[:, :, i])

    # 초기 곡률(Kappa) 계산
    rest_voronoi_lengths = 0.5 * (rest_lengths[:-1] + rest_lengths[1:])
    initial_kappa = np.zeros((3, n_voronoi))
    for i in range(n_voronoi):
        Q1 = directors[:, :, i]
        Q2 = directors[:, :, i+1]
        R = Q2 @ Q1.T
        theta = np.arccos(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0))
        if theta > 1e-12:
            axis = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
            axis /= np.linalg.norm(axis)
            initial_kappa[:, i] = ((Q1 + Q2) / 2.0) @ (theta * axis / rest_voronoi_lengths[i])

    # 3. 물리 객체 생성 및 시스템 추가
    spiral_rod = ea.CosseratRod(
        n_elements=n_elem,
        position=positions,
        velocity=np.zeros((3, n_nodes)),
        omega=np.zeros((3, n_elem)),
        acceleration=np.zeros((3, n_nodes)),
        angular_acceleration=np.zeros((3, n_elem)),
        directors=directors,
        radius=np.full(n_elem, radius),
        mass_second_moment_of_inertia=mass_inertia,
        inv_mass_second_moment_of_inertia=inv_mass_inertia,
        shear_matrix=shear_matrix,
        bend_matrix=bend_matrix,
        density_array=np.full(n_elem, density),
        volume=volumes,
        mass=mass,
        internal_forces=np.zeros((3, n_nodes)),
        internal_torques=np.zeros((3, n_elem)),
        external_forces=np.zeros((3, n_nodes)),
        external_torques=np.zeros((3, n_elem)),
        lengths=rest_lengths,
        rest_lengths=rest_lengths.copy(),
        tangents=tangents.copy(),
        dilatation=np.ones(n_elem),
        dilatation_rate=np.zeros(n_elem),
        voronoi_dilatation=np.ones(n_voronoi),
        rest_voronoi_lengths=rest_voronoi_lengths.copy(),
        sigma=np.zeros((3, n_elem)),
        kappa=initial_kappa.copy(),
        rest_sigma=np.zeros((3, n_elem)),
        rest_kappa=initial_kappa.copy(),
        internal_stress=np.zeros((3, n_elem)),
        internal_couple=np.zeros((3, n_voronoi)),
        ring_rod_flag=False,
    )
    spiral_sim.append(spiral_rod)
    
    # CosseratRod 생성자가 kappa와 sigma를 재계산하므로, rest 값도 동기화
    # (생성자가 sigma와 kappa를 기하학적 형태로 덮어쓰지만 rest_*는 입력값을 유지함)
    spiral_rod.rest_kappa = spiral_rod.kappa.copy()
    spiral_rod.rest_sigma = spiral_rod.sigma.copy()
    # 내부 응력/커플을 0으로 재설정 (strain = kappa - rest_kappa = 0)
    spiral_rod.internal_stress.fill(0.0)
    spiral_rod.internal_couple.fill(0.0)

    # 헤드 바디와 조인트는 제거됨 (FixedJoint 호환성 문제)
    # 단순히 나선형 막대만 사용하여 추진력 시뮬레이션
    # (몸체의 회전 저항은 RFT 항력으로 대체)
    
    # 4. 외부 힘(RFT, 댐퍼, 토크) 적용
    spiral_sim.add_forcing_to(spiral_rod).using(ResistiveForceTheoryForcing, fluid_viscosity=fluid_viscosity, radius=radius, rod_total_length=total_length)
    
    spiral_sim.dampen(spiral_rod).using(ea.AnalyticalLinearDamper, damping_constant=1e-3, time_step=np.float64(dt))
    
    spiral_sim.add_forcing_to(spiral_rod).using(EndpointTorques, start_torque=np.array([0.0, 0.0, torque_magnitude]))

    # 5. 콜백 기반 데이터 수집
    rod_data = {"time": [], "position": [], "velocity": [], "omega": [], "kappa": [], "sigma": []}
    spiral_sim.collect_diagnostics(spiral_rod).using(BasicDataCollector, step_skip=step_skip, callback_params=rod_data)

    # 6. 실행
    spiral_sim.finalize()
    timestepper = ea.PositionVerlet()

    print(f"시뮬레이션 시작: N={n_elem}, pitch={pitch}, radius={radius}, torque={torque_magnitude}")
    ea.integrate(timestepper, spiral_sim, final_time=total_steps * dt, n_steps=total_steps)
    print("시뮬레이션 완료!")

    # 7. 결과 수집
    # Extract z-velocity history for analytical comparison
    vz_history = []
    for v in rod_data["velocity"]:
        vz_history.append(v[2, :].mean())

    # Extract omega z-history for analytical comparison
    omega_history = []
    for o in rod_data["omega"]:
        omega_history.append(o)  # keep full (3, n_elems) arrays

    # Build raw simulation result
    result = {
        "time": rod_data["time"],
        "position": rod_data["position"],
        "velocity": rod_data["velocity"],
        "omega": rod_data["omega"],
        "kappa": rod_data["kappa"],
        "sigma": rod_data["sigma"],
        "vz_history": vz_history,
        "omega_history": omega_history,
        "final_velocity": rod_data["velocity"][-1] if rod_data["velocity"] else None,
        "final_time": rod_data["time"][-1] if rod_data["time"] else total_steps * dt,
        "parameters": {
            "n_elem": n_elem,
            "pitch": pitch,
            "radius": radius,
            "total_length": total_length,
            "body_length_ratio": body_length_ratio,
            "body_radius": body_radius,
            "density": density,
            "E": E,
            "nu": nu,
            "fluid_viscosity": fluid_viscosity,
            "dt": dt,
            "total_steps": total_steps,
            "torque_magnitude": torque_magnitude,
        }
    }

    # Compute analytical comparison
    try:
        analysis = analytical_comparison(result, fluid_viscosity=fluid_viscosity)
        result["analytical"] = analysis
        print(f"  Analytical comparison: V_sim={analysis['V_sim']:.6e}, "
              f"V_theory={analysis['V_theory']:.6e}, "
              f"error={analysis['pct_error']:.2f}%")
    except Exception as e:
        print(f"  Analytical comparison skipped: {e}")
        result["analytical"] = None

    # Compute stiffness check
    try:
        stiffness = stiffness_check(result, deformation_threshold=2.0)
        result["stiffness"] = stiffness
        if stiffness["deformation_exceeded"]:
            print(f"  [!] Stiffness check: {stiffness['status']} - {stiffness['recommendation'][:80]}...")
        else:
            print(f"  Stiffness check: {stiffness['status']} (max disp={stiffness['max_displacement_pct']:.6f}%)")
    except Exception as e:
        print(f"  Stiffness check skipped: {e}")
        result["stiffness"] = None

    # CSV time-series logging (optional, non-blocking)
    try:
        # Generate a default filename based on key parameters
        p = result["parameters"]
        csv_name = f"sim_N{p['n_elem']}_pr{p['pitch']/p['radius']:.2f}_T{p['torque_magnitude']:.0e}.csv"
        log_simulation_timeseries(result, filepath=csv_name, torque_magnitude=p['torque_magnitude'])
    except Exception as e:
        print(f"  CSV logging skipped: {e}")

    return result


# ============================================================
# Hypothesis 1: Pitch/Radius (P/R) Ratio Parameter Sweep
# ============================================================
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
            
            if sim_result["final_velocity"] is not None:
                vz_final = sim_result["final_velocity"][2, :]  # z-velocity at all nodes
                
                # Check for NaN/Inf
                has_nan = bool(np.any(np.isnan(vz_final)))
                has_inf = bool(np.any(np.isinf(vz_final)))
                
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
                
                results[pr] = {
                    "pitch": pitch,
                    "vz_final_mean": vz_mean,
                    "vz_com_avg": vz_com,
                    "vz_array": vz_final,
                    "final_velocity": sim_result["final_velocity"],
                    "time": sim_result["time"],
                    "velocity_history": sim_result["velocity"],
                    "parameters": sim_result["parameters"],
                    "has_nan": has_nan if 'has_nan' in dir() else False,
                    "has_inf": has_inf if 'has_inf' in dir() else False,
                    "status": status,
                    "analytical": sim_result.get("analytical"),
                    "efficiency": compute_efficiency(sim_result, torque_magnitude=torque_magnitude),
                }
                print(f"{pr:>8.1f} {pitch:>12.6f} {vz_mean:>15.6e} {vz_com:>15.6e} {status:>10}")
            else:
                results[pr] = {"pitch": pitch, "error": "No velocity data", "status": "NO_DATA"}
                print(f"{pr:>8.1f} {pitch:>12.6f} {'N/A':>15} {'N/A':>15} {'NO DATA':>10}")
                
        except Exception as e:
            results[pr] = {"pitch": pitch, "error": str(e), "status": "EXCEPTION"}
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
            )
            
            if sim_result["final_velocity"] is not None:
                vz_final = sim_result["final_velocity"][2, :]
                
                # Check for NaN/Inf
                has_nan = bool(np.any(np.isnan(vz_final)))
                has_inf = bool(np.any(np.isinf(vz_final)))
                
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
                
                results[br] = {
                    "body_length_ratio": br,
                    "body_length": body_len,
                    "vz_final_mean": vz_mean,
                    "vz_com_avg": vz_com,
                    "vz_array": vz_final,
                    "final_velocity": sim_result["final_velocity"],
                    "time": sim_result["time"],
                    "velocity_history": sim_result["velocity"],
                    "parameters": sim_result["parameters"],
                    "has_nan": has_nan if 'has_nan' in dir() else False,
                    "has_inf": has_inf if 'has_inf' in dir() else False,
                    "status": status,
                }
                print(f"{br:>8.1f}     {body_len:>12.6f} {vz_mean:>15.6e} {vz_com:>15.6e} {status:>10}")
            else:
                results[br] = {"body_length_ratio": br, "error": "No velocity data", "status": "NO_DATA"}
                print(f"{br:>8.1f}     {body_len:>12.6f} {'N/A':>15} {'N/A':>15} {'NO DATA':>10}")
                
        except Exception as e:
            results[br] = {"body_length_ratio": br, "error": str(e), "status": "EXCEPTION"}
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
def compute_efficiency(
    sim_result: dict,
    torque_magnitude: float = None,
) -> dict:
    """
    Compute propulsive efficiency from simulation results.

    Two efficiency metrics are computed:

    1. **Slip efficiency** (eta_slip):
       Ratio of actual swimming speed to the theoretical 'no-slip' speed
       of a rigid screw propeller.
           eta_slip = V_sim / (omega_z * pitch / (2*pi))
       Range: 0 (fully slipping) to 1 (perfect screw).
       This is the kinematic efficiency of the helix.

    2. **Power efficiency** (eta_power):
       Ratio of useful propulsive power (drag force on body * speed)
       to input mechanical power (torque * angular velocity).
           P_out = C_t * V_sim^2 * body_length
           P_in  = |torque_magnitude * omega_z|
           eta_power = P_out / P_in
       This captures the thermodynamic/dissipative efficiency.

    Returns a dict with all intermediate quantities and both efficiencies,
    or None if required data is missing.
    """
    analysis = sim_result.get("analytical")
    params = sim_result.get("parameters", {})

    if analysis is None:
        return None

    V_sim = analysis.get("V_sim", 0.0)
    omega_z = analysis.get("omega_z", 0.0)
    C_t = analysis.get("C_t", 0.0)
    pitch = params.get("pitch", analysis.get("pitch", 0.02))
    total_length = params.get("total_length", 0.1)
    body_length_ratio = params.get("body_length_ratio", 0.5)
    body_length = body_length_ratio * total_length

    if torque_magnitude is None:
        torque_magnitude = params.get("torque_magnitude", 1e-8)

    abs_omega = abs(omega_z) if omega_z is not None else 0.0

    # ---- Metric 1: Slip efficiency (kinematic) ----
    noslip_speed = abs_omega * pitch / (2.0 * np.pi)  # V_max = omega * P / 2pi
    if noslip_speed > 1e-30:
        eta_slip = abs(V_sim) / noslip_speed
    else:
        eta_slip = 0.0

    # ---- Metric 2: Power efficiency (thermodynamic) ----
    # Input power: torque * angular velocity
    P_in = abs(torque_magnitude * abs_omega) if torque_magnitude is not None else 0.0

    # Output power: drag force on body * swimming speed
    # The straight body section (length = body_length) moves at V_sim,
    # experiencing tangential RFT drag: F_drag_body = C_t * V_sim * body_length
    # The propeller thrust balances this drag at steady state.
    P_out = C_t * V_sim**2 * body_length if C_t > 0 else 0.0

    if P_in > 1e-30:
        eta_power = P_out / P_in
    else:
        eta_power = 0.0

    # ---- Additional info ----
    # Input power density (per unit tail length)
    tail_length = total_length - body_length
    P_in_density = P_in / tail_length if tail_length > 0 else 0.0

    # Propulsive force (thrust)
    F_thrust = C_t * V_sim * body_length if C_t > 0 else 0.0

    return {
        "eta_slip": eta_slip,                # kinematic efficiency
        "eta_power": eta_power,              # power efficiency
        "V_sim": V_sim,                      # swimming speed (m/s)
        "omega_z": omega_z,                  # angular velocity (rad/s)
        "noslip_speed": noslip_speed,        # V_max = omega*P/2pi (m/s)
        "P_in": P_in,                        # input mechanical power (W)
        "P_out": P_out,                      # useful propulsive power (W)
        "F_thrust": F_thrust,                # estimated thrust (N)
        "C_t": C_t,                          # tangential drag coefficient
        "body_length": body_length,          # body section length (m)
        "tail_length": tail_length,          # tail section length (m)
        "pitch": pitch,
    }


def plot_efficiency_curve(
    sweep_results: dict,
    x_key: str = "pitch_over_radius",
    save_path: str = None,
    show_plot: bool = True,
):
    """
    Plot efficiency metrics against P/R ratio (or other sweep parameter).

    Parameters
    ----------
    sweep_results : dict
        Results from parameter_sweep_h1() or similar, keyed by parameter value.
        Each entry must contain 'efficiency' dict (from compute_efficiency).
    x_key : str
        Label for x-axis. Default 'pitch_over_radius' (P/R).
    save_path : str, optional
        File path to save the figure. If None, figure is not saved.
    show_plot : bool
        Whether to display the plot interactively (default True).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[!] matplotlib not installed. Cannot generate plot.")
        return

    # Collect valid data points (status == OK with efficiency data)
    x_vals = []
    eta_slip_vals = []
    eta_power_vals = []
    labels = []

    for key in sorted(sweep_results.keys()):
        data = sweep_results[key]
        if data.get("status") != "OK":
            continue
        eff = data.get("efficiency")
        if eff is None:
            continue
        x_vals.append(float(key))
        eta_slip_vals.append(eff["eta_slip"])
        eta_power_vals.append(eff["eta_power"])
        labels.append(str(key))

    if len(x_vals) < 2:
        print("[!] Insufficient data points for efficiency curve (< 2).")
        return

    x_arr = np.array(x_vals)
    slip_arr = np.array(eta_slip_vals)
    power_arr = np.array(eta_power_vals)

    # ---- Find optimal peaks ----
    # Slip efficiency peak
    idx_slip_peak = int(np.argmax(slip_arr))
    peak_pr_slip = x_arr[idx_slip_peak]
    peak_eta_slip = slip_arr[idx_slip_peak]

    # Power efficiency peak
    idx_power_peak = int(np.argmax(power_arr))
    peak_pr_power = x_arr[idx_power_peak]
    peak_eta_power = power_arr[idx_power_peak]

    # ---- Create figure ----
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

    # --- Top panel: Slip efficiency ---
    ax1.plot(x_arr, slip_arr, 'o-', color='#1f77b4', linewidth=2, markersize=8)
    ax1.axvline(peak_pr_slip, color='#1f77b4', linestyle='--', alpha=0.5,
                label=f'Peak: P/R={peak_pr_slip:.2f}, eta={peak_eta_slip:.4f}')
    ax1.plot(peak_pr_slip, peak_eta_slip, 'D', color='#d62728', markersize=12)

    ax1.set_ylabel('Slip Efficiency  eta_slip = V / (omega*P/2pi)', fontsize=12)
    ax1.set_title('Efficiency vs P/R Ratio (Hypothesis 1)', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=10)

    # Annotate each point with P/R value
    for i, (x, y) in enumerate(zip(x_arr, slip_arr)):
        ax1.annotate(f'{x:.1f}', (x, y), textcoords="offset points",
                     xytext=(0, 10), fontsize=8, ha='center')

    # --- Bottom panel: Power efficiency ---
    ax2.plot(x_arr, power_arr, 's-', color='#2ca02c', linewidth=2, markersize=8)
    ax2.axvline(peak_pr_power, color='#2ca02c', linestyle='--', alpha=0.5,
                label=f'Peak: P/R={peak_pr_power:.2f}, eta={peak_eta_power:.6f}')
    ax2.plot(peak_pr_power, peak_eta_power, 'D', color='#d62728', markersize=12)

    ax2.set_xlabel('Pitch / Radius  (P/R) Ratio', fontsize=12)
    ax2.set_ylabel('Power Efficiency  eta = P_out / P_in', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=10)

    for i, (x, y) in enumerate(zip(x_arr, power_arr)):
        ax2.annotate(f'{x:.1f}', (x, y), textcoords="offset points",
                     xytext=(0, 10), fontsize=8, ha='center')

    plt.tight_layout()

    # ---- Save figure ----
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"[OK] Figure saved to: {save_path}")

    # ---- Print summary ----
    print("\n" + "=" * 70)
    print("EFFICIENCY CURVE RESULTS")
    print("=" * 70)
    print(f"  Optimal P/R (slip efficiency):  {peak_pr_slip:.2f}  (eta_slip = {peak_eta_slip:.4f})")
    print(f"  Optimal P/R (power efficiency): {peak_pr_power:.2f}  (eta_power = {peak_eta_power:.6f})")
    print("-" * 70)
    print(f"  {'P/R':>8} {'eta_slip':>12} {'eta_power':>14}")
    print("-" * 70)
    for i in range(len(x_arr)):
        print(f"  {x_arr[i]:>8.1f} {slip_arr[i]:>12.6f} {power_arr[i]:>14.8f}")
    print("=" * 70)

    if show_plot:
        plt.show()
    else:
        plt.close(fig)


def efficiency_curve_analysis(
    radius: float = 0.01,
    total_length: float = 0.1,
    n_elem: int = 40,
    pr_values: list = None,
    torque_magnitude: float = 1e-7,
    dt: float = 1e-5,
    total_steps: int = 5000,
    step_skip: int = 50,
    fluid_viscosity: float = 0.1,
    density: float = 1000.0,
    E: float = 1e7,
    nu: float = 0.5,
    body_length_ratio: float = 0.5,
    save_plot: bool = True,
    show_plot: bool = True,
    plot_filename: str = "efficiency_curve.png",
) -> dict:
    """
    Full efficiency curve analysis:
      1. Run parameter_sweep_h1() over P/R ratios
      2. Efficiency is computed inside the sweep (via compute_efficiency)
      3. Plot and report the optimal P/R ratio

    Returns the sweep_results dict with efficiency data included.
    """
    # Run the H1 sweep (efficiency is computed per data point in the sweep)
    sweep_results = parameter_sweep_h1(
        radius=radius,
        total_length=total_length,
        n_elem=n_elem,
        pr_values=pr_values,
        torque_magnitude=torque_magnitude,
        dt=dt,
        total_steps=total_steps,
        step_skip=step_skip,
        fluid_viscosity=fluid_viscosity,
        density=density,
        E=E,
        nu=nu,
        body_length_ratio=body_length_ratio,
    )

    # Plot the efficiency curve
    plot_efficiency_curve(
        sweep_results,
        save_path=plot_filename if save_plot else None,
        show_plot=show_plot,
    )

    return sweep_results


# ============================================================
# CSV Data Logger Module (TAS-9)
# Export simulation data to CSV files using pandas
# ============================================================
def log_simulation_timeseries(
    sim_result: dict,
    filepath: str = "simulation_timeseries.csv",
    torque_magnitude: float = None,
) -> str:
    """
    Export time-history data from a single simulation to a CSV file.
    
    Columns:
        - Time (s)
        - Vz_mean (m/s) : mean z-velocity of all nodes at each recorded step
        - Omega_z (rad/s) : mean angular velocity z-component
        - Input_Torque (Nm) : applied torque magnitude
        - Power_Efficiency : P_out / P_in at each recorded step
        - Theoretical_Error (%) : (V_theory - V_sim) / |V_sim| * 100
    
    Returns the filepath of the saved CSV, or None on failure.
    """
    import pandas as pd
    
    time_list = sim_result.get("time", [])
    vel_list = sim_result.get("velocity", [])
    omega_list = sim_result.get("omega", [])
    params = sim_result.get("parameters", {})
    analysis = sim_result.get("analytical")
    
    if torque_magnitude is None:
        torque_magnitude = params.get("torque_magnitude", 0.0)
    
    if not time_list or not vel_list:
        print(f"[!] CSV timeseries: insufficient data (times={len(time_list)}, vels={len(vel_list)})")
        return None
    
    # Compute Vz at each recorded time
    vz_series = []
    for v in vel_list:
        vz_series.append(float(v[2, :].mean()))
    
    # Compute omega_z at each recorded time
    omega_z_series = []
    for o in omega_list:
        omega_z_series.append(float(o[2, :].mean()) if o.shape[0] >= 3 else 0.0)
    
    # Compute power efficiency at each time step
    # Uses the same formula as compute_efficiency
    C_t = analysis.get("C_t", 0.0) if analysis else 0.0
    body_length = params.get("body_length_ratio", 0.5) * params.get("total_length", 0.1)
    pitch = params.get("pitch", 0.02)
    
    # For theoretical error, use steady-state analytical comparison
    theoretical_error = analysis.get("pct_error", float('nan')) if analysis else float('nan')
    V_theory = analysis.get("V_theory", float('nan')) if analysis else float('nan')
    
    rows = []
    for i in range(len(time_list)):
        t = time_list[i]
        vz = vz_series[i] if i < len(vz_series) else float('nan')
        omz = omega_z_series[i] if i < len(omega_z_series) else float('nan')
        
        # Power efficiency at this instant
        P_in = abs(torque_magnitude * abs(omz)) if torque_magnitude and abs(omz) > 1e-30 else 0.0
        P_out = C_t * vz**2 * body_length if C_t > 0 else 0.0
        eta_power = P_out / P_in if P_in > 1e-30 else 0.0
        
        rows.append({
            "Time": t,
            "Vz_mean": vz,
            "Omega_z": omz,
            "Input_Torque": torque_magnitude,
            "Power_Efficiency": eta_power,
            "Theoretical_Error": theoretical_error,
            "V_theory": V_theory,
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False, encoding='utf-8')
    print(f"[OK] CSV timeseries saved: {filepath} ({len(rows)} rows)")
    return filepath


def log_sweep_summary(
    sweep_results: dict,
    filepath: str = "sweep_summary.csv",
    sweep_type: str = "h1",
) -> str:
    """
    Export parameter sweep summary to a CSV file.
    
    For H1 sweeps (P/R ratio), columns:
        - P/R, Pitch, Vz_final_mean, Vz_com_avg, Status
        - Eta_slip, Eta_power, Theoretical_Error
    
    For H2 sweeps (Body/Tail ratio), columns:
        - Body_Length_Ratio, Body_Length, Vz_final_mean, Vz_com_avg, Status
        - Theoretical_Error
    
    Returns the filepath of the saved CSV, or None on failure.
    """
    import pandas as pd
    
    if not sweep_results:
        print("[!] CSV sweep summary: no data")
        return None
    
    rows = []
    for key in sorted(sweep_results.keys()):
        data = sweep_results[key]
        status = data.get("status", "?")
        row = {"Status": status}
        
        if sweep_type in ("h1", "pr"):
            row["P/R"] = float(key)
            row["Pitch"] = data.get("pitch", float('nan'))
        elif sweep_type in ("h2", "body"):
            row["Body_Length_Ratio"] = float(key)
            row["Body_Length"] = data.get("body_length", float('nan'))
        else:
            row["Param"] = float(key)
        
        row["Vz_final_mean"] = data.get("vz_final_mean", float('nan'))
        row["Vz_com_avg"] = data.get("vz_com_avg", float('nan'))
        
        # Analytical / efficiency info
        analysis = data.get("analytical")
        if analysis is not None:
            row["Theoretical_Error"] = analysis.get("pct_error", float('nan'))
            row["V_theory"] = analysis.get("V_theory", float('nan'))
            row["V_sim"] = analysis.get("V_sim", float('nan'))
            row["Cn_over_Ct"] = analysis.get("Cn_over_Ct", float('nan'))
        else:
            row["Theoretical_Error"] = float('nan')
        
        eff = data.get("efficiency")
        if eff is not None:
            row["Eta_slip"] = eff.get("eta_slip", float('nan'))
            row["Eta_power"] = eff.get("eta_power", float('nan'))
            row["P_in"] = eff.get("P_in", float('nan'))
            row["P_out"] = eff.get("P_out", float('nan'))
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False, encoding='utf-8')
    print(f"[OK] CSV sweep summary saved: {filepath} ({len(rows)} entries)")
    return filepath


def log_all_sweep_data(
    sweep_results: dict,
    base_filename: str = "sweep",
    sweep_type: str = "h1",
) -> dict:
    """
    Convenience function: exports both summary CSV for a sweep and
    per-parameter-set time-series CSVs.
    
    Returns dict of {file_key: filepath} for all saved files.
    """
    saved = {}
    
    # Summary CSV
    summary_path = f"{base_filename}_summary.csv"
    result = log_sweep_summary(sweep_results, summary_path, sweep_type)
    if result:
        saved["summary"] = result
    
    # Per-parameter time-series CSVs
    for key in sorted(sweep_results.keys()):
        data = sweep_results[key]
        if data.get("status") != "OK":
            continue
        # Reconstruct a sim_result-like dict from sweep data
        sim_like = {
            "time": data.get("time", []),
            "velocity": data.get("velocity_history", []),
            "omega": data.get("velocity_history", []),  # approximated
            "parameters": data.get("parameters", {}),
            "analytical": data.get("analytical"),
        }
        # Use omega from analytical if available
        analysis = data.get("analytical")
        if analysis and analysis.get("omega_z") is not None:
            # We don't have per-step omega in sweep results, skip timeseries
            pass
        
        pr = float(key)
        ts_path = f"{base_filename}_pr{pr:.2f}_timeseries.csv"
        ts_result = log_simulation_timeseries(sim_like, ts_path)
        if ts_result:
            saved[f"ts_pr{pr:.2f}"] = ts_result
    
    return saved


# ============================================================
# N-Convergence Test Module (TAS-8)
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

                has_nan = bool(np.any(np.isnan(vz_final)))
                has_inf = bool(np.any(np.isinf(vz_final)))

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

            results[N] = {
                "vz_final_mean": vz_mean,
                "vz_com_avg": vz_com,
                "final_velocity": sim_result.get("final_velocity"),
                "velocity_history": sim_result.get("velocity"),
                "time": sim_result.get("time"),
                "parameters": sim_result.get("parameters"),
                "has_nan": has_nan if 'has_nan' in dir() else False,
                "has_inf": has_inf if 'has_inf' in dir() else False,
                "status": status,
            }
            print(f"{N:>10d} {vz_mean:>18.6e} {vz_com:>18.6e} {status:>12}")

        except Exception as e:
            results[N] = {"vz_final_mean": float('nan'), "vz_com_avg": float('nan'),
                          "status": "EXCEPTION", "error": str(e)}
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
                results[N]["status"] = "INCONSISTENT"
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


if __name__ == "__main__":
    import sys
    
    # Check if we should run a single test, sweep, or both
    mode = "sweep"  # default: run sweep h1
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    
    if mode == "single":
        # 기본값으로 단일 시뮬레이션 실행
        results = run_simulation()
        print(f"최종 속도 (z-성분): {results['final_velocity'][2, :].mean():.6e} m/s" if results['final_velocity'] is not None else "속도 데이터 없음")
    
    elif mode == "sweep" or mode == "sweep_h1":
        # Hypothesis 1: P/R ratio sweep
        sweep_results = parameter_sweep_h1()
        
        # Print summary of findings
        print("\n")
        print("=" * 70)
        print("HYPOTHESIS 1 SUMMARY: Propulsion Velocity vs P/R Ratio")
        print("=" * 70)
        print(f"{'P/R':>8} {'Pitch (m)':>12} {'Vz_final':>15} {'Vz_com_avg':>15} {'Status':>12}")
        print("-" * 70)
        for pr in sorted(sweep_results.keys()):
            data = sweep_results[pr]
            status = data.get("status", "?")
            if "vz_final_mean" in data:
                vz_final = data["vz_final_mean"]
                vz_com = data["vz_com_avg"]
                print(f"{pr:>8.1f} {data['pitch']:>12.6f} {vz_final:>15.6e} {vz_com:>15.6e} {status:>12}")
            else:
                print(f"{pr:>8.1f} {data.get('pitch', 0):>12.6f} {'N/A':>15} {'N/A':>15} {status:>12}")
        print("=" * 70)
        
        # Return results for programmatic access
        print(f"\nSweep complete. {sum(1 for d in sweep_results.values() if d.get('status') == 'OK')}/{len(sweep_results)} runs stable.")
    
    elif mode == "sweep_h2":
        # Hypothesis 2: Body-to-Tail length ratio sweep
        sweep_results = parameter_sweep_h2()
        
        # Print summary of findings
        print("\n")
        print("=" * 70)
        print("HYPOTHESIS 2 SUMMARY: Propulsion Velocity vs Body/Tail Ratio")
        print("=" * 70)
        print(f"{'Body/Tail':>10} {'BodyLen(m)':>12} {'Vz_final':>15} {'Vz_com_avg':>15} {'Status':>12}")
        print("-" * 70)
        for br in sorted(sweep_results.keys()):
            data = sweep_results[br]
            status = data.get("status", "?")
            if "vz_final_mean" in data:
                vz_final = data["vz_final_mean"]
                vz_com = data["vz_com_avg"]
                print(f"{br:>8.1f}     {data['body_length']:>12.6f} {vz_final:>15.6e} {vz_com:>15.6e} {status:>12}")
            else:
                print(f"{br:>8.1f}     {data.get('body_length', 0):>12.6f} {'N/A':>15} {'N/A':>15} {status:>12}")
        print("=" * 70)
        
        print(f"\nSweep complete. {sum(1 for d in sweep_results.values() if d.get('status') == 'OK')}/{len(sweep_results)} runs stable.")
    
    elif mode == "convergence" or mode == "n_convergence":
        # N-Convergence Test
        conv_results = n_convergence_test()
        print(f"\nConvergence achieved: {conv_results['convergence_achieved']}")
        print(f"Convergence error: {conv_results['convergence_error_pct']:.4f}%")
        print(f"Recommended N: {conv_results['recommended_n']}")

    elif mode == "analytical":
        # Run single simulation + full analytical comparison
        print("=" * 70)
        print("Analytical Comparison: Simulation vs Purcell Slender Body Theory")
        print("=" * 70)

        # Run simulation with higher resolution for accuracy
        results = run_simulation(
            n_elem=60,
            pitch=0.02,
            radius=0.01,
            total_length=0.1,
            body_length_ratio=0.5,
            torque_magnitude=1e-7,
            total_steps=10000,
            step_skip=50,
        )

        analysis = results.get("analytical")
        if analysis:
            params = results.get("parameters", {})
            p = params.get("pitch", analysis.get('pitch', 0.02))
            r = params.get("radius", analysis.get('radius', 0.01))

            print("\n" + "=" * 70)
            print("COMPARISON RESULTS")
            print("=" * 70)
            print(f"  Geometry:")
            print(f"    Pitch (P):            {p:.6f} m")
            print(f"    Radius (R):           {r:.6f} m")
            print(f"    P/R ratio:            {p/r:.4f}")
            print(f"  Fluid & RFT Coefficients:")
            print(f"    C_t (tangential):     {analysis['C_t']:.6e} N·s/m²")
            print(f"    C_n (normal):         {analysis['C_n']:.6e} N·s/m²")
            print(f"    C_n / C_t:            {analysis['Cn_over_Ct']:.4f}")
            print(f"    Log term (ln(2L/a)):  {analysis['log_term']:.4f}")
            print(f"  Angular Velocity:")
            print(f"    ω_z (measured):       {analysis['omega_z']:.6e} rad/s")
            print(f"  Propulsion Velocity:")
            print(f"    V_sim (simulated):    {analysis['V_sim']:.6e} m/s")
            print(f"    V_theory (RFT):       {analysis['V_theory']:.6e} m/s")
            print(f"    V_slender (Cn=2Ct):   {analysis['V_slender_limit']:.6e} m/s")
            print(f"    Error (theory-sim)/sim: {analysis['pct_error']:.2f}%")
            print("=" * 70)

            # Check if error is reasonable
            if abs(analysis['pct_error']) < 50:
                print("[OK] RFT theory and simulation agree within 50%.")
            else:
                print("Large discrepancy between RFT theory and simulation.")
                print("  Possible causes: non-steady-state, body drag effects,"
                      "  or numerical resolution issues.")
        else:
            print("Analytical comparison not available.")

    elif mode == "stiffness":
        # Stiffness Check: run simulation and report structural deformation
        print("=" * 70)
        print("Stiffness Check: Helical Tail Deformation Analysis")
        print("=" * 70)

        # Run with moderate torque and resolution
        results = run_simulation(
            n_elem=40,
            pitch=0.02,
            radius=0.01,
            total_length=0.1,
            body_length_ratio=0.5,
            torque_magnitude=1e-6,
            total_steps=5000,
            step_skip=50,
        )

        stiffness = results.get("stiffness")
        if stiffness:
            print("\n" + "=" * 70)
            print("STIFFNESS CHECK RESULTS")
            print("=" * 70)
            print(f"  Max displacement / total_length:  {stiffness['max_displacement_pct']:.6e} %")
            if stiffness['pitch_deformation_pct'] is not None:
                print(f"  Pitch deformation (mean):          {stiffness['pitch_deformation_pct']:.6e} %")
            if stiffness['max_pitch_deviation_pct'] is not None:
                print(f"  Max local pitch deviation:          {stiffness['max_pitch_deviation_pct']:.6e} %")
            print(f"  Worst metric:                       {stiffness['worst_metric_pct']:.6e} %")
            print(f"  Threshold:                          2.0 %")
            print(f"  Status:                             {stiffness['status']}")
            print(f"  Recommendation:                     {stiffness['recommendation']}")
            print("=" * 70)

            if stiffness['deformation_exceeded']:
                print("\n[!] Deformation detected - consider increasing Young's Modulus (E).")
            else:
                print("\n[OK] Structural integrity is sufficient for current parameters.")
        else:
            print("Stiffness check not available.")

    elif mode == "calibrate_stiffness" or mode == "calibrate":
        # Stiffness Calibration: sweep E values to find minimum safe stiffness
        print("=" * 70)
        print("Stiffness Calibration: Sweep Young's Modulus for Elastic Integrity")
        print("=" * 70)

        calib_results = stiffness_calibration(
            torque_magnitude=1e-6,
            n_elem=40,
            total_steps=5000,
            step_skip=50,
        )

        # Print final recommendation
        rec_E = calib_results["recommended_E"]
        rec_G = calib_results["recommended_G"]
        print(f"\nFinal recommendation:")
        print(f"  Young's Modulus (E): {rec_E:.2e} Pa")
        print(f"  Shear Modulus (G):   {rec_G:.2e} Pa")
        if calib_results["all_deformed"]:
            print(f"  [!] Even the highest tested E produced >2% deformation.")
            print(f"  [!] Use E >= {rec_E:.2e} Pa for this torque level.")
        elif calib_results["all_ok"]:
            print(f"  Note: All E values produced <2% deformation for torque=1e-6 Nm.")
            print(f"  The default E=1e7 Pa is more than sufficient.")
        else:
            print(f"  Threshold crossed at E = {calib_results['threshold_crossed']:.2e} Pa")
            print(f"  Recommended: use E = {rec_E:.2e} Pa with 2x safety margin.")

    elif mode == "efficiency" or mode == "eff":
        # Efficiency Curve Generation: sweep P/R ratios and plot efficiency
        print("=" * 70)
        print("Efficiency Curve: Propulsive Efficiency vs P/R Ratio")
        print("=" * 70)

        sweep_results = efficiency_curve_analysis(
            n_elem=40,
            torque_magnitude=1e-7,
            total_steps=5000,
            step_skip=50,
            plot_filename="efficiency_curve.png",
            show_plot=True,
        )

        # Print efficiency summary table
        print("\n")
        print("=" * 70)
        print("EFFICIENCY SUMMARY")
        print("=" * 70)
        header = f"{'P/R':>8} {'V_sim':>14} {'eta_slip':>12} {'eta_power':>14} {'Status':>10}"
        print(header)
        print("-" * 70)
        for pr in sorted(sweep_results.keys()):
            data = sweep_results[pr]
            status = data.get("status", "?")
            eff = data.get("efficiency")
            if eff is not None:
                vsim = eff["V_sim"]
                eslip = eff["eta_slip"]
                epow = eff["eta_power"]
                print(f"{pr:>8.1f} {vsim:>14.6e} {eslip:>12.6f} {epow:>14.8f} {status:>10}")
            else:
                print(f"{pr:>8.1f} {'N/A':>14} {'N/A':>12} {'N/A':>14} {status:>10}")
        print("=" * 70)

    elif mode == "csv" or mode == "log":
        # CSV Data Logger: run single simulation and export CSV
        print("=" * 70)
        print("CSV Data Logger: Export simulation data to CSV")
        print("=" * 70)
        
        results = run_simulation(
            n_elem=40,
            pitch=0.02,
            radius=0.01,
            total_length=0.1,
            body_length_ratio=0.5,
            torque_magnitude=1e-7,
            total_steps=5000,
            step_skip=50,
        )
        
        # The timeseries CSV is saved automatically inside run_simulation
        # Also save a separate clean copy
        try:
            extra_path = "simulation_export.csv"
            log_simulation_timeseries(results, filepath=extra_path, torque_magnitude=1e-7)
            print(f"\n[OK] CSV export complete.")
            
            # Print what was saved
            p = results["parameters"]
            default_csv = f"sim_N{p['n_elem']}_pr{p['pitch']/p['radius']:.2f}_T{p['torque_magnitude']:.0e}.csv"
            print(f"  Auto-saved: {default_csv}")
            print(f"  Extra copy: {extra_path}")
        except Exception as e:
            print(f"[!] CSV export error: {e}")

    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python spiral_sim.py [single|sweep|sweep_h1|sweep_h2|convergence|analytical|stiffness|calibrate|efficiency|csv|log]")
