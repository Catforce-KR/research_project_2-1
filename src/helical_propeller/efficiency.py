import numpy as np

def compute_efficiency(
    sim_result: dict,
    torque_magnitude: float = None,
) -> dict:
    """
    Compute propulsive efficiency from simulation results.

    Two efficiency metrics are computed:

    1. **Slip efficiency** (eta_slip):
       Ratio of actual swimming speed to the no-slip speed of a rigid
       screw propeller using the recorded or predicted angular speed.
           eta_slip = V_sim / (omega_used * pitch / (2*pi))
       Range: 0 (fully slipping) to 1 (perfect screw).
       This is a kinematic/slip indicator of conversion from rotation to
       forward motion.

    2. **Power efficiency** (eta_power):
       Ratio of useful propulsive power (drag force on body * speed)
       to input mechanical power (torque * angular velocity).
           P_out = body_translational_drag * V_sim^2
           P_in  = |torque_magnitude * omega_used|
           eta_power = P_out / P_in
       This is an RFT-based useful power ratio estimate, not total fluid
       dissipation efficiency.

    Interpret these metrics together with V_sim, stiffness validity, and
    steady-state status when drawing conclusions.

    Returns a dict with all intermediate quantities and both efficiencies,
    or None if required data is missing.
    """
    analysis = sim_result.get("analytical")
    params = sim_result.get("parameters", {})

    if analysis is None:
        return None

    V_sim = analysis.get("V_sim", 0.0)
    omega_sim = analysis.get("omega_sim", analysis.get("omega_z"))
    omega_theory = analysis.get("omega_theory")
    C_t = analysis.get("C_t", 0.0)
    pitch = params.get("pitch", analysis.get("pitch", 0.02))
    total_length = params.get("total_length", 0.1)
    body_length_ratio = params.get("body_length_ratio", 0.5)
    body_length = body_length_ratio * total_length

    if torque_magnitude is None:
        torque_magnitude = params.get("torque_magnitude", 1e-8)

    if omega_sim is not None and np.isfinite(omega_sim):
        omega_used = float(omega_sim)
        omega_source = "omega_sim"
    elif omega_theory is not None and np.isfinite(omega_theory):
        omega_used = float(omega_theory)
        omega_source = "omega_theory"
    elif params.get("angular_velocity") is not None:
        omega_used = float(params["angular_velocity"])
        omega_source = "configured_omega"
    else:
        omega_used = 0.0
        omega_source = "unavailable"

    abs_omega = abs(omega_used)

    # ---- Metric 1: Slip efficiency (kinematic) ----
    noslip_speed = abs_omega * pitch / (2.0 * np.pi)  # V_max = omega * P / 2pi
    if noslip_speed > 1e-30:
        eta_slip = abs(V_sim) / noslip_speed
    else:
        eta_slip = 0.0

    # ---- Metric 2: Power efficiency (thermodynamic) ----
    # Input power: torque * angular velocity
    P_in = abs(torque_magnitude * abs_omega) if torque_magnitude is not None else 0.0

    # Output power: axial drag of the represented straight body at V_sim.
    body_translational_drag = analysis.get("body_translational_drag")
    if body_translational_drag is None:
        body_translational_drag = C_t * body_length if C_t > 0 else 0.0
    P_out = body_translational_drag * V_sim**2

    if P_in > 1e-30:
        eta_power = P_out / P_in
    else:
        eta_power = 0.0

    # ---- Additional info ----
    # Input power density (per unit tail length)
    tail_length = total_length - body_length
    P_in_density = P_in / tail_length if tail_length > 0 else 0.0

    # Propulsive force (thrust)
    F_thrust = body_translational_drag * V_sim

    return {
        "eta_slip": eta_slip,
        "eta_power": eta_power,
        "Eta_slip": eta_slip,
        "Eta_power": eta_power,
        "efficiency_model": "rft_useful_power_ratio",
        "V_sim": V_sim,
        "omega_z": omega_used,
        "omega_used": omega_used,
        "omega_source": omega_source,
        "omega_sim": omega_sim,
        "omega_theory": omega_theory,
        "noslip_speed": noslip_speed,
        "P_in": P_in,
        "P_out": P_out,
        "F_thrust": F_thrust,
        "C_t": C_t,
        "body_translational_drag": body_translational_drag,
        "body_length": body_length,
        "tail_length": tail_length,
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
    from .sweeps import parameter_sweep_h1

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

