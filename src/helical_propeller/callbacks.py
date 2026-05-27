import numpy as np
import elastica as ea


class BasicDataCollector(ea.CallBackBaseClass):
    def __init__(self, step_skip: int, callback_params: dict):
        super().__init__()
        self.step_skip = step_skip
        self.callback_params = callback_params

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
            if hasattr(system, "kappa"):
                self.callback_params["kappa"].append(system.kappa.copy())
            if hasattr(system, "sigma"):
                self.callback_params["sigma"].append(system.sigma.copy())


# ============================================================
