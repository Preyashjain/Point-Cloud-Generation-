"""
Multi-view triangulation via Union-Find track building.

Why this is better than pair-by-pair DLT
-----------------------------------------
The default pipeline triangulates each matched pair independently, so the
same physical feature triangulated from (frame0↔frame5) and from
(frame5↔frame10) produces two slightly different 3D points.

This module instead builds *tracks*: if keypoint K in frame 0 matches
keypoint L in frame 5, and L matches M in frame 10, then K/L/M are
merged into one track.  The track is triangulated once using the widest
available baseline (frames 0 and 10), maximising depth accuracy.

Benefits:
  - Each 3D point is unique — no near-duplicate cloud bloat.
  - Longer baselines → lower depth uncertainty.
  - Pure Python/NumPy/OpenCV — no native library dependencies.
"""

from pathlib import Path
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _union_find_tracks(
    match_results,
    all_features,
    gap: int,
) -> list:
    """Build multi-view observation tracks using Union-Find.

    Each node is (feat_idx, kp_idx).  Matched keypoints across frames
    are unioned into one component = one 3D track.

    Returns a list of tracks; each track is a list of (feat_idx, kp_idx).
    Only tracks with observations from ≥ 2 distinct feature frames are kept.
    """
    from collections import defaultdict

    parent: dict = {}

    def find(x):
        if x not in parent:
            parent[x] = x
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:  # path compression
            parent[x], x = root, parent[x]
        return root

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for feat_idx_0, *_, match in match_results:
        feat_idx_1 = feat_idx_0 + gap
        if feat_idx_1 >= len(all_features) or match.num_matches == 0:
            continue
        for kp0, kp1 in match.matches.numpy():
            union((feat_idx_0, int(kp0)), (feat_idx_1, int(kp1)))

    components: dict = defaultdict(list)
    for node in parent:
        components[find(node)].append(node)

    return [
        comp for comp in components.values()
        if len({fi for fi, _ in comp}) >= 2
    ]


def _reproj_err(R, t_flat, pt3d, K, ref_px):
    """Pixel reprojection error of pt3d against ref_px in the given camera."""
    c = R @ pt3d + t_flat
    if c[2] <= 0:
        return float("inf")
    u = K[0, 0] * c[0] / c[2] + K[0, 2]
    v = K[1, 1] * c[1] / c[2] + K[1, 2]
    return float(np.hypot(u - ref_px[0], v - ref_px[1]))


def _triangulate_tracks(
    tracks: list,
    all_features,
    all_poses: list,
    K: np.ndarray,
    max_reproj_err: float = 0.0,
) -> np.ndarray:
    """DLT-triangulate each track from its widest-baseline view pair.

    For a track observed in frames [0, 5, 10], using frames 0 and 10
    (60° apart) is far more accurate than using 0 and 5 (30° apart).
    This maximises depth accuracy per point without bundle adjustment.
    max_reproj_err: pixel threshold for reprojection check (0 = off).
    Analytical orbit poses have 50–100 px inherent error at high focal
    lengths, so leave this disabled unless poses are precisely calibrated.
    """
    import cv2

    pts3d: list = []

    for track in tracks:
        obs = [(fi, ki) for fi, ki in track if fi < len(all_poses)]
        if len(obs) < 2:
            continue

        # Find the pair with the largest inter-frame rotation angle
        fi0, ki0, fi1, ki1 = obs[0][0], obs[0][1], obs[1][0], obs[1][1]
        if len(obs) > 2:
            best = -1.0
            for a in range(len(obs)):
                for b in range(a + 1, len(obs)):
                    Ra = all_poses[obs[a][0]][0]
                    Rb = all_poses[obs[b][0]][0]
                    cos_a = np.clip(
                        (np.trace(Rb @ Ra.T) - 1.0) / 2.0, -1.0, 1.0
                    )
                    angle = float(np.arccos(cos_a))
                    if angle > best:
                        best = angle
                        fi0, ki0 = obs[a]
                        fi1, ki1 = obs[b]

        R0, t0 = all_poses[fi0]
        R1, t1 = all_poses[fi1]
        t0 = t0.reshape(3, 1).astype(np.float64)
        t1 = t1.reshape(3, 1).astype(np.float64)

        P0 = (K @ np.hstack([R0, t0])).astype(np.float64)
        P1 = (K @ np.hstack([R1, t1])).astype(np.float64)

        pt0_px = all_features[fi0].cpu_keypoints().numpy()[ki0]
        pt1_px = all_features[fi1].cpu_keypoints().numpy()[ki1]

        pts4d = cv2.triangulatePoints(
            P0, P1,
            pt0_px.reshape(2, 1).astype(np.float64),
            pt1_px.reshape(2, 1).astype(np.float64),
        )
        w = pts4d[3, 0]
        if abs(w) < 1e-10:
            continue
        pt3d = pts4d[:3, 0] / w

        z0 = float((R0 @ pt3d + t0.flatten())[2])
        z1 = float((R1 @ pt3d + t1.flatten())[2])
        if z0 <= 0 or z1 <= 0:
            continue

        if max_reproj_err > 0:
            e0 = _reproj_err(R0, t0.flatten(), pt3d, K, pt0_px)
            e1 = _reproj_err(R1, t1.flatten(), pt3d, K, pt1_px)
            if e0 > max_reproj_err or e1 > max_reproj_err:
                continue

        pts3d.append(pt3d)

    return (
        np.array(pts3d, dtype=np.float64)
        if pts3d
        else np.empty((0, 3), dtype=np.float64)
    )


def triangulate_with_hloc(
    all_features,
    match_results,
    gap: int,
    orbit_poses: list,
    K: np.ndarray,
    image_size: tuple[int, int],
    work_dir: Optional[Path] = None,
    verbose: bool = False,
    max_reproj_err: float = 0.0,
) -> np.ndarray:
    """
    Multi-view triangulation using Union-Find track building + DLT.

    Merges all pair-wise matches into multi-view tracks, then triangulates
    each track using its widest-baseline view pair.  Key improvements over
    the default pair-by-pair DLT:

      - Each 3D point is unique: shared keypoints across (0↔5) and (5↔10)
        become one track triangulated with the full (0↔10) baseline.
      - Longer baselines → lower depth uncertainty → sharper cloud.
      - No duplicate near-identical points from adjacent overlapping pairs.

    Note: HLoc + COLMAP triangulation was attempted but crashes on Windows
    due to a FAISS/native library incompatibility.  This pure-Python
    implementation provides the same structural benefit without native deps.
    """
    print("    Tracks: building Union-Find observation tracks …")
    tracks = _union_find_tracks(match_results, all_features, gap)
    print(
        f"    Tracks: {len(tracks):,} multi-view tracks "
        f"from {len(match_results)} pairs"
    )

    print("    Tracks: triangulating (widest-baseline DLT per track) …")
    pts = _triangulate_tracks(
        tracks, all_features, orbit_poses, K, max_reproj_err
    )
    print(f"    Tracks: {len(pts):,} points")
    return pts
