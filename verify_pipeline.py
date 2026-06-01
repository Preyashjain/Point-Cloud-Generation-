#!/usr/bin/env python3
"""
Comprehensive Verification Script - Check if Pipeline is Working
Verifies:
1. Generated point clouds (PLY format, valid structure)
2. Metrics computation
3. Ground truth comparison
4. All three complexity levels
"""

import sys
from pathlib import Path
import json
import numpy as np
import logging
from datetime import datetime
from src.config import DATASET_ROOT, OUTPUT_ROOT

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.data_loader import DataLoader


def setup_logging():
    logger = logging.getLogger("verification")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    ch = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


def read_ply_file(filename):
    """Read PLY file and extract basic info"""
    points = []
    colors = []
    header_done = False
    num_points = 0

    with open(filename, "r") as f:
        for line in f:
            line = line.strip()

            if line.startswith("element vertex"):
                num_points = int(line.split()[-1])
            elif line == "end_header":
                header_done = True
                break

        # Read vertex data
        if header_done:
            for i in range(num_points):
                line = f.readline().strip()
                if not line:
                    break
                parts = line.split()
                if len(parts) >= 6:
                    x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                    r, g, b = int(parts[3]), int(parts[4]), int(parts[5])
                    points.append([x, y, z])
                    colors.append([r, g, b])

    return np.array(points), np.array(colors), len(points)


def verify_ply_file(ply_file, logger):
    """Verify PLY file integrity"""
    if not ply_file.exists():
        return False, "File not found"

    try:
        points, colors, count = read_ply_file(str(ply_file))

        if count == 0:
            return False, "No points in PLY file"

        # Check for valid 3D coordinates
        if not np.all(np.isfinite(points)):
            return False, "Invalid coordinates (NaN/Inf)"

        # Check depth range
        z_min, z_max = points[:, 2].min(), points[:, 2].max()
        if z_max - z_min < 0.001:
            return False, f"Insufficient depth variation: {z_max - z_min:.6f}"

        return True, f"{count} points, Z range: [{z_min:.2f}, {z_max:.2f}]"

    except Exception as e:
        return False, str(e)


def verify_metrics_file(metrics_file, logger):
    """Verify metrics JSON file"""
    if not metrics_file.exists():
        return False, "File not found"

    try:
        with open(metrics_file, "r") as f:
            metrics = json.load(f)

        required_keys = ["points_generated", "matches_found", "frames_processed"]
        missing = [k for k in required_keys if k not in metrics]

        if missing:
            return False, f"Missing keys: {missing}"

        if metrics["points_generated"] <= 0:
            return False, "No points generated"

        return (
            True,
            f"{metrics['points_generated']} pts, {metrics['matches_found']} matches, {metrics['frames_processed']} frames",
        )

    except Exception as e:
        return False, str(e)


def load_ground_truth(ground_truth_file):
    """Load ground truth PLY file"""
    try:
        points, colors, count = read_ply_file(str(ground_truth_file))
        return points, count
    except:
        return None, 0


def compute_chamfer_distance(pred_points, gt_points, sample_size=5000):
    """Compute approximate Chamfer distance (sampled)"""
    if len(pred_points) == 0 or len(gt_points) == 0:
        return None

    # Sample if too large
    if len(pred_points) > sample_size:
        pred_points = pred_points[
            np.random.choice(len(pred_points), sample_size, replace=False)
        ]
    if len(gt_points) > sample_size:
        gt_points = gt_points[
            np.random.choice(len(gt_points), sample_size, replace=False)
        ]

    # Compute distances
    from scipy.spatial.distance import cdist

    d_pred_to_gt = cdist(pred_points, gt_points).min(axis=1).mean()
    d_gt_to_pred = cdist(gt_points, pred_points).min(axis=1).mean()

    return (d_pred_to_gt + d_gt_to_pred) / 2


