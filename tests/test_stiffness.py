import sys
from pathlib import Path

import numpy as np


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def test_stiffness_check_ok_for_unchanged_positions():
    from helical_propeller.stiffness import stiffness_check

    positions = np.array(
        [
            [0.01, 0.01, 0.01, 0.01],
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.03, 0.06, 0.1],
        ]
    )
    sim_result = {
        "position": [positions.copy(), positions.copy()],
        "kappa": [np.zeros((3, 2)), np.zeros((3, 2))],
        "parameters": {
            "total_length": 0.1,
            "n_elem": 3,
            "body_length_ratio": 0.33,
            "E": 1.0e7,
        },
    }

    result = stiffness_check(sim_result)

    assert result["status"] == "OK"
    assert result["deformation_exceeded"] is False
    assert result["max_displacement_pct"] == 0.0


def test_stiffness_check_reports_insufficient_data():
    from helical_propeller.stiffness import stiffness_check

    result = stiffness_check({"position": []})

    assert result["status"] == "N/A"
    assert result["deformation_exceeded"] is False
