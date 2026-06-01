"""
Entry point: feature extraction (SuperPoint + LightGlue) +
             3D reconstruction (Essential matrix RANSAC + triangulation) +
             optional depth densification (Depth Anything v2 Small).

Usage:
    python src/main.py                              # first sample, sparse only
    python src/main.py --depth                      # + dense depth estimation
    python src/main.py --sample G-TS-O-HI-7/1_single
    python src/main.py --list
    python src/main.py --stride 5 --max-frames 20
    python src/main.py --focal-length 35
    python src/main.py --no-match
    python src/main.py --no-reconstruct
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as `python src/main.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from src.config import Config
from src.core.data_loader import DatasetLoader, extract_frames, video_info
from src.core.feature_extractor import FeatureExtractor, FrameFeatures
from src.core.reconstructor import Reconstructor, save_ply, save_obj


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SuperPoint + LightGlue + Essential-matrix reconstruction "
        "+ optional Depth Anything v2 densification"
    )
    p.add_argument(
        "--sample",
        type=str,
        default=None,
        help="Sample ID, e.g. 'G-TS-O-HI-7/1_single'",
    )
    p.add_argument(
        "--list", action="store_true", help="List all dataset samples and exit"
    )
    p.add_argument(
        "--stride", type=int, default=None, help="Frame stride (default: 10)"
    )
    p.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Stop after this many extracted frames",
    )
    p.add_argument(
        "--focal-length",
        type=float,
        default=None,
        help="Lens focal length in mm (default: 50)",
    )
    p.add_argument(
        "--no-match",
        action="store_true",
        help="Skip LightGlue matching and reconstruction",
    )
    p.add_argument(
        "--no-reconstruct",
        action="store_true",
        help="Skip 3D reconstruction, run matching only",
    )
    p.add_argument(
        "--no-h-filter",
        action="store_true",
        help="Disable homography pre-filter in RANSAC",
    )
    p.add_argument(
        "--depth", action="store_true", help="Densify each frame with Depth Anything v2"
    )
    p.add_argument(
        "--depth-model",
        type=str,
        default=None,
        choices=["Small", "Base", "Large"],
        help="Depth Anything v2 model size (default: Small)",
    )
    p.add_argument(
        "--device", type=str, default=None, help="Force device: 'cuda' or 'cpu'"
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = Config()

    if args.stride is not None:
        cfg.dataset.frame_stride = args.stride
    if args.device is not None:
        cfg.device = args.device
    if args.focal_length is not None:
        cfg.camera.focal_length_mm = args.focal_length
    if args.depth_model is not None:
        cfg.depth.model_size = args.depth_model

    loader = DatasetLoader(cfg.dataset.root)
    samples = loader.discover()

    if not samples:
        print(f"No samples found under '{cfg.dataset.root}'.")
        sys.exit(1)

    if args.list:
        print(f"Found {len(samples)} samples:")
        for s in samples:
            info = video_info(s.video_path)
            print(
                f"  {s.sample_id:45s}  "
                f"{info['frame_count']:5d} frames  "
                f"{info['width']}x{info['height']}  "
                f"{info['fps']:.1f} fps"
            )
        return

    # --- Select sample ---
    if args.sample:
        matches = [s for s in samples if s.sample_id == args.sample]
        if not matches:
            print(f"Sample '{args.sample}' not found. Use --list to see all.")
            sys.exit(1)
        sample = matches[0]
    else:
        sample = samples[0]

    print(f"Sample : {sample.sample_id}")
    info = video_info(sample.video_path)
    print(
        f"Video  : {info['frame_count']} frames  "
        f"{info['width']}x{info['height']}  "
        f"{info['fps']:.1f} fps"
    )
    print(
        f"Stride : {cfg.dataset.frame_stride}  "
        f"(≈ {info['frame_count'] // cfg.dataset.frame_stride} frames)"
    )

    # --- Feature extraction ---
    extractor = FeatureExtractor(cfg.superpoint, cfg.lightglue, cfg.device)
    print(f"Device : {extractor.device}\n")

    all_features: list[FrameFeatures] = []
    all_frames: list[np.ndarray] = []  # kept for depth densification
    for frame_idx, frame_rgb in extract_frames(
        sample.video_path, cfg.dataset.frame_stride
    ):
        feats = extractor.extract(frame_rgb, frame_idx)
        all_features.append(feats)
        if args.depth:
            all_frames.append(frame_rgb)
        print(f"  frame {frame_idx:5d}  ->  {feats.num_keypoints:4d} keypoints")
        if args.max_frames and len(all_features) >= args.max_frames:
            break

    print(f"\nExtracted {len(all_features)} frames.")

    if args.no_match or len(all_features) < 2:
        return

    # --- LightGlue matching ---
    print("\nMatching consecutive frame pairs with LightGlue:")
    match_results = []
    for i in range(len(all_features) - 1):
        f0, f1 = all_features[i], all_features[i + 1]
        m = extractor.match(f0, f1)
        match_results.append((f0, f1, m))
        print(
            f"  frame {f0.frame_idx:5d} ↔ {f1.frame_idx:5d}  "
            f"-> {m.num_matches:4d} matches  "
            f"(mean score: {m.matching_scores.mean():.3f})"
        )

    if args.no_reconstruct:
        return

    # --- Sparse 3D reconstruction with pose chaining ---
    #
    # Problem with independent per-pair reconstruction: each pair triangulates
    # in its own camera-0 coordinate system, so stacking results is incoherent.
    #
    # Fix: chain relative poses (R_rel, t_rel) from consecutive pairs into
    # absolute poses (R_abs, t_abs) for every frame, then triangulate all
    # pairs using those absolute projection matrices so every 3D point lands
    # in the SAME world frame (= camera-0 frame of the first frame).
    #
    # Convention: X_cam = R_abs @ X_world + t_abs
    print("\nReconstructing 3D points (pose chaining + Essential matrix):")
    reconstructor = Reconstructor(cfg.camera, cfg.ransac)
    image_size = all_features[0].image_size
    K = reconstructor.build_K(image_size)
    print(
        f"  K  fx={K[0,0]:.1f}  fy={K[1,1]:.1f}  "
        f"cx={K[0,2]:.1f}  cy={K[1,2]:.1f}  "
        f"(focal={cfg.camera.focal_length_mm} mm)\n"
    )

    # Absolute poses for every extracted frame (initialised to identity)
    cam_Rs: list[np.ndarray] = [np.eye(3)]
    cam_ts: list[np.ndarray] = [np.zeros((3, 1))]

    # World-frame sparse points + per-frame index (for depth densification)
    world_pts_per_frame: list[np.ndarray] = []  # sparse pts in world frame
    frame_indices: list[int] = []  # which list index each entry belongs to

    base_out = cfg.output_dir / sample.object_id / sample.scenario

    for list_idx, (f0, f1, match) in enumerate(match_results):
        R_prev, t_prev = cam_Rs[-1], cam_ts[-1]

        if match.num_matches < 8:
            # Not enough matches — keep camera stationary (best fallback)
            cam_Rs.append(R_prev.copy())
            cam_ts.append(t_prev.copy())
            print(
                f"  frame {f0.frame_idx:5d} ↔ {f1.frame_idx:5d}  "
                "— skipped (too few matches)"
            )
            continue

        kp0 = f0.cpu_keypoints()
        kp1 = f1.cpu_keypoints()
        pts0 = kp0[match.matches[:, 0]].numpy()
        pts1 = kp1[match.matches[:, 1]].numpy()

        # Estimate RELATIVE pose between consecutive frames
        pose = reconstructor.estimate_pose(
            pts0,
            pts1,
            image_size,
            use_homography_filter=not args.no_h_filter,
        )

        if pose is None:
            cam_Rs.append(R_prev.copy())
            cam_ts.append(t_prev.copy())
            print(
                f"  frame {f0.frame_idx:5d} ↔ {f1.frame_idx:5d}  "
                "— pose estimation failed"
            )
            continue

        # Compose relative pose with previous absolute pose
        # R_new = R_rel @ R_prev,  t_new = R_rel @ t_prev + t_rel
        R_rel = pose.R
        t_rel = pose.t.reshape(3, 1)
        R_new = R_rel @ R_prev
        t_new = R_rel @ t_prev + t_rel
        cam_Rs.append(R_new)
        cam_ts.append(t_new)

        # Triangulate with ABSOLUTE projection matrices → points in world frame
        inlier_pts0 = pts0[pose.inlier_mask]
        inlier_pts1 = pts1[pose.inlier_mask]

        pts3d = reconstructor.triangulate(
            inlier_pts0,
            inlier_pts1,
            R_prev,
            t_prev,
            R_new,
            t_new,
            K,
        )

        valid = ~np.isnan(pts3d).any(axis=1)
        angle_deg = np.degrees(np.arccos(np.clip((np.trace(R_rel) - 1) / 2, -1, 1)))
        print(
            f"  frame {f0.frame_idx:5d} ↔ {f1.frame_idx:5d}  "
            f"inliers={pose.num_inliers:4d}  "
            f"pts3d={valid.sum():5d}  "
            f"rot={angle_deg:.2f}°"
        )

        if valid.sum() > 0:
            world_pts_per_frame.append(pts3d[valid])
            frame_indices.append(list_idx)

    if not world_pts_per_frame:
        print("\nNo 3D points reconstructed.")
        return

    sparse_pts = np.vstack(world_pts_per_frame)
    valid_count = len(sparse_pts)
    save_ply(base_out / "sparse.ply", sparse_pts)
    print(
        f"\nSparse: {valid_count:,} points  →  "
        f"{base_out / 'sparse.ply'}  |  {base_out / 'sparse.obj'}"
    )

    if not args.depth:
        return

    # --- Depth densification (Depth Anything v2) ---
    #
    # For each frame k with absolute pose (R_k, t_k):
    #   1. Transform sparse WORLD points to camera-k frame for depth alignment
    #   2. Predict relative depth, align to metric using sparse cam-k points
    #   3. Backproject dense depth → camera-k 3D
    #   4. Transform back to WORLD frame: X_world = R_k^T @ (X_cam - t_k)
    from src.core.depth_estimator import DepthEstimator, densify_frame

    print(f"\nDensifying with Depth Anything v2 ({cfg.depth.model_size}) …")
    depth_estimator = DepthEstimator(cfg.depth, cfg.device)

    all_dense_pts: list[np.ndarray] = []
    all_dense_colors: list[np.ndarray] = []

    for entry_idx, list_idx in enumerate(frame_indices):
        # Absolute pose of this frame (list_idx + 1 because cam_Rs[0] is frame 0)
        cam_idx = list_idx + 1
        if cam_idx >= len(cam_Rs):
            continue
        R_k = cam_Rs[cam_idx]
        t_k = cam_ts[cam_idx]
        frame_rgb = all_frames[list_idx]

        # Sparse world points → camera-k frame for depth scale alignment
        sparse_world = world_pts_per_frame[entry_idx]
        sparse_camk = (R_k @ sparse_world.T + t_k).T
        valid_front = sparse_camk[:, 2] > 0
        if valid_front.sum() < 4:
            continue

        pts3d_camk, colors = densify_frame(
            frame_rgb, sparse_camk[valid_front], K, depth_estimator
        )

        # Camera-k → world:  X_world = R_k^T @ (X_cam - t_k)
        pts3d_world = (R_k.T @ (pts3d_camk.T - t_k)).T

        all_dense_pts.append(pts3d_world)
        if colors is not None:
            all_dense_colors.append(colors)

        f_idx = all_features[list_idx].frame_idx
        print(f"  frame {f_idx:5d}  →  {len(pts3d_world):,} dense points")

    if not all_dense_pts:
        print("No dense points generated.")
        return

    merged_pts = np.vstack(all_dense_pts)
    merged_colors = (
        np.vstack(all_dense_colors)
        if len(all_dense_colors) == len(all_dense_pts)
        else None
    )
    save_ply(base_out / "dense.ply", merged_pts, merged_colors)
    print(f"\nDense : {len(merged_pts):,} points  →  " f"{base_out / 'dense.ply'}")


if __name__ == "__main__":
    main()
