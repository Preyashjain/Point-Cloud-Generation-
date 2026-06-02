from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from src.config import CameraConfig, RANSACConfig


@dataclass
class PoseResult:
    R: np.ndarray  # [3, 3] rotation (frame1 relative to frame0)
    t: np.ndarray  # [3, 1] unit-length translation direction
    inlier_mask: np.ndarray  # [N] bool — inliers after E + cheirality RANSAC
    num_inliers: int
    K: np.ndarray  # [3, 3] intrinsic matrix used


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
        """Construct the 3×3 intrinsic matrix K from config + image size.

        Modern video cameras have square pixels, so fx and fy are derived
        from the same pixel size (sensor_width / image_width).  Using
        sensor_height for fy is wrong when the video aspect ratio differs
        from the sensor's native ratio (e.g. 16:9 video on a 3:2 sensor
        crops the sensor vertically, reducing the effective sensor height
        from 24.0 mm to ~20.2 mm — an 19% error in fy if ignored).
        """
        h, w = image_size
        pixel_size_mm = self.cam.sensor_width_mm / w  # mm per pixel (square)
        fx = self.cam.fx or (self.cam.focal_length_mm / pixel_size_mm)
        fy = self.cam.fy or fx  # square pixels
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
        pts0: np.ndarray,  # [N, 2] pixel coords in frame 0
        pts1: np.ndarray,  # [N, 2] pixel coords in frame 1
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

        # findEssentialMat may return multiple stacked solutions (9×3, 3×9 …)
        # when RANSAC finds several equally-scored hypotheses.
        # recoverPose requires exactly one 3×3 matrix.
        if E.shape != (3, 3):
            E = E[:3, :3]

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
        pts0: np.ndarray,  # [N, 2] pixel coords in camera 0
        pts1: np.ndarray,  # [N, 2] pixel coords in camera 1
        R0: np.ndarray,  # [3, 3] absolute rotation of camera 0
        t0: np.ndarray,  # [3]  or [3,1] absolute translation of camera 0
        R1: np.ndarray,  # [3, 3] absolute rotation of camera 1
        t1: np.ndarray,  # [3]  or [3,1] absolute translation of camera 1
        K: np.ndarray,  # [3, 3]
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
            inlier_pts0,
            inlier_pts1,
            np.eye(3),
            np.zeros(3),  # camera 0 = world origin
            pose.R,
            pose.t,
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


def filter_by_reprojection(
    pts3d: np.ndarray,
    pts0: np.ndarray,
    pts1: np.ndarray,
    R0: np.ndarray,
    t0: np.ndarray,
    R1: np.ndarray,
    t1: np.ndarray,
    K: np.ndarray,
    max_err: float = 2.0,
) -> np.ndarray:
    """
    Boolean mask of points whose reprojection error is <= max_err pixels in
    both views.  Points that are NaN (behind a camera) always fail.

    Reprojection error measures how far each triangulated point re-projects
    from the original matched keypoint.  High error means the pose model and
    the match disagree — typically due to a false match or an inaccurate
    analytical camera pose — so those points are discarded.
    """
    t0 = t0.reshape(3, 1).astype(np.float64)
    t1 = t1.reshape(3, 1).astype(np.float64)

    not_nan = ~np.isnan(pts3d).any(axis=1)
    mask = not_nan.copy()

    if not_nan.sum() == 0:
        return mask

    p = pts3d[not_nan].T  # [3, M]

    def _project(R, t):
        cam = R @ p + t  # [3, M]
        z = cam[2]
        # Points at or behind the camera get infinite error → auto-rejected
        with np.errstate(divide="ignore", invalid="ignore"):
            u = K[0, 0] * cam[0] / z + K[0, 2]
            v = K[1, 1] * cam[1] / z + K[1, 2]
        return u, v

    u0, v0 = _project(R0, t0)
    u1, v1 = _project(R1, t1)

    ref0 = pts0[not_nan]
    ref1 = pts1[not_nan]
    err0 = np.hypot(u0 - ref0[:, 0], v0 - ref0[:, 1])
    err1 = np.hypot(u1 - ref1[:, 0], v1 - ref1[:, 1])

    mask[not_nan] = (err0 <= max_err) & (err1 <= max_err)
    return mask


