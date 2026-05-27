import numpy as np
import elastica as ea

from .analysis_metrics import build_common_result_summary
from .callbacks import BasicDataCollector
from .efficiency import compute_efficiency
from .forces import EndpointTorques, ResistiveForceTheoryForcing
from .geometry import build_body_helical_geometry
from .logging_utils import log_simulation_timeseries
from .stiffness import stiffness_check
from .theory import analytical_comparison

DAMPING_MODEL = "PYELASTICA_ANALYTICAL_LINEAR_DAMPER_DEPRECATED_DAMPING_CONSTANT"
DAMPING_CONSTANT = 1e-3

class SpiralRodSimulator(
    ea.BaseSystemCollection, 
    ea.Forcing, 
    ea.Constraints, 
    ea.CallBacks, 
    ea.Connections, 
    ea.Damping
):
    pass

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
    geometry = build_body_helical_geometry(
        n_elem=n_elem,
        pitch=pitch,
        radius=radius,
        total_length=total_length,
        body_length_ratio=body_length_ratio,
        body_radius=body_radius,
        density=density,
        E=E,
        nu=nu,
    )
    n_nodes = geometry["n_nodes"]
    n_voronoi = geometry["n_voronoi"]
    body_radius = geometry["body_radius"]
    positions = geometry["positions"]
    tangents = geometry["tangents"]
    rest_lengths = geometry["rest_lengths"]
    directors = geometry["directors"]
    shear_matrix = geometry["shear_matrix"]
    bend_matrix = geometry["bend_matrix"]
    volumes = geometry["volumes"]
    mass = geometry["mass"]
    mass_inertia = geometry["mass_inertia"]
    inv_mass_inertia = geometry["inv_mass_inertia"]
    rest_voronoi_lengths = geometry["rest_voronoi_lengths"]
    initial_kappa = geometry["initial_kappa"]

    # 1. 시스템 컬렉션 생성
    spiral_sim = SpiralRodSimulator()
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
    
    spiral_sim.dampen(spiral_rod).using(
        ea.AnalyticalLinearDamper,
        damping_constant=DAMPING_CONSTANT,
        time_step=np.float64(dt),
    )
    
    spiral_sim.add_forcing_to(spiral_rod).using(EndpointTorques, start_torque=np.array([0.0, 0.0, torque_magnitude]))

    # 5. 콜백 기반 데이터 수집
    rod_data = {
        "time": [],
        "position": [],
        "velocity": [],
        "omega": [],
        "omega_z": [],
        "applied_torque_global_z_projection": [],
        "applied_torque_axis_alignment": [],
        "damping_torque_global_z": [],
        "kappa": [],
        "sigma": [],
    }
    spiral_sim.collect_diagnostics(spiral_rod).using(
        BasicDataCollector,
        step_skip=step_skip,
        callback_params=rod_data,
        applied_torque_material=np.array([0.0, 0.0, torque_magnitude]),
        damping_constant=DAMPING_CONSTANT,
    )

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
    omega_z_history = list(rod_data["omega_z"])

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
        "omega_z_history": omega_z_history,
        "applied_torque_global_z_projection_history": list(
            rod_data["applied_torque_global_z_projection"]
        ),
        "applied_torque_axis_alignment_history": list(
            rod_data["applied_torque_axis_alignment"]
        ),
        "damping_torque_global_z_history": list(rod_data["damping_torque_global_z"]),
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
            "damping_model": DAMPING_MODEL,
            "damping_constant": DAMPING_CONSTANT,
            "rotational_damping_mass": float(np.sum(mass)),
            "damping_estimate_status": "PROJECTED_ELEMENTWISE_DEPRECATED_DAMPER_EQUIVALENT",
        }
    }

    # Compute analytical comparison
    try:
        analysis = analytical_comparison(result, fluid_viscosity=fluid_viscosity)
        result["analytical"] = analysis
        result["omega_sim"] = analysis.get("omega_sim")
        result["omega_z_avg"] = analysis.get("omega_sim")
        result["omega_theory"] = analysis.get("omega_theory")
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

    # Summarize result validity and analysis outputs without changing model calculations.
    try:
        result["efficiency"] = compute_efficiency(result, torque_magnitude=torque_magnitude)
    except Exception as e:
        print(f"  Efficiency summary skipped: {e}")
        result["efficiency"] = None
    result.update(
        build_common_result_summary(
            analytical=result.get("analytical"),
            efficiency=result.get("efficiency"),
            stiffness=result.get("stiffness"),
            status="OK",
            raw_velocity=result.get("velocity"),
        )
    )
    if result.get("analytical"):
        print(
            "  Analysis summary: "
            f"V_sim={result['V_sim']:.6e}, "
            f"V_theory={result['V_theory']:.6e}, "
            f"omega_sim={result['omega_sim']}, "
            f"omega_theory={result['omega_theory']}, "
            f"pct_vs_theory={result['pct_error_vs_theory']}, "
            f"pct_vs_sim={result['pct_error_vs_sim']}, "
            f"error_status={result['error_status']}, "
            f"steady_state={result['steady_state_status']}, "
            f"torque_rot/applied={result['torque_rotational_to_applied_ratio']}, "
            f"torque_coupling/applied={result['torque_coupling_to_applied_ratio']}, "
            f"torque_resid/applied={result['torque_residual_to_applied_ratio']}, "
            f"body_rot_frac={result['body_rotational_fraction']}, "
            f"helix_rot_frac={result['helix_rotational_fraction']}, "
            f"effective_D_ratio={result['effective_D_ratio']}, "
            f"frames={result['torque_frame_assumption']}/{result['omega_frame']}, "
            f"damping/applied={result['damping_torque_to_applied_ratio']}, "
            f"resid_with_damping/applied={result['torque_balance_with_damping_residual_ratio']}, "
            f"torque_interp={result['torque_balance_interpretation']}, "
            f"failure_reason={result['failure_reason']}, "
            f"invalid={result['invalid_result']}"
        )

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

