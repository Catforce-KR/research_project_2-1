"""Analytical RFT approximations for the torque-driven helical rod model."""

from __future__ import annotations

import math

import numpy as np

from .analysis_metrics import compute_error_metrics, compute_steady_state_metrics


EPS = 1e-30


def _compute_rft_coefficients(
    characteristic_length: float,
    filament_radius: float,
    fluid_viscosity: float,
) -> dict:
    """Use the same local RFT coefficient definition as numerical forcing."""
    log_arg = 2.0 * characteristic_length / filament_radius
    log_term = np.log(log_arg) if log_arg > 1.0 else 0.0
    C_t = 2.0 * np.pi * fluid_viscosity / (log_term - 0.5)
    C_n = 4.0 * np.pi * fluid_viscosity / (log_term + 0.5)
    return {
        "C_t": C_t,
        "C_n": C_n,
        "Cn_over_Ct": C_n / C_t if C_t != 0 else float("inf"),
        "log_term": log_term,
    }


def compute_helix_geometry(
    pitch: float,
    radius: float,
    total_length: float,
    body_length_ratio: float = 0.5,
) -> dict:
    """Return continuous-helix quantities matching ``geometry.py`` definitions.

    ``pitch`` is the axial distance advanced per complete turn, ``radius`` is
    the helix centerline radius, and ``total_length`` is the configured axial
    body-plus-tail span.  The returned helix angle is the pitch angle above
    the transverse plane; it becomes small for tightly wound, low-P/R tails.
    """
    if pitch <= 0.0 or radius <= 0.0 or total_length <= 0.0:
        raise ValueError("pitch, radius, and total_length must be positive")
    if not 0.0 <= body_length_ratio < 1.0:
        raise ValueError("body_length_ratio must be in [0, 1)")

    body_length = body_length_ratio * total_length
    tail_axial_length = total_length - body_length
    turn_arc_length = math.sqrt(pitch**2 + (2.0 * math.pi * radius) ** 2)
    sin_angle = pitch / turn_arc_length
    cos_angle = 2.0 * math.pi * radius / turn_arc_length
    helix_angle = math.atan2(pitch, 2.0 * math.pi * radius)
    tail_contour_length = tail_axial_length / sin_angle
    pitch_over_radius = pitch / radius
    warning = None
    if pitch_over_radius < 1.0 or helix_angle < math.radians(5.0):
        warning = "LOW_PITCH_RATIO"

    return {
        "pitch": pitch,
        "radius": radius,
        "pitch_over_radius": pitch_over_radius,
        "body_length": body_length,
        "tail_axial_length": tail_axial_length,
        "tail_contour_length": tail_contour_length,
        "helix_angle": helix_angle,
        "helix_angle_deg": math.degrees(helix_angle),
        "sin_helix_angle": sin_angle,
        "cos_helix_angle": cos_angle,
        "theory_warning": warning,
    }


def compute_rft_resistance_matrix(
    pitch: float,
    radius: float,
    total_length: float,
    body_length_ratio: float = 0.5,
    filament_radius: float | None = None,
    fluid_viscosity: float = 0.1,
) -> dict:
    """Build the rigid-tail axial RFT resistance matrix.

    The helical tail relation is written as

        F_z = -A * V + B * omega
        T_z =  B * V - D * omega

    for the handedness constructed in ``geometry.py``.  The coefficient
    calculation uses the same logarithmic local drag model as the numerical
    RFT forcing.
    """
    if filament_radius is None:
        filament_radius = radius
    geometry = compute_helix_geometry(
        pitch=pitch,
        radius=radius,
        total_length=total_length,
        body_length_ratio=body_length_ratio,
    )
    coefficients = _compute_rft_coefficients(
        characteristic_length=total_length,
        filament_radius=filament_radius,
        fluid_viscosity=fluid_viscosity,
    )
    C_t = coefficients["C_t"]
    C_n = coefficients["C_n"]
    sin_angle = geometry["sin_helix_angle"]
    cos_angle = geometry["cos_helix_angle"]
    tail_length = geometry["tail_contour_length"]

    A = tail_length * (C_t * sin_angle**2 + C_n * cos_angle**2)
    B = tail_length * (C_n - C_t) * radius * sin_angle * cos_angle
    D = tail_length * radius**2 * (C_t * cos_angle**2 + C_n * sin_angle**2)
    return {
        **geometry,
        **coefficients,
        "A": A,
        "B": B,
        "D": D,
    }


