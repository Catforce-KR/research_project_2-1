import math
import sys
from pathlib import Path

import numpy as np


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def test_callback_records_inertial_z_angular_velocity():
    from helical_propeller.callbacks import BasicDataCollector

    callback_params = {
        "time": [],
        "position": [],
        "velocity": [],
        "omega": [],
        "omega_z": [],
        "kappa": [],
        "sigma": [],
    }
    collector = BasicDataCollector(step_skip=1, callback_params=callback_params)
    system = type("System", (), {})()
    system.position_collection = np.zeros((3, 2))
    system.velocity_collection = np.zeros((3, 2))
    system.omega_collection = np.array([[1.0], [0.0], [0.0]])
    system.director_collection = np.array([[[0.0], [0.0], [1.0]],
                                           [[0.0], [1.0], [0.0]],
                                           [[-1.0], [0.0], [0.0]]])
    system.kappa = np.zeros((3, 1))
    system.sigma = np.zeros((3, 1))

    collector.make_callback(system, time=0.0, current_step=0)

    assert callback_params["omega"][0][2, 0] == 0.0
    assert callback_params["omega_z"] == [1.0]


def test_callback_records_torque_projection_and_damping_equivalent():
    from helical_propeller.callbacks import BasicDataCollector

    callback_params = {
        "time": [],
        "position": [],
        "velocity": [],
        "omega": [],
        "omega_z": [],
        "kappa": [],
        "sigma": [],
    }
    collector = BasicDataCollector(
        step_skip=1,
        callback_params=callback_params,
        applied_torque_material=np.array([0.0, 0.0, 2.0]),
        damping_constant=0.1,
    )
    system = type("System", (), {})()
    system.position_collection = np.zeros((3, 3))
    system.velocity_collection = np.zeros((3, 3))
    system.omega_collection = np.array([[0.0, 0.0], [0.0, 0.0], [3.0, 3.0]])
    system.director_collection = np.repeat(np.eye(3)[:, :, np.newaxis], 2, axis=2)
    system.mass = np.array([1.0, 2.0, 1.0])
    system.dilatation = np.ones(2)
    system.kappa = np.zeros((3, 1))
    system.sigma = np.zeros((3, 2))

    collector.make_callback(system, time=0.0, current_step=0)

    assert callback_params["applied_torque_global_z_projection"] == [2.0]
    assert callback_params["applied_torque_axis_alignment"] == [1.0]
    assert math.isclose(callback_params["damping_torque_global_z"][0], 1.2)
