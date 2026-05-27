from .efficiency import efficiency_curve_analysis
from .logging_utils import log_simulation_timeseries
from .simulator import run_simulation
from .stiffness import stiffness_calibration
from .sweeps import n_convergence_test, parameter_sweep_h1, parameter_sweep_h2


def main() -> None:
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


if __name__ == "__main__":
    main()