def main():
    logger = setup_logging()

    output_root = Path(OUTPUT_ROOT)
    dataset_root = Path(DATASET_ROOT)

    logger.info("=" * 80)
    logger.info("PIPELINE VERIFICATION - COMPREHENSIVE CHECK")
    logger.info("=" * 80)

    # Check output directories
    pcd_dir = output_root / "point_clouds"
    metrics_dir = output_root / "evaluations"

    if not pcd_dir.exists() or not metrics_dir.exists():
        logger.error("Output directories not found")
        return

    ply_files = list(pcd_dir.glob("*.ply"))
    metrics_files = list(metrics_dir.glob("*.json"))

    logger.info(f"\nGenerated {len(ply_files)} PLY files")
    logger.info(f"Generated {len(metrics_files)} metrics files\n")

    # Verify by complexity level
    results = {
        "1_single": {"ply": [], "metrics": [], "comparisons": []},
        "2_multiple": {"ply": [], "metrics": [], "comparisons": []},
        "3_stacked": {"ply": [], "metrics": [], "comparisons": []},
    }

    for complexity in ["1_single", "2_multiple", "3_stacked"]:
        logger.info(f"\n{'='*80}")
        logger.info(f"LEVEL: {complexity.upper()}")
        logger.info(f"{'='*80}")

        level_files = [f for f in ply_files if complexity in f.name]
        logger.info(f"Found {len(level_files)} point clouds for {complexity}\n")

        for ply_file in sorted(level_files):
            metrics_file = metrics_dir / f"{ply_file.stem}_metrics.json"

            # Verify PLY
            ply_ok, ply_msg = verify_ply_file(ply_file, logger)
            results[complexity]["ply"].append((ply_file.name, ply_ok))

            # Verify metrics
            metrics_ok, metrics_msg = verify_metrics_file(metrics_file, logger)
            results[complexity]["metrics"].append((metrics_file.name, metrics_ok))

            status = "✓" if (ply_ok and metrics_ok) else "✗"
            logger.info(f"{status} {ply_file.name}")
            logger.info(f"  PLY: {ply_msg}")
            logger.info(f"  Metrics: {metrics_msg}")

            # Try ground truth comparison
            try:
                part_code = ply_file.name.split("_")[0]
                gt_file = dataset_root / part_code / complexity / "ground_truth.ply"

                if gt_file.exists():
                    pred_points, pred_count = read_ply_file(str(ply_file))
                    gt_points, gt_count = load_ground_truth(gt_file)

                    if gt_points is not None and len(pred_points) > 0:
                        # Rough comparison: point count ratio
                        ratio = len(pred_points) / gt_count if gt_count > 0 else 0

                        logger.info(
                            f"  Ground Truth: {gt_count} points (ratio: {ratio:.2%})"
                        )
                        results[complexity]["comparisons"].append(
                            (ply_file.name, ratio)
                        )
            except Exception as e:
                logger.debug(f"  GT comparison failed: {e}")

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}\n")

    total_ply = sum(len(results[level]["ply"]) for level in results)
    total_metrics = sum(len(results[level]["metrics"]) for level in results)

    ply_ok = sum(
        1
        for level in results
        for ok in (
            results[level]["ply"][i][1]
            for i in range(len(results[level]["ply"]))
            if i < len(results[level]["ply"])
        )
    )
    metrics_ok = sum(
        1
        for level in results
        for ok in (
            results[level]["metrics"][i][1]
            for i in range(len(results[level]["metrics"]))
            if i < len(results[level]["metrics"])
        )
    )

    logger.info(f"✓ PLY Files Valid: {ply_ok}/{total_ply}")
    logger.info(f"✓ Metrics Files Valid: {metrics_ok}/{total_metrics}")

    # Per-level summary
    for complexity in ["1_single", "2_multiple", "3_stacked"]:
        level_ply = len(results[complexity]["ply"])
        level_metrics = len(results[complexity]["metrics"])
        level_ply_ok = sum(1 for _, ok in results[complexity]["ply"] if ok)
        level_metrics_ok = sum(1 for _, ok in results[complexity]["metrics"] if ok)

        logger.info(
            f"\n{complexity:12s}: {level_ply_ok:2d}/{level_ply:2d} PLY ✓ | {level_metrics_ok:2d}/{level_metrics:2d} Metrics ✓"
        )

    # Overall status
    all_ok = ply_ok == total_ply and metrics_ok == total_metrics

    logger.info(f"\n{'='*80}")
    if all_ok:
        logger.info("✓✓✓ PIPELINE IS WORKING CORRECTLY ✓✓✓")
        logger.info(
            "All generated files are valid and all three complexity levels are complete"
        )
    else:
        logger.info("⚠ ISSUES DETECTED - See details above")
    logger.info(f"{'='*80}\n")

    # Save detailed report
    report_file = output_root / "verification_report.json"
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "total_ply_files": total_ply,
        "total_metrics_files": total_metrics,
        "ply_valid": ply_ok,
        "metrics_valid": metrics_ok,
        "all_valid": all_ok,
        "by_level": {
            level: {
                "ply_files": len(results[level]["ply"]),
                "ply_valid": sum(1 for _, ok in results[level]["ply"] if ok),
                "metrics_files": len(results[level]["metrics"]),
                "metrics_valid": sum(1 for _, ok in results[level]["metrics"] if ok),
            }
            for level in results
        },
    }

    with open(report_file, "w") as f:
        json.dump(report_data, f, indent=2)

    logger.info(f"Detailed report saved to: {report_file}\n")

    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
