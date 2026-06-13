"""
Entry point: feature extraction (SuperPoint + LightGlue) +
             3D reconstruction (orbit-rig analytical poses + triangulation) +
             optional depth densification (Depth Anything v2 Small).

Usage:
    python src/main.py                          # first sample
    python src/main.py --all                    # all samples
    python src/main.py --sample G-TS-O-HI-7/1_single
    python src/main.py --list
    python src/main.py --depth                  # + dense depth estimation
    python src/main.py --stride 5 --match-gap 3
    python src/main.py --focal-length 35
    python src/main.py --eval-only                # re-evaluate existing outputs, no reconstruction
    python src/main.py --eval-only --fscore-pcts 1,2,5 --no-icp
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as `python src/main.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from src.config import Config
from src.core.data_loader import (
    DatasetLoader,
    DatasetSample,
    extract_frames,
    video_info,
)
from src.core.colmap_extractor import ColmapExtractor
from src.core.feature_extractor import FeatureExtractor, FrameFeatures
from src.core.hloc_triangulator import triangulate_with_hloc
from src.core.reconstructor import (
    Reconstructor,
    filter_by_center_distance,
    filter_by_density,
    filter_by_reprojection,
    filter_outliers,
    save_ply,
    voxel_downsample,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SuperPoint + LightGlue + orbit-rig 3D reconstruction"
    )
    p.add_argument(
        "--sample",
        type=str,
        default=None,
        help="Sample ID, e.g. 'G-TS-O-HI-7/1_single'",
    )
    p.add_argument(
        "--all", action="store_true", help="Process every sample in the dataset"
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
        help="Stop after this many extracted frames per sample",
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
        "--match-gap",
        type=int,
        default=8,
        help=(
            "Extracted-frame distance between matched pairs (default: 8). "
            "With stride=5 this is 40° per pair — good depth accuracy while "
            "staying within LightGlue's reliable matching range."
        ),
    )
    p.add_argument(
        "--match-step",
        type=int,
        default=1,
        help=(
            "Step between consecutive pair start-frames (default: 1 = overlapping pairs). "
            "Use --match-step equal to --match-gap for non-overlapping pairs."
        ),
    )
    p.add_argument(
        "--no-orbit", action="store_true", help="Fall back to E-matrix pose estimation"
    )
    p.add_argument(
        "--use-hloc",
        action="store_true",
        help=(
            "Use Union-Find multi-view track building instead of pair-by-pair DLT. "
            "Works well for general SfM; for orbital rigs with stride<10 the "
            "chains can span >180° and match different physical surfaces — "
            "use with caution."
        ),
    )
    p.add_argument(
        "--coverage",
        type=float,
        default=None,
        help="Orbit coverage in degrees (default: 360)",
    )
    p.add_argument(
        "--outlier-k",
        type=int,
        default=20,
        help="k-NN count for statistical outlier removal (0 = off)",
    )
    p.add_argument(
        "--outlier-std",
        type=float,
        default=2.5,
        help="Std-deviation multiplier for SOR threshold (default: 2.5)",
    )
    p.add_argument(
        "--h-filter",
        action="store_true",
        help="Enable homography pre-filter before E-matrix RANSAC",
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
    p.add_argument(
        "--feature-extractor",
        type=str,
        default="superpoint",
        choices=["superpoint", "sift"],
        help=(
            "Feature extractor: 'superpoint' (default, GPU, LightGlue matching) "
            "or 'sift' (COLMAP SIFT + FLANN, CPU, typically 10-30x more keypoints)"
        ),
    )
    p.add_argument(
        "--eval-only",
        action="store_true",
        help=(
            "Skip reconstruction; load existing sparse/dense PLY outputs and "
            "evaluate them against ground truth"
        ),
    )
    p.add_argument(
        "--fscore-pcts",
        type=str,
        default=None,
        metavar="1,2,5",
        help=(
            "Comma-separated F-score thresholds as %% of GT bounding-box diagonal "
            "(default: 1,2,5)"
        ),
    )
    p.add_argument(
        "--no-icp",
        action="store_true",
        help="Disable ICP refinement during evaluation (faster, less accurate alignment)",
    )
    p.add_argument(
        "--eval-format",
        type=str,
        default="compact",
        choices=["compact", "box"],
        help=(
            "Evaluation output format: 'compact' (default) prints plain ASCII "
            "key=value lines with a SUMMARY line — easy to paste into an LLM prompt. "
            "'box' prints the Unicode table."
        ),
    )
    p.add_argument(
        "--reproj-err",
        type=float,
        default=0.0,
        help=(
            "Max reprojection error in pixels for triangulated points; "
            "removes points where the pose model and the match disagree. "
            "Default 0 = off (appropriate for analytical orbit poses whose "
            "geometric uncertainty is typically 10–100 px; use SOR instead). "
            "Only enable when orbit parameters are precisely calibrated."
        ),
    )
    p.add_argument(
        "--dense-voxel",
        type=float,
        default=1.0,
        metavar="MM",
        help=(
            "Voxel size for downsampling the dense cloud before saving and "
            "evaluation (default: 1.0 units = keeps ~1 pt per 1 mm cube). "
            "0 = off (can produce 10M+ pts and hours of evaluation time)."
        ),
    )
    p.add_argument(
        "--eval-max-pts",
        type=int,
        default=500_000,
        metavar="N",
        help=(
            "Randomly subsample the predicted cloud to at most N points "
            "before evaluation (default: 500000). "
            "0 = off. Reduces cKDTree query time for large dense clouds."
        ),
    )
    return p.parse_args()


def _parse_fscore_pcts(args: argparse.Namespace) -> tuple[float, ...]:
    """Convert '--fscore-pcts 1,2,5' → (0.01, 0.02, 0.05)."""
    if args.fscore_pcts is None:
        return (0.01, 0.02, 0.05)
    return tuple(float(x.strip()) / 100.0 for x in args.fscore_pcts.split(","))


def _run_depth_densification(
    entries: list,
    all_features,
    all_frames: list,
    K: np.ndarray,
    depth_estimator,
    cfg,
    base_out: Path,
    sample: "DatasetSample",
    args: "argparse.Namespace",
) -> None:
    """Densify each frame with Depth Anything v2 using sparse entries as scale.

    Shared by both the DLT and HLoc triangulation paths.
    entries: list of (world_pts [N,3], R_cw [3,3], t [3,1], feat_idx).
    """
    from src.core.depth_estimator import densify_frame

    print(f"\n  Densifying with Depth Anything v2 ({cfg.depth.model_size}) …")
    all_dense_pts: list[np.ndarray] = []
    all_dense_colors: list[np.ndarray] = []

    # DepthEstimator works in metres; our orbit geometry is in mm.
    # Convert the sparse camera-space reference points to metres before
    # densify_frame so the depth model's max_depth clip (5 m) is correct,
    # then convert the returned camera-space points back to mm.
    MM_TO_M = 1e-3
    M_TO_MM = 1e3

    for world_pts, R_f0, t_f0, feat_idx_0 in entries:
        if feat_idx_0 >= len(all_frames):
            continue
        sparse_cam = (R_f0 @ world_pts.T + t_f0).T  # [N, 3] mm
        valid_front = sparse_cam[:, 2] > 0
        if valid_front.sum() < 4:
            continue

        sparse_cam_m = sparse_cam[valid_front] * MM_TO_M  # mm → m
        pts_cam_m, colors = densify_frame(
            all_frames[feat_idx_0],
            sparse_cam_m,
            K,
            depth_estimator,
        )
        pts_cam = pts_cam_m * M_TO_MM  # m → mm

        # Remove background: keep only depth ≤ 2.5× orbit distance.
        # Background walls/floor are typically 1–4 m away; the object is
        # ~D mm from every camera, so 2.5×D is a generous object margin.
        orbit_d_mm = float(np.sqrt(cfg.orbit.radius_mm**2 + cfg.orbit.height_mm**2))
        fg_mask = pts_cam[:, 2] < orbit_d_mm * 2.5
        pts_cam = pts_cam[fg_mask]
        if colors is not None:
            colors = colors[fg_mask]

        if len(pts_cam) == 0:
            continue

        pts_world = (R_f0.T @ (pts_cam.T - t_f0)).T

        # Keep only points near the platform centre (object zone).
        # Floor/walls that survived the camera-depth gate are far from
        # the world origin and are removed here.
        max_obj_dist = min(cfg.orbit.radius_mm, cfg.orbit.height_mm) * 0.75
        center_mask = np.linalg.norm(pts_world, axis=1) <= max_obj_dist
        pts_world = pts_world[center_mask]
        if colors is not None:
            colors = colors[center_mask]

        all_dense_pts.append(pts_world)
        if colors is not None:
            all_dense_colors.append(colors)
        print(
            f"    frame {all_features[feat_idx_0].frame_idx:5d}  "
            f"→  {len(pts_world):,} dense points"
        )

    if not all_dense_pts:
        print("  No dense points generated.")
        return

    merged_pts = np.vstack(all_dense_pts)
    merged_colors = (
        np.vstack(all_dense_colors)
        if len(all_dense_colors) == len(all_dense_pts)
        else None
    )

    # Voxel downsample before saving — depth back-projection produces
    # millions of near-duplicate points per frame that bloat the file and
    # make evaluation intractably slow without reducing accuracy.
    voxel = getattr(args, "dense_voxel", 2.0)
    if voxel > 0 and len(merged_pts) > 0:
        n_before = len(merged_pts)
        merged_pts = voxel_downsample(merged_pts, voxel)
        if merged_colors is not None:
            merged_colors = None  # colors can't be sensibly downsampled
        print(
            f"\n  Voxel filter ({voxel} units): "
            f"{n_before:,} → {len(merged_pts):,} points"
        )

    save_ply(base_out / "dense.ply", merged_pts, merged_colors)
    print(f"\n  Dense : {len(merged_pts):,} pts  →  {base_out / 'dense.ply'}")
    _run_evaluation(
        merged_pts,
        sample,
        base_out,
        tag="dense",
        fscore_pcts=_parse_fscore_pcts(args),
        use_icp=not args.no_icp,
        eval_format=args.eval_format,
        focal_length_mm=cfg.camera.focal_length_mm,
        max_eval_pts=getattr(args, "eval_max_pts", 500_000),
    )


def _run_evaluation(
    pts: np.ndarray,
    sample: "DatasetSample",
    base_out: Path,
    tag: str,
    fscore_pcts: tuple[float, ...] = (0.01, 0.02, 0.05),
    use_icp: bool = True,
    eval_format: str = "compact",
    focal_length_mm: float | None = None,
    max_eval_pts: int = 0,
) -> None:
    """Evaluate *pts* against the sample's ground-truth PLY and print results."""
    if not sample.ground_truth_path.exists():
        return
    from src.core.evaluation import (
        evaluate,
        load_ply_points,
        print_results,
        print_results_compact,
        save_results,
    )

    # Randomly subsample very large predicted clouds so cKDTree queries
    # complete in seconds rather than hours.  GT stays at full resolution
    # so recall is always computed against the complete ground truth.
    eval_pts = pts
    if max_eval_pts > 0 and len(pts) > max_eval_pts:
        idx = np.random.choice(len(pts), max_eval_pts, replace=False)
        eval_pts = pts[idx]
        print(
            f"  Eval: subsampled pred {len(pts):,} → {max_eval_pts:,} pts "
            f"(use --eval-max-pts 0 to disable)"
        )

    title = f"Evaluation: {sample.sample_id} | {tag} vs ground truth"
    print()
    try:
        gt_pts = load_ply_points(sample.ground_truth_path)
        results = evaluate(eval_pts, gt_pts, use_icp=use_icp, fscore_pcts=fscore_pcts)
        if eval_format == "compact":
            print_results_compact(results, title=title)
        else:
            print_results(results, title=title)
        save_results(results, base_out / f"evaluation_{tag}.json")
        print(f"  Results -> {base_out / f'evaluation_{tag}.json'}")
        _print_scale_hint(results.get("scale_factor", 1.0), focal_length_mm)
    except Exception as exc:
        print(f"  Evaluation failed: {exc}")


