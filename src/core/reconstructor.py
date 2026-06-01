from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from src.config import CameraConfig, RANSACConfig


@dataclass
class PoseResult:
    R: np.ndarray            # [3, 3] rotation (frame1 relative to frame0)
    t: np.ndarray            # [3, 1] unit-length translation direction
    inlier_mask: np.ndarray  # [N] bool — inliers after E + cheirality RANSAC
    num_inliers: int
    K: np.ndarray            # [3, 3] intrinsic matrix used


@dataclass
class ReconstructionResult:
    points_3d: np.ndarray  # [M, 3] metric-up-to-scale triangulated points
    frame0_idx: int
    frame1_idx: int
    pose: PoseResult


class Reconstructor:
    """
    RANSAC-based pose estimation and triangulation using the Essential matrix.

    Pipeline per frame pair:
      1. Homography RANSAC  – 4-DOF filter exploiting the constrained
                              orbital motion (approx. pure rotation)
      2. Essential matrix   – 5 DOF (uses known K, avoids F's 7 DOF)
      3. recoverPose        – decomposes E into R, t with cheirality check
      4. triangulatePoints  – DLT triangulation in camera-0 coordinates
    """

    def __init__(self, camera_cfg: CameraConfig, ransac_cfg: RANSACConfig):
        self.cam = camera_cfg
        self.ransac = ransac_cfg

    # ------------------------------------------------------------------
    # Intrinsics
    # ------------------------------------------------------------------

    def build_K(self, image_size: tuple[int, int]) -> np.ndarray:
        """Construct the 3×3 intrinsic matrix K from config + image size."""
        h, w = image_size
        fx = self.cam.fx or (
            self.cam.focal_length_mm / self.cam.sensor_width_mm * w
        )
        fy = self.cam.fy or (
            self.cam.focal_length_mm / self.cam.sensor_height_mm * h
        )
        cx = self.cam.cx if self.cam.cx is not None else w / 2.0
        cy = self.cam.cy if self.cam.cy is not None else h / 2.0
        return np.array(
            [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    # Step 1 — homography pre-filter
    # ------------------------------------------------------------------

    def _homography_inlier_mask(
        self, pts0: np.ndarray, pts1: np.ndarray
    ) -> np.ndarray:
        """
        Find correspondences consistent with a homography via RANSAC.

        For the orbit rig, consecutive frames undergo mostly rotation with a
        small translation.  A homography (4 DOF for a rotating camera over a
        dominant plane) is a tight geometric constraint that removes spurious
        matches before the Essential-matrix fit.
        """
        _, mask = cv2.findHomography(
            pts0,
            pts1,
            method=cv2.RANSAC,
            ransacReprojThreshold=self.ransac.threshold,
            confidence=self.ransac.confidence,
            maxIters=self.ransac.max_iters,
        )
        if mask is None:
            return np.ones(len(pts0), dtype=bool)
        return mask.ravel().astype(bool)

    # ------------------------------------------------------------------
    # Step 2+3 — Essential matrix + pose recovery
    # ------------------------------------------------------------------

    def estimate_pose(
        self,
        pts0: np.ndarray,           # [N, 2] pixel coords in frame 0
        pts1: np.ndarray,           # [N, 2] pixel coords in frame 1
        image_size: tuple[int, int],
        use_homography_filter: bool = True,
    ) -> Optional[PoseResult]:
        """
        Estimate relative pose between two frames.

        Returns None when fewer than 5 correspondences survive or RANSAC fails.
        """
        K = self.build_K(image_size)
        pts0 = pts0.astype(np.float64)
        pts1 = pts1.astype(np.float64)
        n_orig = len(pts0)

        # survivor_mask tracks which of the *original* N points are still live.
        # All downstream masks are local (M-element); we compose them back so
        # the returned inlier_mask is always N-element and indexes correctly
        # into the caller's original arrays.
        survivor_mask = np.ones(n_orig, dtype=bool)

        # --- Homography pre-filter (optional) ---
        if use_homography_filter and len(pts0) >= 4:
            h_mask = self._homography_inlier_mask(pts0, pts1)
            survivor_mask &= h_mask
            pts0, pts1 = pts0[h_mask], pts1[h_mask]

        if len(pts0) < 5:
            return None

        # --- Essential matrix (5 DOF) via RANSAC ---
        # K is known → skip F (7 DOF); work in calibrated coordinates
        E, e_mask = cv2.findEssentialMat(
            pts0,
            pts1,
            K,
            method=cv2.RANSAC,
            prob=self.ransac.confidence,
            threshold=self.ransac.threshold,
            maxIters=self.ransac.max_iters,
        )
        if E is None or e_mask is None:
            return None

        # --- recoverPose: decompose E → (R, t) + cheirality check ---
        # Cheirality selects the valid solution where inlier points have
        # positive depth in both cameras → metric R and unit-length t.
        mask_io = e_mask.copy()  # recoverPose modifies the mask in-place
        num_inliers, R, t, final_mask = cv2.recoverPose(
            E, pts0, pts1, K, mask=mask_io
        )

        # Map the local M-element result back to the original N-element space
        local_inlier = final_mask.ravel() > 0
        full_inlier_mask = np.zeros(n_orig, dtype=bool)
        full_inlier_mask[survivor_mask] = local_inlier

        return PoseResult(
            R=R,
            t=t,
            inlier_mask=full_inlier_mask,
            num_inliers=num_inliers,
            K=K,
        )

    # ------------------------------------------------------------------
    # Step 4 — triangulation
    # ------------------------------------------------------------------

    def triangulate(
        self,
        pts0: np.ndarray,   # [N, 2] pixel coords in camera 0
        pts1: np.ndarray,   # [N, 2] pixel coords in camera 1
        R0: np.ndarray,     # [3, 3] absolute rotation of camera 0
        t0: np.ndarray,     # [3]  or [3,1] absolute translation of camera 0
        R1: np.ndarray,     # [3, 3] absolute rotation of camera 1
        t1: np.ndarray,     # [3]  or [3,1] absolute translation of camera 1
        K: np.ndarray,      # [3, 3]
    ) -> np.ndarray:
        """
        DLT triangulation in world frame using absolute camera poses.

        Convention: X_cam = R @ X_world + t
        Returns [N, 3] world-frame points; points behind either camera → NaN.
        """
        if len(pts0) == 0:
            return np.empty((0, 3), dtype=np.float64)

        t0 = t0.reshape(3, 1).astype(np.float64)
        t1 = t1.reshape(3, 1).astype(np.float64)

        # triangulatePoints requires float64, C-contiguous [3,4] matrices
        P0 = np.ascontiguousarray(
            K @ np.hstack([R0.astype(np.float64), t0]), dtype=np.float64
        )
        P1 = np.ascontiguousarray(
            K @ np.hstack([R1.astype(np.float64), t1]), dtype=np.float64
        )
        pts0_mat = np.ascontiguousarray(pts0.T, dtype=np.float64)
        pts1_mat = np.ascontiguousarray(pts1.T, dtype=np.float64)

        pts4d = cv2.triangulatePoints(P0, P1, pts0_mat, pts1_mat)
        w = pts4d[3]
        with np.errstate(divide="ignore", invalid="ignore"):
            pts3d = (pts4d[:3] / w).T  # [N, 3] world frame

        # Discard points behind either camera
        z0 = (R0 @ pts3d.T + t0)[2]
        z1 = (R1 @ pts3d.T + t1)[2]
        pts3d[(z0 <= 0) | (z1 <= 0)] = np.nan

        return pts3d

    # ------------------------------------------------------------------
    # Full pair pipeline
    # ------------------------------------------------------------------

    def reconstruct(
        self,
        pts0: np.ndarray,
        pts1: np.ndarray,
        image_size: tuple[int, int],
        frame0_idx: int = 0,
        frame1_idx: int = 1,
        use_homography_filter: bool = True,
    ) -> Optional[ReconstructionResult]:
        """Estimate pose + triangulate for one matched frame pair."""
        pose = self.estimate_pose(
            pts0, pts1, image_size, use_homography_filter
        )
        if pose is None:
            return None

        inlier_pts0 = pts0[pose.inlier_mask]
        inlier_pts1 = pts1[pose.inlier_mask]
        pts3d = self.triangulate(
            inlier_pts0, inlier_pts1,
            np.eye(3), np.zeros(3),   # camera 0 = world origin
            pose.R, pose.t,
            pose.K,
        )

        return ReconstructionResult(
            points_3d=pts3d,
            frame0_idx=frame0_idx,
            frame1_idx=frame1_idx,
            pose=pose,
        )


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------


def save_ply(
    path,
    points_3d: np.ndarray,
    colors: Optional[np.ndarray] = None,
) -> None:
    """Write an ASCII PLY file. colors must be [N, 3] uint8 when provided."""
    import pathlib

    mask = ~np.isnan(points_3d).any(axis=1)
    pts = points_3d[mask]
    clr = colors[mask] if colors is not None else None

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(pts)}\n")
        f.write(
            "property float x\nproperty float y\nproperty float z\n"
        )
        if clr is not None:
            f.write(
                "property uchar red\n"
                "property uchar green\n"
                "property uchar blue\n"
            )
        f.write("end_header\n")
        for i, p in enumerate(pts):
            line = f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}"
            if clr is not None:
                r, g, b = int(clr[i, 0]), int(clr[i, 1]), int(clr[i, 2])
                line += f" {r} {g} {b}"
            f.write(line + "\n")


def save_obj(
    path,
    points_3d: np.ndarray,
    colors: Optional[np.ndarray] = None,
) -> None:
    """
    Write a Wavefront OBJ point-cloud file.

    Vertices are written as  'v x y z'  (no color) or  'v x y z r g b'
    (extended format, r/g/b in [0, 1], supported by MeshLab and CloudCompare).
    Each vertex is also emitted as a 'p' point element so that viewers that
    require explicit geometry render something.
    """
    import pathlib

    mask = ~np.isnan(points_3d).any(axis=1)
    pts = points_3d[mask]
    clr = colors[mask] if colors is not None else None

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("# Point cloud exported by Point-Cloud-Generation\n")
        f.write(f"# Vertices: {len(pts)}\n\n")

        for i, p in enumerate(pts):
            if clr is not None:
                r = clr[i, 0] / 255.0
                g = clr[i, 1] / 255.0
                b = clr[i, 2] / 255.0
                f.write(
                    f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f} "
                    f"{r:.6f} {g:.6f} {b:.6f}\n"
                )
            else:
                f.write(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")

        f.write("\n")
        for i in range(1, len(pts) + 1):
            f.write(f"p {i}\n")
