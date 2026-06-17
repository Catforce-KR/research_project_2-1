"""Generate report-ready figures of the helical propeller model geometry.

This script only visualizes the rest geometry from ``build_body_helical_geometry``.
It does not run a PyElastica time integration or any parameter sweep.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from helical_propeller.geometry import build_body_helical_geometry


REPORT_DPI = 300
BODY_COLOR = "#2f5597"
TAIL_COLOR = "#c55a11"
AXIS_COLOR = "#4d4d4d"
TORQUE_COLOR = "#7a1fa2"
RFT_COLOR = "#008a8a"
SHEAR_COLOR = "#2ca02c"
TWIST_COLOR = "#d62728"
DIRECTOR_COLORS = ("#9467bd", "#17becf", "#111111")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate multi-view report figures for the helical propeller model."
    )
    parser.add_argument("--output-dir", default="results/figures")
    parser.add_argument("--prefix", default="model")
    parser.add_argument("--n-elem", type=int, default=120)
    parser.add_argument("--pitch", type=float, default=0.02)
    parser.add_argument("--radius", type=float, default=0.01)
    parser.add_argument("--total-length", type=float, default=0.1)
    parser.add_argument("--body-length-ratio", type=float, default=0.5)
    parser.add_argument("--body-radius", type=float, default=None)
    parser.add_argument(
        "--body-visual-radius",
        type=float,
        default=None,
        help="Visual-only radius for the rendered straight body cylinder.",
    )
    parser.add_argument("--density", type=float, default=1000.0)
    parser.add_argument("--youngs-modulus", type=float, default=1.0e7)
    parser.add_argument("--poisson-ratio", type=float, default=0.5)
    return parser.parse_args()


def build_geometry(args: argparse.Namespace) -> dict:
    geometry = build_body_helical_geometry(
        n_elem=args.n_elem,
        pitch=args.pitch,
        radius=args.radius,
        total_length=args.total_length,
        body_length_ratio=args.body_length_ratio,
        body_radius=args.body_radius,
        density=args.density,
        E=args.youngs_modulus,
        nu=args.poisson_ratio,
    )
    geometry["body_visual_radius"] = (
        args.body_visual_radius
        if args.body_visual_radius is not None
        else max(0.38 * args.radius, 0.0025 * args.total_length)
    )
    return geometry


def split_body_tail(geometry: dict) -> tuple[np.ndarray, np.ndarray]:
    positions = geometry["positions"]
    n_body = geometry["n_body_elems"]
    body = positions[:, : n_body + 1]
    tail = positions[:, n_body:]
    return body, tail


def set_equal_3d(ax, positions: np.ndarray, margin: float = 0.012) -> None:
    mins = positions.min(axis=1)
    maxs = positions.max(axis=1)
    center = 0.5 * (mins + maxs)
    span = max(float(np.max(maxs - mins)), margin)
    radius = 0.5 * span + margin
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_box_aspect((1.0, 1.0, 1.0))


def set_focused_3d(
    ax,
    positions: np.ndarray,
    xy_margin: float = 0.008,
    z_margin: float = 0.004,
    min_xy_span: float = 0.052,
) -> None:
    """Tight 3D limits for report figures where the full model should fill the panel."""
    mins = positions.min(axis=1)
    maxs = positions.max(axis=1)
    x_center = 0.5 * (mins[0] + maxs[0])
    y_center = 0.5 * (mins[1] + maxs[1])
    x_span = max(maxs[0] - mins[0] + 2.0 * xy_margin, min_xy_span)
    y_span = max(maxs[1] - mins[1] + 2.0 * xy_margin, min_xy_span)
    ax.set_xlim(x_center - 0.5 * x_span, x_center + 0.5 * x_span)
    ax.set_ylim(y_center - 0.5 * y_span, y_center + 0.5 * y_span)
    ax.set_zlim(mins[2] - z_margin, maxs[2] + z_margin)
    spans = np.array(
        [
            x_span,
            y_span,
            maxs[2] - mins[2] + 2.0 * z_margin,
        ]
    )
    ax.set_box_aspect(spans)
    ax.set_xticks([-0.01, 0.0, 0.01])
    ax.set_yticks([-0.01, 0.0, 0.01])
    ax.set_zticks([0.0, 0.05, 0.1])
    ax.tick_params(labelsize=8, pad=1)


def make_3d_axes_compact(ax) -> None:
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_zlabel("")
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_zticklabels([])


def clean_3d_axes(ax) -> None:
    ax.set_xlabel("x [m]", labelpad=8)
    ax.set_ylabel("y [m]", labelpad=8)
    ax.set_zlabel("z [m]", labelpad=8)
    ax.grid(True, alpha=0.22)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_alpha(0.0)


def save_figure(fig: plt.Figure, output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    fig.savefig(path, dpi=REPORT_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def draw_geometry_3d(ax, geometry: dict, lw: float = 3.0) -> None:
    body, tail = split_body_tail(geometry)
    draw_body_tube_3d(ax, geometry)
    ax.plot(tail[0], tail[1], tail[2], color=TAIL_COLOR, lw=lw, label="helical tail")
    ax.scatter(tail[0, -1], tail[1, -1], tail[2, -1], color=TAIL_COLOR, s=26)


def draw_body_tube_3d(ax, geometry: dict) -> None:
    body, _ = split_body_tail(geometry)
    visual_radius = float(geometry["body_visual_radius"])
    theta = np.linspace(0.0, 2.0 * np.pi, 42)
    z = np.linspace(float(body[2, 0]), float(body[2, -1]), 24)
    theta_grid, z_grid = np.meshgrid(theta, z)
    x_grid = float(body[0, 0]) + visual_radius * np.cos(theta_grid)
    y_grid = float(body[1, 0]) + visual_radius * np.sin(theta_grid)
    ax.plot_surface(
        x_grid,
        y_grid,
        z_grid,
        color=BODY_COLOR,
        alpha=0.34,
        linewidth=0.0,
        antialiased=True,
        shade=True,
    )
    for z_end in (float(body[2, 0]), float(body[2, -1])):
        ax.plot(
            float(body[0, 0]) + visual_radius * np.cos(theta),
            float(body[1, 0]) + visual_radius * np.sin(theta),
            np.full_like(theta, z_end),
            color=BODY_COLOR,
            lw=1.5,
        )
    ax.plot(body[0], body[1], body[2], color=BODY_COLOR, lw=1.4, alpha=0.9, label="thick straight body")


def draw_body_capsule_side(ax, geometry: dict, label: str | None = None) -> None:
    body, _ = split_body_tail(geometry)
    visual_radius = float(geometry["body_visual_radius"])
    z0 = float(body[2, 0])
    z1 = float(body[2, -1])
    center_x = float(body[0, 0])
    ax.fill_between(
        [z0, z1],
        [center_x - visual_radius, center_x - visual_radius],
        [center_x + visual_radius, center_x + visual_radius],
        color=BODY_COLOR,
        alpha=0.32,
        linewidth=0,
        label=label,
    )
    theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, 80)
    ax.fill(
        z1 + visual_radius * np.cos(theta),
        center_x + visual_radius * np.sin(theta),
        color=BODY_COLOR,
        alpha=0.32,
        linewidth=0,
    )
    theta = np.linspace(0.5 * np.pi, 1.5 * np.pi, 80)
    ax.fill(
        z0 + visual_radius * np.cos(theta),
        center_x + visual_radius * np.sin(theta),
        color=BODY_COLOR,
        alpha=0.32,
        linewidth=0,
    )
    ax.plot(body[2], body[0], color=BODY_COLOR, lw=2.0)


def draw_body_disk_top(ax, geometry: dict, label: str | None = None) -> None:
    body, _ = split_body_tail(geometry)
    visual_radius = float(geometry["body_visual_radius"])
    disk = Circle(
        (float(body[0, 0]), float(body[1, 0])),
        visual_radius,
        facecolor=BODY_COLOR,
        edgecolor=BODY_COLOR,
        alpha=0.32,
        linewidth=1.5,
        label=label,
    )
    ax.add_patch(disk)
    ax.scatter([body[0, 0]], [body[1, 0]], color=BODY_COLOR, s=18, zorder=4)


def add_reference_axis_3d(ax, geometry: dict) -> None:
    total_length = float(geometry["positions"][2].max())
    ax.plot(
        [0.0, 0.0],
        [0.0, 0.0],
        [0.0, total_length],
        color=AXIS_COLOR,
        lw=1.3,
        ls="--",
        label="propulsion axis",
    )
    ax.quiver(
        0.0,
        0.0,
        total_length * 0.12,
        0.0,
        0.0,
        total_length * 0.22,
        color=AXIS_COLOR,
        arrow_length_ratio=0.22,
        linewidth=1.6,
    )
    ax.text(0.001, 0.001, total_length * 0.4, "+z propulsion axis", color=AXIS_COLOR)


def add_torque_cue_3d(ax, geometry: dict) -> None:
    positions = geometry["positions"]
    radius = max(float(np.linalg.norm(positions[:2, 0])), 1.0e-3)
    z0 = float(positions[2, 0])
    theta = np.linspace(0.0, 1.65 * np.pi, 70)
    r = 1.35 * radius
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    z = z0 + np.full_like(theta, 0.006)
    ax.plot(x, y, z, color=TORQUE_COLOR, lw=2.0)
    ax.quiver(
        x[-2],
        y[-2],
        z[-2],
        x[-1] - x[-2],
        y[-1] - y[-2],
        0.0,
        color=TORQUE_COLOR,
        arrow_length_ratio=0.55,
        linewidth=2.0,
    )
    ax.text(x[16], y[16], z[16] + 0.003, "applied endpoint torque Tz", color=TORQUE_COLOR)


def add_rft_cues_3d(ax, geometry: dict) -> None:
    positions = geometry["positions"]
    tangents = geometry["tangents"]
    rest_lengths = geometry["rest_lengths"]
    n_body = geometry["n_body_elems"]
    radius = float(geometry["body_radius"])
    total_length = float(positions[2].max())
    idx = min(n_body + max(2, geometry["n_tail_elems"] // 3), tangents.shape[1] - 2)
    point = 0.5 * (positions[:, idx] + positions[:, idx + 1])
    tangent = tangents[:, idx]
    rotation_velocity = np.cross(np.array([0.0, 0.0, 1.0]), point)
    velocity = rotation_velocity + np.array([0.0, 0.0, 0.16 * total_length])
    vt = np.dot(velocity, tangent) * tangent
    vn = velocity - vt
    if np.linalg.norm(vn) < 1e-12:
        vn = np.cross(tangent, np.array([0.0, 0.0, 1.0]))
    vt = vt / (np.linalg.norm(vt) + 1e-15) * rest_lengths[idx] * 1.8
    vn = vn / (np.linalg.norm(vn) + 1e-15) * rest_lengths[idx] * 1.8
    drag = -(0.65 * vt + 1.0 * vn)

    for vec, color, label, dz in (
        (vt, "#1f77b4", "v_t", 0.002),
        (vn, "#ff7f0e", "v_n", -0.002),
        (drag, RFT_COLOR, "drag", 0.004),
    ):
        ax.quiver(
            point[0],
            point[1],
            point[2],
            vec[0],
            vec[1],
            vec[2],
            color=color,
            arrow_length_ratio=0.25,
            linewidth=1.6,
        )
        ax.text(point[0] + vec[0], point[1] + vec[1], point[2] + vec[2] + dz, label, color=color)


def figure_overview(geometry: dict, output_dir: Path, prefix: str) -> Path:
    fig = plt.figure(figsize=(9.0, 7.2))
    ax = fig.add_subplot(111, projection="3d")
    draw_geometry_3d(ax, geometry)
    add_reference_axis_3d(ax, geometry)
    add_torque_cue_3d(ax, geometry)
    add_rft_cues_3d(ax, geometry)
    set_focused_3d(ax, geometry["positions"], xy_margin=0.009, z_margin=0.004)
    clean_3d_axes(ax)
    ax.view_init(elev=24, azim=-56)
    ax.set_title("Helical propeller model: body, tail, torque, and local RFT vectors", pad=16)
    legend_handles = [
        Line2D([0], [0], color=BODY_COLOR, lw=6, alpha=0.5, label="thick straight body"),
        Line2D([0], [0], color=TAIL_COLOR, lw=3, label="helical tail"),
        Line2D([0], [0], color=AXIS_COLOR, lw=1.5, ls="--", label="propulsion axis"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False)
    return save_figure(fig, output_dir, f"{prefix}_overview_perspective.png")


def figure_side_view(geometry: dict, output_dir: Path, prefix: str) -> Path:
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    body, tail = split_body_tail(geometry)
    positions = geometry["positions"]
    body_length = float(geometry["body_length"])
    total_length = float(positions[2].max())
    radius = float(geometry["body_radius"])
    pitch = float(np.diff(tail[2]).mean() * (2.0 * np.pi) / np.mean(np.abs(np.diff(np.unwrap(np.arctan2(tail[1], tail[0]))))))

    draw_body_capsule_side(ax, geometry, label="straight body volume")
    ax.plot(tail[2], tail[0], color=TAIL_COLOR, lw=3.0, label="helical tail projection")
    ax.axhline(0.0, color=AXIS_COLOR, lw=1.2, ls="--")
    ax.axvline(body_length, color="#777777", lw=1.0, ls=":")
    ax.annotate(
        "propulsion +z",
        xy=(total_length * 0.88, -1.35 * radius),
        xytext=(total_length * 0.56, -1.35 * radius),
        arrowprops={"arrowstyle": "->", "color": AXIS_COLOR, "lw": 1.6},
        color=AXIS_COLOR,
    )
    ax.annotate(
        "body length",
        xy=(body_length * 0.5, radius * 1.17),
        ha="center",
        color=BODY_COLOR,
        fontsize=10,
    )
    ax.plot([0.0, body_length], [radius * 1.15, radius * 1.15], color=BODY_COLOR, lw=1.4)
    ax.annotate(
        "one pitch P",
        xy=(body_length + pitch, -radius * 1.05),
        xytext=(body_length, -radius * 1.05),
        arrowprops={"arrowstyle": "<->", "color": TAIL_COLOR, "lw": 1.4},
        color=TAIL_COLOR,
        ha="center",
        va="top",
    )
    ax.text(body_length + 0.18 * pitch, radius * 0.72, "tail radius R", color=TAIL_COLOR)
    ax.set_xlabel("z [m]")
    ax.set_ylabel("x [m]")
    ax.set_title("Side view: pitch, radius, and body-to-tail partition")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, loc="lower left")
    return save_figure(fig, output_dir, f"{prefix}_side_view.png")


def figure_top_view(geometry: dict, output_dir: Path, prefix: str) -> Path:
    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    body, tail = split_body_tail(geometry)
    radius = float(geometry["body_radius"])
    theta = np.linspace(0.0, 2.0 * np.pi, 240)
    draw_body_disk_top(ax, geometry, label="body cross-section")
    ax.plot(tail[0], tail[1], color=TAIL_COLOR, lw=2.6, label="tail swept radius")
    ax.plot(radius * np.cos(theta), radius * np.sin(theta), color="#999999", lw=1.0, ls="--")
    ax.scatter([0.0], [0.0], color=AXIS_COLOR, s=24, zorder=3)
    ax.annotate(
        "rotation around z",
        xy=(radius * 0.05, radius * 1.05),
        xytext=(-radius * 1.45, radius * 1.45),
        arrowprops={"arrowstyle": "->", "connectionstyle": "arc3,rad=-0.42", "color": TORQUE_COLOR, "lw": 1.8},
        color=TORQUE_COLOR,
    )
    ax.annotate(
        "R",
        xy=(radius, 0.0),
        xytext=(radius * 0.46, radius * 0.1),
        arrowprops={"arrowstyle": "<->", "color": TAIL_COLOR, "lw": 1.4},
        color=TAIL_COLOR,
    )
    ax.text(0.0006, -0.0016, "z axis", color=AXIS_COLOR)
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    ax.set_title("Top view: circular sweep of the helical tail")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, loc="upper right")
    return save_figure(fig, output_dir, f"{prefix}_top_view.png")


def figure_tail_closeup(geometry: dict, output_dir: Path, prefix: str) -> Path:
    fig = plt.figure(figsize=(8.2, 6.8))
    ax = fig.add_subplot(111, projection="3d")
    positions = geometry["positions"]
    directors = geometry["directors"]
    n_body = geometry["n_body_elems"]
    n_elem = geometry["tangents"].shape[1]
    idx = min(n_body + max(5, geometry["n_tail_elems"] // 2), n_elem - 2)
    window = slice(max(n_body, idx - 14), min(positions.shape[1], idx + 16))
    local_positions = positions[:, window]
    ax.plot(local_positions[0], local_positions[1], local_positions[2], color=TAIL_COLOR, lw=3.2)
    point = 0.5 * (positions[:, idx] + positions[:, idx + 1])
    scale = float(geometry["rest_lengths"][idx]) * 2.4
    labels = ("d1", "d2", "d3")
    for d_idx, (color, label) in enumerate(zip(DIRECTOR_COLORS, labels)):
        vec = directors[d_idx, :, idx] * scale
        ax.quiver(
            point[0],
            point[1],
            point[2],
            vec[0],
            vec[1],
            vec[2],
            color=color,
            arrow_length_ratio=0.25,
            linewidth=1.8,
        )
        ax.text(
            point[0] + vec[0] * 1.08,
            point[1] + vec[1] * 1.08,
            point[2] + vec[2] * 1.08,
            label,
            color=color,
            fontsize=9,
        )

    twist_theta = np.linspace(0.0, 1.6 * np.pi, 80)
    tangent = directors[2, :, idx]
    normal_1 = directors[0, :, idx]
    normal_2 = directors[1, :, idx]
    spiral = point[:, None] + tangent[:, None] * np.linspace(-scale, scale, 80)
    spiral += 0.22 * scale * (
        normal_1[:, None] * np.cos(twist_theta) + normal_2[:, None] * np.sin(twist_theta)
    )
    ax.plot(spiral[0], spiral[1], spiral[2], color=TWIST_COLOR, lw=2.0)
    ax.text(spiral[0, 48], spiral[1, 48], spiral[2, 48], "twist", color=TWIST_COLOR, fontsize=10)

    shear_vec = directors[0, :, idx] * scale * 0.75
    shear_base = point - directors[2, :, idx] * scale * 0.65
    ax.quiver(
        shear_base[0],
        shear_base[1],
        shear_base[2],
        shear_vec[0],
        shear_vec[1],
        shear_vec[2],
        color=SHEAR_COLOR,
        arrow_length_ratio=0.22,
        linewidth=1.8,
    )
    ax.text(
        shear_base[0] + shear_vec[0],
        shear_base[1] + shear_vec[1],
        shear_base[2] + shear_vec[2],
        "shear",
        color=SHEAR_COLOR,
        fontsize=10,
    )
    set_equal_3d(ax, local_positions, margin=0.006)
    clean_3d_axes(ax)
    ax.view_init(elev=28, azim=-34)
    ax.set_title("Tail close-up: Cosserat directors, shear, and twist")
    legend_handles = [
        Line2D([0], [0], color=DIRECTOR_COLORS[0], lw=2, label="d1 shear/bending direction"),
        Line2D([0], [0], color=DIRECTOR_COLORS[1], lw=2, label="d2 shear/bending direction"),
        Line2D([0], [0], color=DIRECTOR_COLORS[2], lw=2, label="d3 tangent"),
        Line2D([0], [0], color=SHEAR_COLOR, lw=2, label="sigma shear strain cue"),
        Line2D([0], [0], color=TWIST_COLOR, lw=2, label="kappa_3 twist cue"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False, fontsize=8)
    return save_figure(fig, output_dir, f"{prefix}_tail_directors_closeup.png")


def figure_multi_view_panel(geometry: dict, output_dir: Path, prefix: str) -> Path:
    fig = plt.figure(figsize=(11.0, 8.4))
    gs = fig.add_gridspec(2, 2, hspace=0.28, wspace=0.2)

    ax1 = fig.add_subplot(gs[0, 0], projection="3d")
    draw_geometry_3d(ax1, geometry, lw=2.4)
    add_reference_axis_3d(ax1, geometry)
    set_focused_3d(ax1, geometry["positions"], xy_margin=0.009, z_margin=0.004)
    clean_3d_axes(ax1)
    make_3d_axes_compact(ax1)
    ax1.view_init(elev=22, azim=-58)
    ax1.set_title("3D model")

    ax2 = fig.add_subplot(gs[0, 1])
    body, tail = split_body_tail(geometry)
    ax2.plot(tail[2], tail[0], color=TAIL_COLOR, lw=2.4)
    draw_body_capsule_side(ax2, geometry)
    ax2.axhline(0.0, color=AXIS_COLOR, lw=1.0, ls="--")
    ax2.set_title("Side projection")
    ax2.set_xlabel("z [m]")
    ax2.set_ylabel("x [m]")
    ax2.set_aspect("equal", adjustable="box")
    ax2.grid(True, alpha=0.22)

    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(tail[0], tail[1], color=TAIL_COLOR, lw=2.4)
    draw_body_disk_top(ax3, geometry)
    ax3.scatter([0.0], [0.0], color=AXIS_COLOR, s=20)
    ax3.set_title("Top projection")
    ax3.set_xlabel("x [m]")
    ax3.set_ylabel("y [m]")
    ax3.set_aspect("equal", adjustable="box")
    ax3.grid(True, alpha=0.22)

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis("off")
    y0 = 0.82
    items = [
        (TORQUE_COLOR, "rotation", "endpoint torque Tz drives spin about the z axis"),
        (RFT_COLOR, "RFT drag", "local drag is split into tangent and normal components"),
        (SHEAR_COLOR, "shear sigma", "cross-section displacement relative to centerline tangent"),
        (TWIST_COLOR, "twist kappa_3", "director rotation around the local tangent"),
        ("#111111", "bending kappa_1,2", "curvature of the helical centerline"),
    ]
    for idx, (color, label, text) in enumerate(items):
        y = y0 - idx * 0.16
        ax4.plot([0.05, 0.22], [y, y], color=color, lw=4, solid_capstyle="round")
        ax4.text(0.27, y + 0.035, label, color=color, fontsize=11, fontweight="bold")
        ax4.text(0.27, y - 0.035, text, color="#333333", fontsize=9.5)
    ax4.set_xlim(0.0, 1.0)
    ax4.set_ylim(0.0, 1.0)
    ax4.set_title("Physical law legend", loc="left")

    fig.suptitle("Helical propeller model views and physical quantities", fontsize=15, y=0.98)
    return save_figure(fig, output_dir, f"{prefix}_multi_view_physics_panel.png")


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    geometry = build_geometry(args)
    paths = [
        figure_overview(geometry, output_dir, args.prefix),
        figure_side_view(geometry, output_dir, args.prefix),
        figure_top_view(geometry, output_dir, args.prefix),
        figure_tail_closeup(geometry, output_dir, args.prefix),
        figure_multi_view_panel(geometry, output_dir, args.prefix),
    ]
    print("Generated model figures:")
    for path in paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