def estimate_body_drag_coefficients(
    body_length: float,
    body_radius: float,
    C_t: float,
    C_n: float,
) -> dict:
    """Approximate drag of the straight offset body represented in simulation.

    The body is modeled as a straight centerline parallel to the swimming axis
    and offset by ``body_radius``.  Axial translation therefore uses local
    tangential drag while rotation about the swimming axis uses transverse
    drag acting at the offset radius.  This is a slender/cylinder-inspired
    RFT centerline approximation, not a resolved body hydrodynamic model.
    """
    if body_length < 0.0 or body_radius < 0.0:
        raise ValueError("body_length and body_radius must be non-negative")
    return {
        "body_translational_drag": C_t * body_length,
        "body_rotational_drag": C_n * body_length * body_radius**2,
    }


def solve_torque_driven_velocity(
    A: float,
    B: float,
    D: float,
    body_translational_drag: float,
    body_rotational_drag: float,
    torque_magnitude: float,
) -> dict:
    """Solve force-free axial translation and applied-torque balance."""
    A_total = A + body_translational_drag
    D_total = D + body_rotational_drag
    determinant = A_total * D_total - B**2
    if not math.isfinite(determinant) or abs(determinant) <= EPS:
        V_theory = float("nan")
        omega_theory = float("nan")
    else:
        V_theory = B * torque_magnitude / determinant
        omega_theory = A_total * torque_magnitude / determinant
    return {
        "V_theory": V_theory,
        "omega_theory": omega_theory,
        "A_total": A_total,
        "D_total": D_total,
        "resistance_determinant": determinant,
    }


def compute_rotational_resistance_breakdown(
    D: float | None,
    body_rotational_drag: float | None,
    D_total: float,
    eps: float = EPS,
) -> dict:
    """Expose helix/body portions of the existing rotational resistance."""
    helix_fraction = None
    body_fraction = None
    if (
        D is not None
        and body_rotational_drag is not None
        and all(math.isfinite(value) for value in (D, body_rotational_drag, D_total))
    ):
        resistance_scale = max(abs(D_total), eps)
        helix_fraction = D / resistance_scale
        body_fraction = body_rotational_drag / resistance_scale
    return {
        "helix_rotational_resistance": D,
        "total_rotational_resistance": D_total,
        "body_rotational_fraction": body_fraction,
        "helix_rotational_fraction": helix_fraction,
    }


def torque_frame_metadata(
    applied_torque_material_component: float | None = None,
    applied_torque_global_z_projection: float | None = None,
    applied_torque_axis_alignment: float | None = None,
) -> dict:
    """Record torque/omega axis convention and whether projection was observed."""
    projection_available = (
        applied_torque_global_z_projection is not None
        and applied_torque_axis_alignment is not None
        and math.isfinite(applied_torque_global_z_projection)
        and math.isfinite(applied_torque_axis_alignment)
    )
    frame_mismatch_risk = (
        True if not projection_available
        else abs(applied_torque_axis_alignment - 1.0) > 0.05
    )
    return {
        "torque_frame_assumption": "ASSUMED_MATERIAL_COMPONENT_2",
        "omega_frame": "INERTIAL_GLOBAL_Z",
        "torque_axis": "COMPONENT_2_AT_FIRST_ELEMENT",
        "omega_axis": "GLOBAL_Z",
        "torque_sign_convention": "POSITIVE_APPLIED_COMPONENT_2",
        "applied_torque_material_component": applied_torque_material_component,
        "applied_torque_global_z_projection": applied_torque_global_z_projection,
        "applied_torque_axis_alignment": applied_torque_axis_alignment,
        "torque_projection_to_omega_axis": applied_torque_global_z_projection,
        "torque_frame_status": (
            "PROJECTED_TO_GLOBAL_Z" if projection_available
            else "PROJECTION_UNAVAILABLE"
        ),
        "frame_mismatch_risk": frame_mismatch_risk,
    }


