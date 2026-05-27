import pytest
import sys
from pathlib import Path


pytest.importorskip("elastica", reason="PyElastica is required to import research_code.py")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


LEGACY_PUBLIC_API = [
    "SpiralRodSimulator",
    "ResistiveForceTheoryForcing",
    "EndpointTorques",
    "BasicDataCollector",
    "compute_theoretical_velocity",
    "analytical_comparison",
    "stiffness_check",
    "stiffness_calibration",
    "run_simulation",
    "parameter_sweep_h1",
    "parameter_sweep_h2",
    "compute_efficiency",
    "plot_efficiency_curve",
    "efficiency_curve_analysis",
    "log_simulation_timeseries",
    "log_sweep_summary",
    "log_all_sweep_data",
    "n_convergence_test",
]


def test_research_code_exports_core_functions():
    from research_code import (
        compute_theoretical_velocity,
        run_simulation,
        stiffness_check,
    )

    assert callable(run_simulation)
    assert callable(compute_theoretical_velocity)
    assert callable(stiffness_check)


def test_research_code_reexports_legacy_public_api():
    import research_code

    missing = [name for name in LEGACY_PUBLIC_API if not hasattr(research_code, name)]

    assert missing == []
    for name in LEGACY_PUBLIC_API:
        assert callable(getattr(research_code, name))


def test_package_exports_core_functions():
    from helical_propeller.simulator import run_simulation
    from helical_propeller.stiffness import stiffness_check
    from helical_propeller.theory import compute_theoretical_velocity

    assert callable(run_simulation)
    assert callable(compute_theoretical_velocity)
    assert callable(stiffness_check)


def test_compute_theoretical_velocity_returns_expected_keys():
    from research_code import compute_theoretical_velocity

    result = compute_theoretical_velocity(
        pitch=0.02,
        radius=0.01,
        total_length=0.1,
        angular_velocity=1.0,
        fluid_viscosity=0.1,
    )

    assert isinstance(result, dict)
    assert "V_theory" in result
    assert "C_t" in result
    assert "C_n" in result