def _print_scale_hint(scale: float, focal_length_mm: float | None) -> None:
    """When scale deviates > 5% from 1.0, print a corrected-focal-length suggestion.

    Empirically, in orbital SfM scale ≈ (focal_used / focal_true)^2:
    - scale < 1 → pred cloud is too large → focal_used is too short → increase it
    - scale > 1 → pred cloud is too small → focal_used is too long → decrease it

    Correction: focal_target = focal_current / sqrt(scale)
    (dividing by sqrt(scale) because scale ∝ focal^2)
    """
    if abs(scale - 1.0) <= 0.05 or focal_length_mm is None:
        return
    corrected = focal_length_mm / (scale**0.5)
    direction = "too short" if scale < 1.0 else "too long"
    print(
        f"  Scale hint: factor={scale:.4f} (pred cloud is {1/scale:.2f}x GT size).\n"
        f"    Assumed focal length {focal_length_mm:.0f} mm may be {direction}.\n"
        f"    Try: --focal-length {corrected:.0f}"
    )


def process_sample(
    sample: DatasetSample,
    args: argparse.Namespace,
    cfg: Config,
    extractor: FeatureExtractor,
    reconstructor: Reconstructor,
    depth_estimator,  # DepthEstimator | None
) -> None:
    """Run the full pipeline for a single dataset sample."""
    info = video_info(sample.video_path)
    print(
        f"  Video  : {info['frame_count']} frames  "
        f"{info['width']}x{info['height']}  {info['fps']:.1f} fps"
    )
    print(
        f"  Stride : {cfg.dataset.frame_stride}  "
        f"(≈ {info['frame_count'] // cfg.dataset.frame_stride} frames)\n"
    )

    # --- Feature extraction ---
    all_features: list[FrameFeatures] = []
    all_frames: list[np.ndarray] = []
    for frame_idx, frame_rgb in extract_frames(
        sample.video_path, cfg.dataset.frame_stride
    ):
        feats = extractor.extract(frame_rgb, frame_idx)
        all_features.append(feats)
        if args.depth:
            all_frames.append(frame_rgb)
        print(f"    frame {frame_idx:5d}  →  {feats.num_keypoints:4d} keypoints")
        if args.max_frames and len(all_features) >= args.max_frames:
            break

    print(f"\n  Extracted {len(all_features)} frames.")

    if args.no_match or len(all_features) < 2:
        return

    # --- LightGlue matching ---
    gap = args.match_gap
    step = args.match_step
    n_pairs = len(range(0, len(all_features) - gap, step))
    if n_pairs == 0:
        min_frames = gap + 1
        suggested_gap = max(1, len(all_features) // 2)
        print(
            f"\n  No pairs to match: match-gap={gap} >= extracted frames "
            f"({len(all_features)}).\n"
            f"  Fix: use --max-frames {min_frames * 2} or --match-gap {suggested_gap}."
        )
        return
    print(
        f"\n  Matching frame pairs (gap={gap}, step={step}, total={n_pairs}) with LightGlue:"
    )
    match_results = []
    for i in range(0, len(all_features) - gap, step):
        f0, f1 = all_features[i], all_features[i + gap]
        m = extractor.match(f0, f1)
        match_results.append((i, f0, f1, m))
        print(
            f"    frame {f0.frame_idx:5d} ↔ {f1.frame_idx:5d}  "
            f"→ {m.num_matches:4d} matches  "
            f"(score: {m.matching_scores.mean():.3f})"
        )

    if args.no_reconstruct:
        return

    # --- 3D reconstruction ---
    print("\n  Reconstructing 3D points:")
    image_size = all_features[0].image_size
    K = reconstructor.build_K(image_size)
    print(
        f"    K  fx={K[0, 0]:.1f}  fy={K[1, 1]:.1f}  "
        f"cx={K[0, 2]:.1f}  cy={K[1, 2]:.1f}  "
        f"(focal={cfg.camera.focal_length_mm} mm)"
    )

    use_orbit = not args.no_orbit
    base_out = cfg.output_dir / sample.object_id / sample.scenario
    if sample.orientation:
        base_out = base_out / sample.orientation
    entries: list[tuple[np.ndarray, np.ndarray, np.ndarray, int]] = []

    if use_orbit:
        from src.core.orbit import poses_for_video

        fc = info["frame_count"]
        D = np.sqrt(cfg.orbit.radius_mm**2 + cfg.orbit.height_mm**2)
        all_poses = poses_for_video(
            cfg.orbit,
            fc,
            cfg.dataset.frame_stride,
            len(all_features),
        )
        print(
            f"    Orbit  R={cfg.orbit.radius_mm:.0f} mm  "
            f"H={cfg.orbit.height_mm:.0f} mm  "
            f"D={D:.1f} mm  coverage={cfg.orbit.coverage_deg:.0f}°"
        )

        if args.use_hloc:
            # --- HLoc multi-view triangulation ---
            # All pairs are triangulated simultaneously using COLMAP's track
            # builder, giving much stronger per-point constraints than DLT.
            sparse_pts = triangulate_with_hloc(
                all_features=all_features,
                match_results=match_results,
                gap=gap,
                orbit_poses=all_poses,
                K=K,
                image_size=image_size,
                verbose=False,
            )
            if len(sparse_pts) == 0:
                print("\n  HLoc produced no points.")
                return
            # Skip entries / depth path — save and evaluate directly
            if args.outlier_k > 0:
                n_before = len(sparse_pts)
                sparse_pts = filter_outliers(
                    sparse_pts, k=args.outlier_k, std_ratio=args.outlier_std
                )
                print(
                    f"\n  Outlier filter: {n_before:,} → {len(sparse_pts):,} points "
                    f"({n_before - len(sparse_pts):,} removed)"
                )
            max_obj_dist = min(cfg.orbit.radius_mm, cfg.orbit.height_mm) * 0.75
            n_before = len(sparse_pts)
            sparse_pts = filter_by_center_distance(sparse_pts, max_obj_dist)
            if len(sparse_pts) < n_before:
                print(
                    f"\n  Center filter (<{max_obj_dist:.0f} mm): "
                    f"{n_before:,} → {len(sparse_pts):,} points"
                )
            n_before = len(sparse_pts)
            sparse_pts = filter_by_density(sparse_pts, eps=15.0, min_neighbors=10)
            if len(sparse_pts) < n_before:
                print(
                    f"\n  Density filter: "
                    f"{n_before:,} → {len(sparse_pts):,} points"
                )
            save_ply(base_out / "sparse.ply", sparse_pts)
            print(
                f"\n  Sparse (HLoc): {len(sparse_pts):,} pts  "
                f"→  {base_out / 'sparse.ply'}"
            )
            _run_evaluation(
                sparse_pts,
                sample,
                base_out,
                tag="sparse",
                fscore_pcts=_parse_fscore_pcts(args),
                use_icp=not args.no_icp,
                eval_format=args.eval_format,
                focal_length_mm=cfg.camera.focal_length_mm,
            )
            if args.depth and depth_estimator is not None and all_frames:
                # Each orbit frame uses the full global sparse cloud as scale
                # reference; only points in front of that camera are kept.
                hloc_entries = [
                    (sparse_pts, all_poses[i][0], all_poses[i][1], i)
                    for i in range(min(len(all_poses), len(all_frames)))
                ]
                _run_depth_densification(
                    hloc_entries,
                    all_features,
                    all_frames,
                    K,
                    depth_estimator,
                    cfg,
                    base_out,
                    sample,
                    args,
                )
            return

        # --- Pair-by-pair DLT (default) ---
        for feat_idx_0, f0, f1, match in match_results:
            feat_idx_1 = feat_idx_0 + gap
            if feat_idx_1 >= len(all_poses) or match.num_matches < 4:
                continue

            R_f0, t_f0 = all_poses[feat_idx_0]
            R_f1, t_f1 = all_poses[feat_idx_1]
            pts0 = f0.cpu_keypoints().numpy()[match.matches[:, 0]]
            pts1 = f1.cpu_keypoints().numpy()[match.matches[:, 1]]

            pts3d = reconstructor.triangulate(
                pts0,
                pts1,
                R_f0,
                t_f0,
                R_f1,
                t_f1,
                K,
            )
            if args.reproj_err > 0:
                valid = filter_by_reprojection(
                    pts3d, pts0, pts1, R_f0, t_f0, R_f1, t_f1, K, args.reproj_err
                )
            else:
                valid = ~np.isnan(pts3d).any(axis=1)
            R_rel = R_f1 @ R_f0.T
            angle_deg = np.degrees(np.arccos(np.clip((np.trace(R_rel) - 1) / 2, -1, 1)))
            print(
                f"    frame {f0.frame_idx:5d} ↔ {f1.frame_idx:5d}  "
                f"angle={angle_deg:.1f}°  "
                f"matches={match.num_matches:4d}  pts3d={valid.sum():5d}"
            )
            if valid.sum() > 0:
                entries.append((pts3d[valid], R_f0, t_f0, feat_idx_0))

    else:
        R_abs, t_abs = np.eye(3), np.zeros((3, 1))

        for feat_idx_0, f0, f1, match in match_results:
            R_f0, t_f0 = R_abs.copy(), t_abs.copy()
            if match.num_matches < 8:
                continue

            pts0 = f0.cpu_keypoints()[match.matches[:, 0]].numpy()
            pts1 = f1.cpu_keypoints()[match.matches[:, 1]].numpy()
            pose = reconstructor.estimate_pose(
                pts0,
                pts1,
                image_size,
                use_homography_filter=args.h_filter,
            )
            if pose is None:
                continue

            R_rel = pose.R
            t_rel = pose.t.reshape(3, 1)
            angle_deg = np.degrees(np.arccos(np.clip((np.trace(R_rel) - 1) / 2, -1, 1)))
            if angle_deg < 0.5:
                continue

            R_f1 = R_rel @ R_f0
            t_f1 = R_rel @ t_f0 + t_rel
            inlier_pts0 = pts0[pose.inlier_mask]
            inlier_pts1 = pts1[pose.inlier_mask]
            pts3d = reconstructor.triangulate(
                inlier_pts0,
                inlier_pts1,
                R_f0,
                t_f0,
                R_f1,
                t_f1,
                K,
            )
            if args.reproj_err > 0:
                valid = filter_by_reprojection(
                    pts3d,
                    inlier_pts0,
                    inlier_pts1,
                    R_f0,
                    t_f0,
                    R_f1,
                    t_f1,
                    K,
                    args.reproj_err,
                )
            else:
                valid = ~np.isnan(pts3d).any(axis=1)
            print(
                f"    frame {f0.frame_idx:5d} ↔ {f1.frame_idx:5d}  "
                f"rot={angle_deg:.1f}°  inliers={pose.num_inliers:4d}  "
                f"pts3d={valid.sum():5d}"
            )
            if valid.sum() > 0:
                entries.append((pts3d[valid], R_f0, t_f0, feat_idx_0))
            R_abs, t_abs = R_f1, t_f1

    if not entries:
        print("\n  No 3D points reconstructed.")
        return

    sparse_pts = np.vstack([e[0] for e in entries])

    if args.outlier_k > 0:
        n_before = len(sparse_pts)
        sparse_pts = filter_outliers(
            sparse_pts,
            k=args.outlier_k,
            std_ratio=args.outlier_std,
        )
        print(
            f"\n  Outlier filter: {n_before:,} → {len(sparse_pts):,} points "
            f"({n_before - len(sparse_pts):,} removed)"
        )

    if use_orbit:
        max_obj_dist = min(cfg.orbit.radius_mm, cfg.orbit.height_mm) * 0.75
        n_before = len(sparse_pts)
        sparse_pts = filter_by_center_distance(sparse_pts, max_obj_dist)
        if len(sparse_pts) < n_before:
            print(
                f"\n  Center filter (<{max_obj_dist:.0f} mm): "
                f"{n_before:,} → {len(sparse_pts):,} points"
            )
        n_before = len(sparse_pts)
        sparse_pts = filter_by_density(sparse_pts, eps=15.0, min_neighbors=10)
        if len(sparse_pts) < n_before:
            print(
                f"\n  Density filter: "
                f"{n_before:,} → {len(sparse_pts):,} points"
            )

    save_ply(base_out / "sparse.ply", sparse_pts)
    print(f"\n  Sparse: {len(sparse_pts):,} pts  →  {base_out / 'sparse.ply'}")

    _run_evaluation(
        sparse_pts,
        sample,
        base_out,
        tag="sparse",
        fscore_pcts=_parse_fscore_pcts(args),
        use_icp=not args.no_icp,
        eval_format=args.eval_format,
        focal_length_mm=cfg.camera.focal_length_mm,
    )

    if args.depth and depth_estimator is not None:
        _run_depth_densification(
            entries,
            all_features,
            all_frames,
            K,
            depth_estimator,
            cfg,
            base_out,
            sample,
            args,
        )


def eval_sample(sample: DatasetSample, args: argparse.Namespace, cfg: Config) -> None:
    """Load existing sparse/dense PLY outputs and evaluate against ground truth."""
    from src.core.evaluation import (
        evaluate,
        load_ply_points,
        print_results,
        print_results_compact,
        save_results,
    )

    base_out = cfg.output_dir / sample.object_id / sample.scenario
    if sample.orientation:
        base_out = base_out / sample.orientation

    if not sample.ground_truth_path.exists():
        print("  No ground truth found — skipping.")
        return

    gt_pts = load_ply_points(sample.ground_truth_path)
    fscore_pcts = _parse_fscore_pcts(args)
    use_icp = not args.no_icp

    found_any = False
    for tag in ("sparse", "dense"):
        ply_path = base_out / f"{tag}.ply"
        if not ply_path.exists():
            continue
        found_any = True
        print(f"\n  Evaluating {ply_path} ...")
        try:
            pred_pts = load_ply_points(ply_path)
            results = evaluate(
                pred_pts, gt_pts, use_icp=use_icp, fscore_pcts=fscore_pcts
            )
            if args.eval_format == "compact":
                print_results_compact(
                    results,
                    title=f"Evaluation: {sample.sample_id} | {tag} vs ground truth",
                )
            else:
                print_results(
                    results,
                    title=f"Evaluation: {sample.sample_id} | {tag} vs ground truth",
                )
            out_json = base_out / f"evaluation_{tag}.json"
            save_results(results, out_json)
            print(f"  Results -> {out_json}")
            _print_scale_hint(
                results.get("scale_factor", 1.0), cfg.camera.focal_length_mm
            )
        except Exception as exc:
            print(f"  Evaluation failed: {exc}")

    if not found_any:
        print(
            f"  No PLY outputs found under {base_out} — run without --eval-only first."
        )


def main() -> None:
    args = parse_args()
    cfg = Config()

    if args.stride is not None:
        cfg.dataset.frame_stride = args.stride
    if args.device is not None:
        cfg.device = args.device
    if args.coverage is not None:
        cfg.orbit.coverage_deg = args.coverage
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
                f"{info['width']}x{info['height']}  {info['fps']:.1f} fps"
            )
        return

    # --- Select samples ---
    if args.all:
        selected = samples
    elif args.sample:
        matched = [s for s in samples if s.sample_id == args.sample]
        if not matched:
            print(f"Sample '{args.sample}' not found. Use --list to see all.")
            sys.exit(1)
        selected = matched
    else:
        selected = [samples[0]]

    # --- Eval-only: skip model loading and reconstruction entirely ---
    if args.eval_only:
        n = len(selected)
        for i, sample in enumerate(selected):
            print(f"\n{'=' * 60}")
            print(f"[{i + 1}/{n}] {sample.sample_id}")
            print("=" * 60)
            eval_sample(sample, args, cfg)
        if n > 1:
            print(f"\n{'=' * 60}")
            print(f"Done — evaluated {n} samples.")
        return

    # --- Initialize models once (reused across all samples) ---
    if args.feature_extractor == "sift":
        extractor = ColmapExtractor(cfg.sift)
    else:
        extractor = FeatureExtractor(cfg.superpoint, cfg.lightglue, cfg.device)
    reconstructor = Reconstructor(cfg.camera, cfg.ransac)
    print(f"Device : {extractor.device}")

    depth_estimator = None
    if args.depth:
        from src.core.depth_estimator import DepthEstimator

        depth_estimator = DepthEstimator(cfg.depth, cfg.device)
        print(f"Depth  : Depth Anything v2 {cfg.depth.model_size} loaded")

    # --- Process ---
    n = len(selected)
    for i, sample in enumerate(selected):
        header = f"[{i + 1}/{n}] {sample.sample_id}"
        print(f"\n{'=' * 60}")
        print(header)
        print("=" * 60)
        try:
            process_sample(
                sample,
                args,
                cfg,
                extractor,
                reconstructor,
                depth_estimator,
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")
            if n == 1:
                raise

    if n > 1:
        print(f"\n{'=' * 60}")
        print(f"Done — processed {n} samples.")


if __name__ == "__main__":
    main()