def compute_damping_torque_diagnostics(
    torque_balance_residual: float,
    omega_sim: float,
    torque_magnitude: float,
    damping_model: str | None = None,
    damping_constant: float | None = None,
    rotational_damping_mass: float | None = None,
    damping_torque_estimate: float | None = None,
    damping_estimate_status: str | None = None,
    frame_mismatch_risk: bool = True,
    eps: float = EPS,
) -> dict:
    """Estimate the damper share of the measured torque residual.

    For PyElastica's deprecated ``damping_constant`` protocol, the equivalent
    elementwise rotational resisting torque is proportional to element mass
    and angular velocity.  A supplied projected estimate is preferred; using
    total mass times averaged global-z omega remains an explicitly labeled
    approximation.
    """
    applied_scale = max(abs(torque_magnitude), eps) if math.isfinite(torque_magnitude) else None
    missing_fraction = None
    if applied_scale is not None and math.isfinite(torque_balance_residual):
        missing_fraction = abs(torque_balance_residual) / applied_scale
    metrics = {
        "damping_model": damping_model or "UNKNOWN",
        "damping_constant": damping_constant,
        "damping_effective_coefficient": None,
        "rotational_damping_mass": rotational_damping_mass,
        "damping_estimate_status": damping_estimate_status or "UNKNOWN",
        "damping_torque_estimate": None,
        "damping_torque_to_applied_ratio": None,
        "torque_balance_with_damping_residual": None,
        "torque_balance_with_damping_residual_ratio": None,
        "torque_balance_missing_fraction": missing_fraction,
        "torque_balance_interpretation": "INSUFFICIENT_DAMPING_INFO",
    }
    if (
        applied_scale is None
        or not all(math.isfinite(value) for value in (torque_balance_residual, omega_sim))
    ):
        return metrics

    if damping_torque_estimate is None:
        if (
            damping_constant is None
            or rotational_damping_mass is None
            or not all(math.isfinite(value) for value in (damping_constant, rotational_damping_mass))
        ):
            return metrics
        metrics["damping_effective_coefficient"] = damping_constant * rotational_damping_mass
        damping_torque_estimate = metrics["damping_effective_coefficient"] * omega_sim
        metrics["damping_estimate_status"] = (
            damping_estimate_status or "ESTIMATED_FROM_MEAN_GLOBAL_Z_OMEGA"
        )
    elif (
        damping_constant is not None
        and rotational_damping_mass is not None
        and all(math.isfinite(value) for value in (damping_constant, rotational_damping_mass))
    ):
        metrics["damping_effective_coefficient"] = damping_constant * rotational_damping_mass

    if not math.isfinite(damping_torque_estimate):
        return metrics
    residual_with_damping = torque_balance_residual - damping_torque_estimate
    residual_ratio = abs(residual_with_damping) / applied_scale
    metrics.update({
        "damping_torque_estimate": damping_torque_estimate,
        "damping_torque_to_applied_ratio": abs(damping_torque_estimate) / applied_scale,
        "torque_balance_with_damping_residual": residual_with_damping,
        "torque_balance_with_damping_residual_ratio": residual_ratio,
    })
    if residual_ratio <= 0.1:
        metrics["torque_balance_interpretation"] = "DAMPING_DOMINATED"
    elif frame_mismatch_risk:
        metrics["torque_balance_interpretation"] = "FRAME_MISMATCH_POSSIBLE"
    else:
        metrics["torque_balance_interpretation"] = "RFT_ROTATIONAL_RESISTANCE_TOO_SMALL"
    return metrics


