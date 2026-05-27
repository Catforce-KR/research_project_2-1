from pathlib import Path

from .analysis_metrics import ANALYSIS_FIELDS, EFFICIENCY_FIELDS, RESULT_STATUS_FIELDS, STIFFNESS_FIELDS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def _resolve_output_path(filepath: str, default_dir: Path) -> Path:
    path = Path(filepath)
    if path.is_absolute():
        output_path = path
    elif path.parent == Path("."):
        output_path = default_dir / path
    else:
        output_path = PROJECT_ROOT / path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def log_simulation_timeseries(
    sim_result: dict,
    filepath: str = "simulation_timeseries.csv",
    torque_magnitude: float = None,
) -> str:
    """
    Export time-history data from a single simulation to a CSV file.

    Single simulation and per-sweep detail time-series CSV files are saved
    under data/raw/ when a bare filename is supplied.

    Columns:
        - Time (s)
        - Vz_mean (m/s) : mean z-velocity of all nodes at each recorded step
        - Omega_z (rad/s) : mean angular velocity z-component
        - Input_Torque (Nm) : applied torque magnitude
        - Applied_Torque_Global_Z_Projection (Nm) : material torque projected on inertial z
        - Damping_Torque_Global_Z_Estimate (Nm) : equivalent resisting damper torque projection
        - Power_Efficiency : P_out / P_in at each recorded step
        - Theoretical_Error (%) : compatibility alias for pct_error_vs_sim

    Returns the filepath of the saved CSV, or None on failure.
    """
    import pandas as pd

    output_path = _resolve_output_path(filepath, DATA_RAW_DIR)
    time_list = sim_result.get("time", [])
    vel_list = sim_result.get("velocity", [])
    omega_list = sim_result.get("omega", [])
    omega_z_history = sim_result.get("omega_z_history", [])
    torque_projection_history = sim_result.get("applied_torque_global_z_projection_history", [])
    torque_alignment_history = sim_result.get("applied_torque_axis_alignment_history", [])
    damping_torque_history = sim_result.get("damping_torque_global_z_history", [])
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
    if omega_z_history:
        omega_z_series = [float(value) for value in omega_z_history]
    else:
        for o in omega_list:
            omega_z_series.append(float(o[2, :].mean()) if o.shape[0] >= 3 else 0.0)

    # Compute power efficiency at each time step
    # Uses the same formula as compute_efficiency
    C_t = analysis.get("C_t", 0.0) if analysis else 0.0
    body_length = params.get("body_length_ratio", 0.5) * params.get("total_length", 0.1)
    body_translational_drag = (
        analysis.get("body_translational_drag") if analysis else None
    )
    if body_translational_drag is None:
        body_translational_drag = C_t * body_length if C_t > 0 else 0.0

    # For theoretical error, use steady-state analytical comparison
    theoretical_error = analysis.get("pct_error", float("nan")) if analysis else float("nan")
    V_theory = analysis.get("V_theory", float("nan")) if analysis else float("nan")

    rows = []
    for i in range(len(time_list)):
        t = time_list[i]
        vz = vz_series[i] if i < len(vz_series) else float("nan")
        omz = omega_z_series[i] if i < len(omega_z_series) else float("nan")

        # Power efficiency at this instant
        P_in = abs(torque_magnitude * abs(omz)) if torque_magnitude and abs(omz) > 1e-30 else 0.0
        P_out = body_translational_drag * vz**2
        eta_power = P_out / P_in if P_in > 1e-30 else 0.0

        rows.append({
            "Time": t,
            "Vz_mean": vz,
            "Omega_z": omz,
            "Input_Torque": torque_magnitude,
            "Applied_Torque_Global_Z_Projection": (
                torque_projection_history[i]
                if i < len(torque_projection_history) else None
            ),
            "Applied_Torque_Axis_Alignment": (
                torque_alignment_history[i]
                if i < len(torque_alignment_history) else None
            ),
            "Damping_Torque_Global_Z_Estimate": (
                damping_torque_history[i]
                if i < len(damping_torque_history) else None
            ),
            "Power_Efficiency": eta_power,
            "Theoretical_Error": theoretical_error,
            "V_theory": V_theory,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8")
    saved_path = _display_path(output_path)
    print(f"[OK] CSV timeseries saved: {saved_path} ({len(rows)} rows)")
    return saved_path


def log_sweep_summary(
    sweep_results: dict,
    filepath: str = "sweep_summary.csv",
    sweep_type: str = "h1",
) -> str:
    """
    Export parameter sweep summary to a CSV file.

    Sweep summary CSV files are saved under data/processed/ when a bare
    filename is supplied.

    For H1 sweeps (P/R ratio), columns:
        - P/R, Pitch, Vz_final_mean, Vz_com_avg, Status
        - Eta_slip, Eta_power, Theoretical_Error

    For H2 sweeps (Body/Tail ratio), columns:
        - Body_Length_Ratio, Body_Length, Vz_final_mean, Vz_com_avg, Status
        - Theoretical_Error

    Returns the filepath of the saved CSV, or None on failure.
    """
    import pandas as pd

    output_path = _resolve_output_path(filepath, DATA_PROCESSED_DIR)
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
            row["Pitch"] = data.get("pitch", float("nan"))
        elif sweep_type in ("h2", "body"):
            row["Body_Length_Ratio"] = float(key)
            row["Body_Length"] = data.get("body_length", float("nan"))
        else:
            row["Param"] = float(key)

        row["Vz_final_mean"] = data.get("vz_final_mean", float("nan"))
        row["Vz_com_avg"] = data.get("vz_com_avg", float("nan"))

        analysis = data.get("analytical") or {}
        eff = data.get("efficiency") or {}
        stiffness = data.get("stiffness") or {}
        for field in RESULT_STATUS_FIELDS:
            row[field] = data.get(field)
        row["status"] = data.get("status", status)
        for field in ANALYSIS_FIELDS:
            row[field] = data.get(field, analysis.get(field))
        row["Cn_over_Ct"] = data.get("Cn_over_Ct", analysis.get("Cn_over_Ct"))
        row["Theoretical_Error"] = row["pct_error"]
        efficiency_sources = {
            "Eta_slip": "eta_slip",
            "Eta_power": "eta_power",
            "P_in": "P_in",
            "P_out": "P_out",
            "omega_used": "omega_used",
            "omega_source": "omega_source",
            "efficiency_model": "efficiency_model",
        }
        for field in EFFICIENCY_FIELDS:
            row[field] = data.get(field, eff.get(efficiency_sources[field]))
        stiffness_sources = {
            "stiffness_status": "status",
            "deformation_exceeded": "deformation_exceeded",
            "worst_metric_pct": "worst_metric_pct",
        }
        for field in STIFFNESS_FIELDS:
            row[field] = data.get(field, stiffness.get(stiffness_sources[field]))

        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8")
    saved_path = _display_path(output_path)
    print(f"[OK] CSV sweep summary saved: {saved_path} ({len(rows)} entries)")
    return saved_path


def log_all_sweep_data(
    sweep_results: dict,
    base_filename: str = "sweep",
    sweep_type: str = "h1",
) -> dict:
    """
    Convenience function: exports both summary CSV for a sweep and
    per-parameter-set time-series CSVs.

    Summary CSV files go to data/processed/. Per-parameter detail
    time-series CSV files go to data/raw/.

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
            "omega": data.get("omega_history", []),
            "omega_z_history": data.get("omega_z_history", []),
            "parameters": data.get("parameters", {}),
            "analytical": data.get("analytical"),
        }

        pr = float(key)
        ts_path = f"{base_filename}_pr{pr:.2f}_timeseries.csv"
        ts_result = log_simulation_timeseries(sim_like, ts_path)
        if ts_result:
            saved[f"ts_pr{pr:.2f}"] = ts_result

    return saved


# ============================================================
