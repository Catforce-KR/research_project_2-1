import numpy as np


def build_body_helical_geometry(
    n_elem: int,
    pitch: float,
    radius: float,
    total_length: float,
    body_length_ratio: float,
    body_radius: float,
    density: float,
    E: float,
    nu: float,
) -> dict:
    """Build body-tail geometry and rod material arrays for the helical propeller."""
    n_nodes = n_elem + 1
    n_voronoi = n_elem - 1
    G = E / (2.0 * (1.0 + nu))
    body_length = body_length_ratio * total_length
    if body_radius is None:
        body_radius = 1.0 * radius

    n_body_elems = max(1, min(n_elem - 1, int(round(body_length_ratio * n_elem))))
    n_tail_elems = n_elem - n_body_elems

    positions = np.zeros((3, n_nodes))

    z_body = np.linspace(0, body_length, n_body_elems + 1)
    positions[0, :n_body_elems + 1] = body_radius
    positions[1, :n_body_elems + 1] = 0.0
    positions[2, :n_body_elems + 1] = z_body

    z_tail = np.linspace(body_length, total_length, n_tail_elems + 1)
    theta_tail = 2 * np.pi * (z_tail - body_length) / pitch
    positions[0, n_body_elems:] = radius * np.cos(theta_tail)
    positions[1, n_body_elems:] = radius * np.sin(theta_tail)
    positions[2, n_body_elems:] = z_tail

    tangents = np.diff(positions, axis=1)
    rest_lengths = np.linalg.norm(tangents, axis=0)
    tangents /= rest_lengths

    directors = np.zeros((3, 3, n_elem))
    for i in range(n_elem):
        t = tangents[:, i]
        if i < n_body_elems:
            d1 = np.array([0.0, 1.0, 0.0])
            d2 = np.cross(t, d1)
            d2 /= np.linalg.norm(d2)
            d1 = np.cross(d2, t)
        else:
            d2 = np.array([-positions[0, i], -positions[1, i], 0.0])
            d2_norm = np.linalg.norm(d2)
            d2 = d2 / d2_norm if d2_norm > 1e-10 else np.array([1.0, 0.0, 0.0])
            d1 = np.cross(d2, t)
            d1 /= np.linalg.norm(d1)
            d2 = np.cross(t, d1)

        directors[0, :, i] = d1
        directors[1, :, i] = d2
        directors[2, :, i] = t

    A = np.pi * radius**2
    I = (np.pi * radius**4) / 4.0
    J = 2.0 * I

    shear_matrix = np.zeros((3, 3, n_elem))
    bend_matrix = np.zeros((3, 3, n_voronoi))
    for i in range(n_elem):
        shear_matrix[:, :, i] = np.diag([G * A, G * A, E * A])
    for i in range(n_voronoi):
        bend_matrix[:, :, i] = np.diag([E * I, E * I, G * J])

    volumes = np.full(n_elem, A * total_length / n_elem)
    mass = np.zeros(n_nodes)
    mass[:-1] += 0.5 * density * volumes
    mass[1:] += 0.5 * density * volumes

    mass_inertia = np.zeros((3, 3, n_elem))
    inv_mass_inertia = np.zeros((3, 3, n_elem))
    for i in range(n_elem):
        mass_inertia[:, :, i] = np.diag([I, I, J]) * density * rest_lengths[i]
        inv_mass_inertia[:, :, i] = np.linalg.inv(mass_inertia[:, :, i])

    rest_voronoi_lengths = 0.5 * (rest_lengths[:-1] + rest_lengths[1:])
    initial_kappa = np.zeros((3, n_voronoi))
    for i in range(n_voronoi):
        Q1 = directors[:, :, i]
        Q2 = directors[:, :, i + 1]
        R = Q2 @ Q1.T
        theta = np.arccos(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0))
        if theta > 1e-12:
            axis = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
            axis /= np.linalg.norm(axis)
            initial_kappa[:, i] = ((Q1 + Q2) / 2.0) @ (theta * axis / rest_voronoi_lengths[i])

    return {
        "n_nodes": n_nodes,
        "n_voronoi": n_voronoi,
        "G": G,
        "body_length": body_length,
        "body_radius": body_radius,
        "n_body_elems": n_body_elems,
        "n_tail_elems": n_tail_elems,
        "positions": positions,
        "tangents": tangents,
        "rest_lengths": rest_lengths,
        "directors": directors,
        "A": A,
        "I": I,
        "J": J,
        "shear_matrix": shear_matrix,
        "bend_matrix": bend_matrix,
        "volumes": volumes,
        "mass": mass,
        "mass_inertia": mass_inertia,
        "inv_mass_inertia": inv_mass_inertia,
        "rest_voronoi_lengths": rest_voronoi_lengths,
        "initial_kappa": initial_kappa,
    }


__all__ = ["build_body_helical_geometry"]