def compute_balance_diagnostics(
    V_sim: float,
    omega_sim: float,
    A_total: float,
    B: float,
    D_total: float,
    torque_magnitude: float,
    D: float | None = None,
    body_rotational_drag: float | None = None,
    eps: float = EPS,
) -> dict:
    """Evaluate steady analytical balance equations at simulated averages.

    These residuals diagnose whether the final-window simulated velocity and
    rotation can be compared to the steady rigid-helix analytical solution.
    They do not alter the solved theoretical state or imply that a transient,
    damped, deformable simulation must satisfy the steady equations.
    """
    resistance_breakdown = compute_rotational_resistance_breakdown(
        D=D,
        body_rotational_drag=body_rotational_drag,
        D_total=D_total,
        eps=eps,
    )
    values = (V_sim, omega_sim, A_total, B, D_total, torque_magnitude)
    if not all(math.isfinite(value) for value in values):
        return {
            "force_residual": float("nan"),
            "force_residual_norm": None,
            "torque_residual": float("nan"),
            "torque_residual_norm": None,
            "torque_coupling_term": float("nan"),
            "torque_rotational_resistance_term": float("nan"),
            "torque_applied_term": torque_magnitude,
            "torque_balance_residual": float("nan"),
            "torque_coupling_to_applied_ratio": None,
            "torque_rotational_to_applied_ratio": None,
            "torque_residual_to_applied_ratio": None,
            "effective_rotational_resistance": None,
            "effective_rotational_resistance_ratio": None,
            "effective_D_from_omega_sim": None,
            "effective_D_ratio": None,
            **resistance_breakdown,
        }

    axial_drag = A_total * V_sim
    propulsive_force = B * omega_sim
    force_residual = -axial_drag + propulsive_force
    coupling_torque = B * V_sim
    rotational_drag = D_total * omega_sim
    torque_residual = torque_magnitude + coupling_torque - rotational_drag
    force_scale = abs(axial_drag) + abs(propulsive_force)
    torque_scale = abs(torque_magnitude) + abs(coupling_torque) + abs(rotational_drag)
    applied_scale = max(abs(torque_magnitude), eps)
    effective_rotational_resistance = None
    effective_rotational_resistance_ratio = None
    if abs(omega_sim) > eps:
        effective_rotational_resistance = (
            torque_magnitude + coupling_torque
        ) / omega_sim
        if abs(D_total) > eps:
            effective_rotational_resistance_ratio = (
                effective_rotational_resistance / D_total
            )
    return {
        "force_residual": force_residual,
        "force_residual_norm": abs(force_residual) / max(force_scale, eps),
        "torque_residual": torque_residual,
        "torque_residual_norm": abs(torque_residual) / max(torque_scale, eps),
        "torque_coupling_term": coupling_torque,
        "torque_rotational_resistance_term": rotational_drag,
        "torque_applied_term": torque_magnitude,
        "torque_balance_residual": torque_residual,
        "torque_coupling_to_applied_ratio": abs(coupling_torque) / applied_scale,
        "torque_rotational_to_applied_ratio": abs(rotational_drag) / applied_scale,
        "torque_residual_to_applied_ratio": abs(torque_residual) / applied_scale,
        "effective_rotational_resistance": effective_rotational_resistance,
        "effective_rotational_resistance_ratio": effective_rotational_resistance_ratio,
        "effective_D_from_omega_sim": effective_rotational_resistance,
        "effective_D_ratio": effective_rotational_resistance_ratio,
        **resistance_breakdown,
    }