def voxel_downsample(pts: np.ndarray, voxel_size: float) -> np.ndarray:
    """Voxel-grid downsampling — keeps one point per voxel cell.

    Uses open3d when available (faster); falls back to a pure-numpy
    implementation that packs voxel indices into a 64-bit key and takes
    the first point per unique key.

    Parameters
    ----------
    pts         [N, 3] float array
    voxel_size  edge length of each voxel cube (same units as pts)

    Returns [M, 3] array, M ≤ N.
    """
    if voxel_size <= 0 or len(pts) == 0:
        return pts

    try:
        import open3d as o3d

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts.astype(np.float64))
        down = pcd.voxel_down_sample(voxel_size)
        return np.asarray(down.points, dtype=pts.dtype)
    except ImportError:
        pass

    # Pure-numpy fallback: pack (ix, iy, iz) into one int64 key
    mins = pts.min(axis=0)
    idx = np.floor((pts - mins) / voxel_size).astype(np.int64)
    # Each dimension capped at 2^20 ≈ 1M voxels; enough for any realistic cloud
    key = (
        (idx[:, 0] << 40)
        | ((idx[:, 1] & 0xFFFFF) << 20)
        | (idx[:, 2] & 0xFFFFF)
    )
    _, first = np.unique(key, return_index=True)
    return pts[np.sort(first)]


def filter_by_density(
    pts: np.ndarray,
    eps: float = 15.0,
    min_neighbors: int = 10,
) -> np.ndarray:
    """Remove points that have fewer than min_neighbors within eps mm.

    Removes isolated false triangulations and small noise clusters that
    survive SOR.  Uses the distance to the k-th nearest neighbour as a
    fast proxy for local density (O(N log N)).

    Valid surface points are packed densely; scattered outliers are not.
    """
    if len(pts) <= min_neighbors:
        return pts
    from scipy.spatial import cKDTree

    tree = cKDTree(pts)
    # dists[:, min_neighbors] = distance to the min_neighbors-th neighbour
    dists, _ = tree.query(pts, k=min_neighbors + 1)
    return pts[dists[:, min_neighbors] <= eps]


def filter_by_center_distance(pts: np.ndarray, max_dist: float) -> np.ndarray:
    """Remove points farther than max_dist from the world origin.

    For orbit-rig captures the object sits at the platform centre (origin).
    Background surfaces (table edge, walls) triangulate far from the origin
    and are cleanly rejected by this simple Euclidean-distance gate.
    """
    return pts[np.linalg.norm(pts, axis=1) <= max_dist]


def filter_outliers(
    pts: np.ndarray,
    k: int = 20,
    std_ratio: float = 2.0,
) -> np.ndarray:
    """
    Statistical outlier removal (SOR).

    For each point compute the mean distance to its k nearest neighbours.
    Points whose mean distance exceeds  mean + std_ratio * std  across the
    whole cloud are discarded.

    Returns the filtered [M, 3] array (M ≤ N).
    """
    if len(pts) <= k + 1:
        return pts

    from scipy.spatial import cKDTree

    tree = cKDTree(pts)
    # query k+1 so we can drop the self-distance (always 0) in col 0
    dists, _ = tree.query(pts, k=k + 1)
    mean_dists = dists[:, 1:].mean(axis=1)
    threshold = mean_dists.mean() + std_ratio * mean_dists.std()
    return pts[mean_dists <= threshold]


def save_ply(
    path,
    points_3d: np.ndarray,
    colors: Optional[np.ndarray] = None,
) -> None:
    """Write a binary-little-endian PLY file. colors must be [N, 3] uint8 when provided."""
    import pathlib
    import struct

    mask = ~np.isnan(points_3d).any(axis=1)
    pts = points_3d[mask].astype(np.float32)
    clr = colors[mask] if colors is not None else None

    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        header = "ply\nformat binary_little_endian 1.0\n"
        header += f"element vertex {len(pts)}\n"
        header += "property float x\nproperty float y\nproperty float z\n"
        if clr is not None:
            header += (
                "property uchar red\n"
                "property uchar green\n"
                "property uchar blue\n"
            )
        header += "end_header\n"
        f.write(header.encode("ascii"))
        if clr is not None:
            clr_u8 = clr.astype(np.uint8)
            for i in range(len(pts)):
                f.write(struct.pack("<fff", pts[i, 0], pts[i, 1], pts[i, 2]))
                f.write(struct.pack("BBB", clr_u8[i, 0], clr_u8[i, 1], clr_u8[i, 2]))
        else:
            f.write(pts.tobytes())
