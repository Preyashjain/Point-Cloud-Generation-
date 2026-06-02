"""
Analytical camera-pose computation for the orbit rig.

Rig geometry (source: dataset/README.txt):
  - Nikon D780 on a circular rail at 40 cm horizontal distance from the
    platform centre axis and 41 cm height, tilted at ~45° inclination.

Coordinate convention (world frame, Y-up):
  - Platform centre at origin [0, 0, 0].
  - Orbit in the X-Z plane; at theta=0 the camera is in the +X direction.
  - Y axis points straight up.

For a camera at orbit angle theta, its centre is:
    C(theta) = [R*cos(theta), H, R*sin(theta)]

where R = horizontal radius, H = height above platform.

The camera looks toward the platform centre (origin), tilted downward
at inclination = atan(H/R) ≈ 45°.  The camera never rolls.

Resulting rotation matrix (world-to-camera) and translation:
    R_cw  — 3×3, rows are camera X/Y/Z axes expressed in world frame
    t     — [0, 0, D] in camera frame, where D = sqrt(R²+H²)
             i.e. the platform centre is always at depth D on the
             optical axis, regardless of theta.
"""

import numpy as np

from src.config import OrbitConfig


def orbit_pose(
    theta: float,
    radius_mm: float,
    height_mm: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (R_cw [3,3], t [3,1]) for a camera at orbit angle *theta* (rad).

    Convention: X_cam = R_cw @ X_world + t
    """
    R = float(radius_mm)
    H = float(height_mm)
    D = float(np.sqrt(R * R + H * H))
    c, s = np.cos(theta), np.sin(theta)

    # Camera axes in world frame:
    #   x_cam (right)   : tangential to the orbit circle
    #   y_cam (down)    : in the vertical plane containing optical axis
    #   z_cam (forward) : from camera toward platform centre
    R_cw = np.array(
        [
            [-s, 0.0, c],  # x_cam
            [-H * c / D, R / D, -H * s / D],  # y_cam
            [-R * c / D, -H / D, -R * s / D],  # z_cam
        ],
        dtype=np.float64,
    )

    # Platform centre is at depth D along the optical axis in camera frame
    t = np.array([[0.0], [0.0], [D]], dtype=np.float64)

    return R_cw, t


def poses_for_video(
    orbit_cfg: OrbitConfig,
    frame_count: int,
    frame_stride: int,
    n_extracted: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """
    Return one (R_cw, t) per *extracted* frame (index 0 … n_extracted-1).

    The i-th extracted frame corresponds to video frame  i * frame_stride.
    Assuming the video covers `coverage_deg` degrees of the orbit uniformly.
    """
    coverage = np.radians(orbit_cfg.coverage_deg)
    poses = []
    for i in range(n_extracted):
        video_frame = i * frame_stride
        theta = coverage * video_frame / frame_count
        R_cw, t = orbit_pose(theta, orbit_cfg.radius_mm, orbit_cfg.height_mm)
        poses.append((R_cw, t))
    return poses