def _compute_legacy_velocity(
    pitch: float,
    radius: float,
    total_length: float,
    angular_velocity: float,
    filament_radius: float,
    fluid_viscosity: float,
) -> dict:
    """Preserve the previous prescribed-omega, helix-only formula."""
    coefficients = _compute_rft_coefficients(total_length, filament_radius, fluid_viscosity)
    C_t = coefficients["C_t"]
    C_n = coefficients["C_n"]
    denominator = 4.0 * np.pi**2 * radius**2 * C_n + pitch**2 * C_t
    if abs(denominator) < EPS:
        V_theory = 0.0
    else:
        V_theory = (
            (C_n - C_t) * angular_velocity * 2.0 * np.pi * radius**2 * pitch
            / denominator
        )
    return {
        "V_theory": V_theory,
        "omega_theory": angular_velocity,
        "V_slender_limit": angular_velocity * 2.0 * np.pi * radius**2 * pitch / (
            8.0 * np.pi**2 * radius**2 + pitch**2
        ),
        **coefficients,
        "theory_mode": "legacy_prescribed_omega",
    }


def compute_theoretical_velocity(
    pitch: float,
    radius: float,
    total_length: float,
    angular_velocity: float | None = None,
    filament_radius: float | None = None,
    fluid_viscosity: float = 0.1,
    torque_magnitude: float = 1e-8,
    body_length_ratio: float = 0.5,
    body_radius: float | None = None,
    mode: str = "torque_driven_rft",
) -> dict:
    """Compute analytical propulsion for the configured RFT rod approximation.

    The default model solves the same type of torque-driven problem as the
    simulation: applied endpoint torque drives a rigid body-tail centerline,
    while RFT line drag supplies axial force and resisting torque.  The body
    drag contribution is intentionally minimal and approximate.

    ``mode="legacy"`` retains the prior prescribed-angular-velocity helix-only
    result for comparison; in the default mode ``angular_velocity`` is not an
    input to the solved theoretical state.
    """
    if filament_radius is None:
        filament_radius = radius
    if mode in ("legacy", "legacy_prescribed_omega"):
        if angular_velocity is None:
            raise ValueError("angular_velocity is required for legacy theory mode")
        legacy = _compute_legacy_velocity(
            pitch,
            radius,
            total_length,
            angular_velocity,
            filament_radius,
            fluid_viscosity,
        )
        return {
            "pitch": pitch,
            "radius": radius,
            "angular_velocity": angular_velocity,
            **legacy,
        }
    if mode != "torque_driven_rft":
        raise ValueError(f"Unsupported theory mode: {mode}")

    body_radius = radius if body_radius is None else body_radius
    resistance = compute_rft_resistance_matrix(
        pitch=pitch,
        radius=radius,
        total_length=total_length,
        body_length_ratio=body_length_ratio,
        filament_radius=filament_radius,
        fluid_viscosity=fluid_viscosity,
    )
    body_drag = estimate_body_drag_coefficients(
        body_length=resistance["body_length"],
        body_radius=body_radius,
        C_t=resistance["C_t"],
        C_n=resistance["C_n"],
    )
    solution = solve_torque_driven_velocity(
        A=resistance["A"],
        B=resistance["B"],
        D=resistance["D"],
        body_translational_drag=body_drag["body_translational_drag"],
        body_rotational_drag=body_drag["body_rotational_drag"],
        torque_magnitude=torque_magnitude,
    )
    resistance_breakdown = compute_rotational_resistance_breakdown(
        D=resistance["D"],
        body_rotational_drag=body_drag["body_rotational_drag"],
        D_total=solution["D_total"],
    )
    return {
        **resistance,
        **body_drag,
        **solution,
        **resistance_breakdown,
        **torque_frame_metadata(applied_torque_material_component=torque_magnitude),
        "angular_velocity": solution["omega_theory"],
        "torque_magnitude": torque_magnitude,
        "body_radius": body_radius,
        "theory_mode": "torque_driven_rft",
        "V_slender_limit": None,
    }


