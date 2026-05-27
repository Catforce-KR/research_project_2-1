import numpy as np
import elastica as ea


class BasicDataCollector(ea.CallBackBaseClass):
    def __init__(
        self,
        step_skip: int,
        callback_params: dict,
        applied_torque_material=None,
        damping_constant: float | None = None,
    ):
        super().__init__()
        self.step_skip = step_skip
        self.callback_params = callback_params
        self.applied_torque_material = (
            None if applied_torque_material is None
            else np.asarray(applied_torque_material, dtype=float)
        )
        self.damping_constant = damping_constant

    def make_callback(self, system, time, current_step: int):
        if current_step % self.step_skip == 0:
            self.callback_params["time"].append(time)
            self.callback_params["position"].append(system.position_collection.copy())
            self.callback_params["velocity"].append(system.velocity_collection.copy())
            if hasattr(system, "omega_collection"):
                self.callback_params["omega"].append(system.omega_collection.copy())
                if hasattr(system, "director_collection"):
                    # PyElastica stores omega in material coordinates.
                    omega_inertial = np.einsum(
                        "jik,jk->ik",
                        system.director_collection,
                        system.omega_collection,
                    )
                    self.callback_params.setdefault("omega_z", []).append(
                        float(omega_inertial[2, :].mean())
                    )
                    if self.applied_torque_material is not None:
                        torque_inertial = np.einsum(
                            "ji,j->i",
                            system.director_collection[:, :, 0],
                            self.applied_torque_material,
                        )
                        projection = float(torque_inertial[2])
                        torque_norm = float(np.linalg.norm(self.applied_torque_material))
                        self.callback_params.setdefault(
                            "applied_torque_global_z_projection", []
                        ).append(projection)
                        self.callback_params.setdefault(
                            "applied_torque_axis_alignment", []
                        ).append(projection / torque_norm if torque_norm > 1e-30 else 0.0)
                    if (
                        self.damping_constant is not None
                        and hasattr(system, "mass")
                        and hasattr(system, "dilatation")
                    ):
                        nodal_mass = system.mass
                        element_mass = 0.5 * (nodal_mass[1:] + nodal_mass[:-1])
                        element_mass[0] += 0.5 * nodal_mass[0]
                        element_mass[-1] += 0.5 * nodal_mass[-1]
                        damping_material = (
                            self.damping_constant
                            * element_mass[np.newaxis, :]
                            * system.omega_collection
                        )
                        damping_inertial = np.einsum(
                            "jik,jk->ik",
                            system.director_collection,
                            damping_material,
                        )
                        self.callback_params.setdefault(
                            "damping_torque_global_z", []
                        ).append(float(damping_inertial[2, :].sum()))
            if hasattr(system, "kappa"):
                self.callback_params["kappa"].append(system.kappa.copy())
            if hasattr(system, "sigma"):
                self.callback_params["sigma"].append(system.sigma.copy())


# ============================================================
