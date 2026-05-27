import numpy as np
import elastica as ea

class ResistiveForceTheoryForcing(ea.NoForces):
    def __init__(self, fluid_viscosity, radius, rod_total_length=None):
        super().__init__()
        self.fluid_viscosity = fluid_viscosity
        self.radius = radius
        self.rod_total_length = rod_total_length  # 로그 항에 사용할 전체 막대 길이
        
    def apply_forces(self, system, time=0.0):
        # 나선형 추진체(CosseratRod)에 대한 항력
        if hasattr(system, 'velocity_collection') and hasattr(system, 'tangents'):
            velocity = system.velocity_collection
            tangents = system.tangents
            radius = self.radius
            
            # 전체 막대 길이 계산 (슬렌더 바디 이론의 특성 길이)
            if self.rod_total_length is not None:
                L_total = self.rod_total_length
            else:
                L_total = np.sum(system.rest_lengths)
            
            # Purcell/Lighthill Slender Body Theory 계수
            # 점근적으로 Cn/Ct → 2 (slender limit)
            # ξ_∥ = 2πμ / (ln(2L_total/a) - 0.5)  접선 저항 계수 (단위 길이당)
            # ξ_⊥ = 4πμ / (ln(2L_total/a) + 0.5)  법선 저항 계수 (단위 길이당)
            log_arg = 2.0 * L_total / radius
            log_term = np.log(log_arg) if log_arg > 1.0 else 0.0
            
            C_t = 2.0 * np.pi * self.fluid_viscosity / (log_term - 0.5)  # ξ_∥
            C_n = 4.0 * np.pi * self.fluid_viscosity / (log_term + 0.5)  # ξ_⊥
            
            for i in range(system.n_elems):
                v_elem = 0.5 * (velocity[:, i] + velocity[:, i+1])
                t = tangents[:, i]
                L_elem = system.rest_lengths[i]
                
                v_t = np.dot(v_elem, t) * t
                v_n = v_elem - v_t
                
                # 요소 길이를 곱하여 요소 전체 항력 계산
                drag_force = -(C_t * v_t + C_n * v_n) * L_elem
                
                system.external_forces[:, i] += 0.5 * drag_force
                system.external_forces[:, i+1] += 0.5 * drag_force
                
        # 원통형 몸체(Cylinder)에 대한 항력 - tangents가 없으면 Cylinder로 판별
        elif hasattr(system, 'velocity_collection') and not hasattr(system, 'tangents'):
            vel = system.velocity_collection.flatten()
            body_len = system.length  # 실린더 길이
            C_drag = 4.0 * np.pi * self.fluid_viscosity  # Stokes 항력 계수 (단위 길이당)
            system.external_forces += (-C_drag * vel * body_len).reshape(3, 1)


class EndpointTorques(ea.NoForces):
    def __init__(self, start_torque):
        super().__init__()
        self.start_torque = start_torque
        
    def apply_torques(self, system, time=0.0):
        system.external_torques[:, 0] += self.start_torque

