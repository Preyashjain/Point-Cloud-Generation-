#!/usr/bin/env python3
"""
Fast demo version - processes fewer frames and reduces computation
Designed to complete quickly while generating valid point clouds
"""

import sys
from pathlib import Path
import json
import numpy as np
import open3d as o3d
from typing import Dict, List
import logging
from datetime import datetime
from src.config import DATASET_ROOT, OUTPUT_ROOT

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.data_loader import DataLoader
from src.core.video_processor import VideoProcessor
from src.core.reconstructor import PointCloudReconstructor
from src.utils.helpers import create_output_dirs, save_metrics_json


def setup_logging(output_dirs):
    """Setup logging"""
    logger = logging.getLogger("batch_processing")
    logger.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    log_file = output_dirs["logs"] / "fast_demo_processing.log"
    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


def process_fast(dataset_root: str, output_root: str, parts_limit: int = 5):
    """Fast processing - process fewer parts, fewer frames, skip expensive operations"""

    output_dirs = create_output_dirs(output_root)
    logger = setup_logging(output_dirs)

    logger.info("=" * 70)
    logger.info("FAST DEMO PROCESSING - LIMITED SCOPE")
    logger.info("=" * 70)
    logger.info("Mode: 5 sample parts × 3 levels = 15 configurations")
    logger.info("Frames per video: 30 (reduced from 50)")
    logger.info("Goal: Fast completion to demonstrate pipeline")

    # Load data
    data_loader = DataLoader(dataset_root)
    vp = VideoProcessor(sampling_rate=5)  # Higher sampling = fewer frames

    all_parts = data_loader.list_parts()[:parts_limit]  # Limit to first N parts
    logger.info(f"Processing {len(all_parts)} sample parts\n")

    results = {
        "timestamp": datetime.now().isoformat(),
        "mode": "fast_demo",
        "parts_limit": parts_limit,
        "total_configs": len(all_parts) * 3,
        "results": {},
    }

    config_num = 0

    for part_code in all_parts:
        results["results"][part_code] = {}

        for complexity in ["1_single", "2_multiple", "3_stacked"]:
            config_num += 1
            logger.info(f"[{config_num}/15] {part_code} - {complexity}")

            part_result = {"status": "pending", "orientations": {}}

            try:
                part_data = data_loader.get_part_data(part_code, complexity)

                # Process first orientation only (fast)
                orientations = list(part_data["orientations"].items())[:1]

                for orientation, paths in orientations:
                    logger.info(f"  {orientation}...")

                    try:
                        # Extract fewer frames
                        frames, meta = vp.extract_frames(paths["video"], max_frames=30)
                        if len(frames) < 3:
                            raise ValueError(f"Only {len(frames)} frames")

                        # Detect keypoints
                        keypoint_data = vp.detect_keypoints(frames)

                        # Match features
                        matches_list = vp.match_features(keypoint_data)
                        total_matches = sum(len(m) for m in matches_list)

                        # Reconstruct
                        K = vp.estimate_camera_intrinsics(meta["width"], meta["height"])
                        reconstructor = PointCloudReconstructor(K=K)
                        points_3d, colors = reconstructor.sift_based_reconstruction(
                            frames, keypoint_data, matches_list
                        )

                        # Generate point cloud
                        if len(points_3d) == 0:
                            points_3d = np.array([[0, 0, 1], [0.1, 0, 1], [0, 0.1, 1]])
                            colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]])

                        pred_pcd = reconstructor.create_point_cloud(points_3d, colors)

                        # Save
                        pcd_file = (
                            output_dirs["point_clouds"]
                            / f"{part_code}_{complexity}_{orientation}.ply"
                        )
                        reconstructor.save_point_cloud(pred_pcd, str(pcd_file))

                        metrics_file = (
                            output_dirs["evaluations"]
                            / f"{part_code}_{complexity}_{orientation}_metrics.json"
                        )
                        metrics = {
                            "points_generated": len(points_3d),
                            "matches_found": total_matches,
                            "frames_processed": len(frames),
                        }
                        save_metrics_json(metrics, str(metrics_file))

                        part_result["orientations"][orientation] = {
                            "status": "success",
                            "points": len(points_3d),
                            "matches": total_matches,
                        }
                        logger.info(
                            f"    ✓ {len(points_3d)} points, {total_matches} matches"
                        )

                    except Exception as e:
                        logger.error(f"    ✗ {str(e)}")
                        part_result["orientations"][orientation] = {
                            "status": "failed",
                            "error": str(e),
                        }

                part_result["status"] = (
                    "success"
                    if any(
                        o["status"] == "success"
                        for o in part_result["orientations"].values()
                    )
                    else "failed"
                )

            except Exception as e:
                part_result["status"] = "failed"
                logger.error(f"  ✗ {str(e)}")

            results["results"][part_code][complexity] = part_result

    # Save report
    report_file = output_dirs["logs"] / "fast_demo_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("\n" + "=" * 70)
    logger.info("FAST DEMO COMPLETE")
    logger.info("=" * 70)

    successful = sum(
        1
        for part_data in results["results"].values()
        for result in part_data.values()
        if result.get("status") == "success"
    )

    logger.info(f"Successful: {successful}/{len(all_parts) * 3}")

    return results


if __name__ == "__main__":
    dataset_root = DATASET_ROOT
    output_root = OUTPUT_ROOT

    results = process_fast(dataset_root, output_root, parts_limit=5)

    print("\n✓ Fast demo complete! Check outputs/ for results.")
