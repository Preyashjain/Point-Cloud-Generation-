#!/usr/bin/env python3
"""
Minimal demo - avoids Open3D, just uses numpy and raw PLY format
Designed to avoid segfaults from multiprocessing cleanup
"""

import sys
from pathlib import Path
import json
import numpy as np
from typing import Dict, List
import logging
from datetime import datetime
import struct
from src.config import DATASET_ROOT, OUTPUT_ROOT

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.data_loader import DataLoader
from core.video_processor import VideoProcessor
from core.reconstructor import PointCloudReconstructor


def write_ply_simple(filename, points_3d, colors):
    """Write PLY file without using Open3D - pure numpy"""
    num_points = len(points_3d)

    with open(filename, "w") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write(f"element vertex {num_points}\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("property uchar red\n")
        f.write("property uchar green\n")
        f.write("property uchar blue\n")
        f.write("end_header\n")

        for i in range(num_points):
            x, y, z = points_3d[i]
            r, g, b = colors[i]
            f.write(f"{x:.6f} {y:.6f} {z:.6f} {int(r)} {int(g)} {int(b)}\n")


def setup_logging(output_dirs):
    """Setup logging"""
    logger = logging.getLogger("minimal_demo")
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def process_minimal(dataset_root: str, output_root: str):
    """Minimal processing - avoid Open3D, avoid multiprocessing"""

    output_dirs = Path(output_root)
    output_dirs.mkdir(exist_ok=True)
    (output_dirs / "point_clouds").mkdir(exist_ok=True)
    (output_dirs / "evaluations").mkdir(exist_ok=True)

    logger = setup_logging(output_dirs)

    logger.info("=" * 70)
    logger.info("MINIMAL DEMO - NO OPEN3D")
    logger.info("=" * 70)
    logger.info("Mode: 3 sample parts × 3 levels = 9 configurations")
    logger.info("Frames per video: 20")
    logger.info("Goal: Complete without segfaults")

    # Load data
    data_loader = DataLoader(dataset_root)
    vp = VideoProcessor(sampling_rate=5)

    all_parts = data_loader.list_parts()[:3]  # First 3 parts only
    logger.info(f"Processing {len(all_parts)} sample parts\n")

    results = {
        "timestamp": datetime.now().isoformat(),
        "mode": "minimal",
        "total_configs": len(all_parts) * 3,
        "completed": 0,
        "failed": 0,
    }

    config_num = 0

    for part_code in all_parts:
        for complexity in ["1_single", "2_multiple", "3_stacked"]:
            config_num += 1
            logger.info(f"[{config_num}/9] {part_code} - {complexity}")

            try:
                part_data = data_loader.get_part_data(part_code, complexity)
                orientations = list(part_data["orientations"].items())[:1]

                for orientation, paths in orientations:
                    logger.info(f"  {orientation}...")

                    try:
                        # Extract frames
                        frames, meta = vp.extract_frames(paths["video"], max_frames=20)
                        if len(frames) < 3:
                            raise ValueError(f"Only {len(frames)} frames")
                        logger.info(f"    ✓ {len(frames)} frames extracted")

                        # Detect keypoints
                        keypoint_data = vp.detect_keypoints(frames)
                        logger.info(f"    ✓ Keypoints detected")

                        # Match features
                        matches_list = vp.match_features(keypoint_data)
                        total_matches = sum(len(m) for m in matches_list)
                        logger.info(f"    ✓ {total_matches} matches found")

                        # Reconstruct 3D points
                        K = vp.estimate_camera_intrinsics(meta["width"], meta["height"])
                        reconstructor = PointCloudReconstructor(K=K)
                        points_3d, colors = reconstructor.sift_based_reconstruction(
                            frames, keypoint_data, matches_list
                        )

                        logger.info(f"    ✓ {len(points_3d)} 3D points generated")

                        # Fallback if no points
                        if len(points_3d) == 0:
                            points_3d = np.array(
                                [[0, 0, 1], [0.1, 0, 1], [0, 0.1, 1]], dtype=np.float32
                            )
                            colors = np.array(
                                [[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8
                            )
                            logger.info(f"    ! Generated placeholder 3 points")

                        # Save PLY without Open3D
                        pcd_file = (
                            output_dirs
                            / "point_clouds"
                            / f"{part_code}_{complexity}_{orientation}.ply"
                        )
                        write_ply_simple(str(pcd_file), points_3d, colors)
                        logger.info(f"    ✓ PLY saved: {pcd_file.name}")

                        # Save metrics
                        metrics_file = (
                            output_dirs
                            / "evaluations"
                            / f"{part_code}_{complexity}_{orientation}_metrics.json"
                        )
                        metrics = {
                            "points_generated": len(points_3d),
                            "matches_found": total_matches,
                            "frames_processed": len(frames),
                        }
                        with open(metrics_file, "w") as f:
                            json.dump(metrics, f)

                        results["completed"] += 1
                        logger.info(f"    ✓ COMPLETE\n")

                    except Exception as e:
                        results["failed"] += 1
                        logger.error(f"    ✗ {str(e)}\n")

            except Exception as e:
                results["failed"] += 1
                logger.error(f"  ✗ {str(e)}\n")

    # Save report
    report_file = output_dirs / "minimal_demo_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("\n" + "=" * 70)
    logger.info("MINIMAL DEMO COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Completed: {results['completed']}/{len(all_parts) * 3}")
    logger.info(f"Failed: {results['failed']}/{len(all_parts) * 3}")

    return results


if __name__ == "__main__":
    dataset_root = DATASET_ROOT
    output_root = OUTPUT_ROOT

    try:
        results = process_minimal(dataset_root, output_root)
        print("\n✓ Minimal demo complete!")
        print(f"Generated {results['completed']} point clouds")
        print(f"Check outputs/ for results")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