def analytical_comparison(
    sim_result: dict,
    fluid_viscosity: float = 0.1,
) -> dict:
    """Compare simulated motion with the torque-driven RFT approximation."""
    params = sim_result.get("parameters", {})
    pitch = params.get("pitch", 0.02)
    radius = params.get("radius", 0.01)
    total_length = params.get("total_length", 0.1)

    omega_history = sim_result.get("omega_history", [])
    omega_z_history = sim_result.get("omega_z_history")
    if omega_z_history is None:
        omega_z_history = [float(o[2, :].mean()) for o in omega_history]
    omega_metrics = compute_steady_state_metrics(omega_z_history)
    if omega_z_history:
        n_omega = len(omega_z_history)
        steady_omega = omega_z_history[max(0, n_omega - max(1, n_omega // 5)):]
        omega_sim = float(np.mean(steady_omega))
    else:
        omega_sim = 0.0

    theory = compute_theoretical_velocity(
        pitch=pitch,
        radius=radius,
        total_length=total_length,
        filament_radius=radius,
        fluid_viscosity=fluid_viscosity,
        torque_magnitude=params.get("torque_magnitude", 1e-8),
        body_length_ratio=params.get("body_length_ratio", 0.5),
        body_radius=params.get("body_radius", radius),
    )

    vz_history = sim_result.get("vz_history", [])
    if vz_history:
        n_vz = len(vz_history)
        steady_vz = vz_history[max(0, n_vz - max(1, n_vz // 5)):]
        V_sim = float(np.mean(steady_vz))
    else:
        V_sim = 0.0

    error_metrics = compute_error_metrics(V_sim, theory["V_theory"])
    steady_metrics = compute_steady_state_metrics(vz_history)
    balance_diagnostics = compute_balance_diagnostics(
        V_sim=V_sim,
        omega_sim=omega_sim,
        A_total=theory["A_total"],
        B=theory["B"],
        D_total=theory["D_total"],
        torque_magnitude=params.get("torque_magnitude", 1e-8),
        D=theory["D"],
        body_rotational_drag=theory["body_rotational_drag"],
    )
    torque_projection_history = sim_result.get(
        "applied_torque_global_z_projection_history", []
    )
    torque_alignment_history = sim_result.get("applied_torque_axis_alignment_history", [])
    projection_mean = (
        float(np.mean(torque_projection_history[-max(1, len(torque_projection_history) // 5):]))
        if torque_projection_history else None
    )
    alignment_mean = (
        float(np.mean(torque_alignment_history[-max(1, len(torque_alignment_history) // 5):]))
        if torque_alignment_history else None
    )
    frame_metadata = torque_frame_metadata(
        applied_torque_material_component=params.get("torque_magnitude", 1e-8),
        applied_torque_global_z_projection=projection_mean,
        applied_torque_axis_alignment=alignment_mean,
    )
    damping_history = sim_result.get("damping_torque_global_z_history", [])
    damping_torque_estimate = (
        float(np.mean(damping_history[-max(1, len(damping_history) // 5):]))
        if damping_history else None
    )
    damping_diagnostics = compute_damping_torque_diagnostics(
        torque_balance_residual=balance_diagnostics["torque_balance_residual"],
        omega_sim=omega_sim,
        torque_magnitude=params.get("torque_magnitude", 1e-8),
        damping_model=params.get("damping_model"),
        damping_constant=params.get("damping_constant"),
        rotational_damping_mass=params.get("rotational_damping_mass"),
        damping_torque_estimate=damping_torque_estimate,
        damping_estimate_status=params.get("damping_estimate_status"),
        frame_mismatch_risk=frame_metadata["frame_mismatch_risk"],
    )
    omega_summary = {
        f"omega_{key.removeprefix('steady_')}": value
        for key, value in omega_metrics.items()
    }
    return {
        **theory,
        "V_sim": V_sim,
        "omega_sim": omega_sim,
        "omega_z": omega_sim,
        **error_metrics,
        **steady_metrics,
        **balance_diagnostics,
        **frame_metadata,
        **damping_diagnostics,
        **omega_summary,
    }
