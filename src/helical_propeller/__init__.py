"""Helical propeller RFT simulation package."""

from importlib import import_module


_EXPORTS = {
    "BasicDataCollector": "callbacks",
    "ResistiveForceTheoryForcing": "forces",
    "EndpointTorques": "forces",
    "build_body_helical_geometry": "geometry",
    "compute_theoretical_velocity": "theory",
    "analytical_comparison": "theory",
    "compute_helix_geometry": "theory",
    "compute_rft_resistance_matrix": "theory",
    "estimate_body_drag_coefficients": "theory",
    "solve_torque_driven_velocity": "theory",
    "compute_balance_diagnostics": "theory",
    "compute_rotational_resistance_breakdown": "theory",
    "torque_frame_metadata": "theory",
    "compute_damping_torque_diagnostics": "theory",
    "compute_error_metrics": "analysis_metrics",
    "compute_steady_state_metrics": "analysis_metrics",
    "summarize_result_status": "analysis_metrics",
    "build_common_result_summary": "analysis_metrics",
    "stiffness_check": "stiffness",
    "stiffness_calibration": "stiffness",
    "SpiralRodSimulator": "simulator",
    "run_simulation": "simulator",
    "parameter_sweep_h1": "sweeps",
    "parameter_sweep_h2": "sweeps",
    "n_convergence_test": "sweeps",
    "compute_efficiency": "efficiency",
    "plot_efficiency_curve": "efficiency",
    "efficiency_curve_analysis": "efficiency",
    "log_simulation_timeseries": "logging_utils",
    "log_sweep_summary": "logging_utils",
    "log_all_sweep_data": "logging_utils",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{_EXPORTS[name]}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
