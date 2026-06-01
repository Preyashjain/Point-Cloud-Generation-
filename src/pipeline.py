"""End-to-end pipeline for batch processing"""

import sys
from pathlib import Path
import json
import numpy as np
import open3d as o3d
from typing import Dict, List, Tuple
import logging
from config import DATASET_ROOT, OUTPUT_ROOT

# Setup paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import DataLoader
from core.video_processor import VideoProcessor
from core.reconstructor import PointCloudReconstructor
from core.evaluator import PointCloudEvaluator
from utils.helpers import create_output_dirs, save_metrics_json
from visualization.visualizer import PointCloudVisualizer


class BatchReconstructionPipeline:
    """Batch processing pipeline for multiple parts"""

    def __init__(
        self,
        dataset_root: str,
        output_root: str,
        max_frames: int = 50,
        log_file: str = None,
    ):
        """Initialize pipeline

        Args:
            dataset_root: Root directory of dataset
            output_root: Root directory for outputs
            max_frames: Maximum frames to process per video
            log_file: Optional log file path
        """
        self.dataset_root = Path(dataset_root)
        self.output_dirs = create_output_dirs(output_root)
        self.max_frames = max_frames
        self.data_loader = DataLoader(str(self.dataset_root))
        self.vp = VideoProcessor(sampling_rate=3)

        # Setup logging
        self.logger = self._setup_logging(log_file)

    def _setup_logging(self, log_file: str = None) -> logging.Logger:
        """Setup logging"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        # Console handler
        ch = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # File handler
        if log_file:
            fh = logging.FileHandler(log_file)
            fh.setFormatter(formatter)
            logger.addHandler(fh)

        return logger

    def process_part(
        self,
        part_code: str,
        complexity_level: str = "1_single",
        save_outputs: bool = True,
    ) -> Dict:
        """Process a single part

        Args:
            part_code: Part code (e.g., 'G-LS-I-LO-33')
            complexity_level: Complexity level ('1_single', '2_multiple', '3_stacked')
            save_outputs: Whether to save output files

        Returns:
            Dictionary with results
        """
        results = {
            "part_code": part_code,
            "complexity_level": complexity_level,
            "status": "pending",
            "error": None,
            "orientations": {},
        }

        try:
            self.logger.info(f"Processing {part_code} - Level {complexity_level}")

            # Get part data
            part_data = self.data_loader.get_part_data(part_code, complexity_level)

            # Process each orientation
            for orientation, paths in part_data["orientations"].items():
                try:
                    orientation_result = self._process_orientation(
                        part_code, orientation, paths, save_outputs
                    )
                    results["orientations"][orientation] = orientation_result
                except Exception as e:
                    self.logger.error(
                        f"Failed to process {part_code}/{orientation}: {e}"
                    )
                    results["orientations"][orientation] = {
                        "status": "failed",
                        "error": str(e),
                    }

            # Aggregate results
            successful = sum(
                1
                for o in results["orientations"].values()
                if o.get("status") == "success"
            )
            results["status"] = "success" if successful > 0 else "partial"

        except Exception as e:
            self.logger.error(f"Failed to process {part_code}: {e}")
            results["status"] = "failed"
            results["error"] = str(e)

        return results

    def _process_orientation(
        self, part_code: str, orientation: str, paths: Dict, save_outputs: bool
    ) -> Dict:
        """Process single orientation

        Args:
            part_code: Part code
            orientation: Orientation name
            paths: Dictionary with video and ground_truth paths
            save_outputs: Whether to save outputs

        Returns:
            Dictionary with orientation results
        """
        orient_result = {
            "status": "pending",
            "video_path": paths["video"],
            "metrics": {},
            "files_saved": [],
        }

        # Load video
        frames, video_meta = self.vp.extract_frames(
            paths["video"], max_frames=self.max_frames
        )

        if len(frames) < 3:
            raise ValueError(f"Not enough frames extracted: {len(frames)}")

        self.logger.info(f"  Orientation {orientation}: {len(frames)} frames extracted")

        # Detect keypoints
        keypoint_data = self.vp.detect_keypoints(frames)
        matches_list = self.vp.match_features(keypoint_data)

        total_matches = sum(len(m) for m in matches_list)
        if total_matches < 50:
            self.logger.warning(f"  Few matches found: {total_matches}")

        # Reconstruct
        K = self.vp.estimate_camera_intrinsics(
            video_meta["width"], video_meta["height"]
        )
        reconstructor = PointCloudReconstructor(K=K)

        points_3d, colors = reconstructor.sift_based_reconstruction(
            frames, keypoint_data, matches_list
        )

        if len(points_3d) == 0:
            raise ValueError("No 3D points reconstructed")

        # Create and filter point cloud
        pred_pcd = reconstructor.create_point_cloud(points_3d, colors)
        pred_pcd = reconstructor.filter_outliers(pred_pcd)
        pred_pcd = reconstructor.downsample(pred_pcd, voxel_size=0.01)

        # Load ground truth
        gt_pcd = o3d.io.read_point_cloud(paths["ground_truth"])
        gt_pcd = reconstructor.downsample(gt_pcd, voxel_size=0.01)

        # Alignment
        reg_result = reconstructor.register_to_ground_truth(
            pred_pcd, gt_pcd, max_correspondence_distance=1.0
        )
        pred_pcd = pred_pcd.transform(reg_result.transformation)

        # Evaluation
        metrics = PointCloudEvaluator.point_cloud_metrics(pred_pcd, gt_pcd)
        orient_result["metrics"] = metrics

        # Save outputs
        if save_outputs:
            try:
                # Point cloud
                pcd_path = (
                    self.output_dirs["point_clouds"]
                    / f"{part_code}_{orientation}_reconstructed.ply"
                )
                reconstructor.save_point_cloud(pred_pcd, str(pcd_path))
                orient_result["files_saved"].append(str(pcd_path))

                # Metrics
                metrics_path = (
                    self.output_dirs["evaluations"]
                    / f"{part_code}_{orientation}_metrics.json"
                )
                save_metrics_json(metrics, str(metrics_path))
                orient_result["files_saved"].append(str(metrics_path))

            except Exception as e:
                self.logger.warning(f"Failed to save outputs: {e}")

        orient_result["status"] = "success"
        return orient_result

    def batch_process(
        self, part_codes: List[str] = None, complexity_level: str = "1_single"
    ) -> Dict:
        """Process multiple parts

        Args:
            part_codes: List of part codes to process (None = all)
            complexity_level: Which complexity level to process

        Returns:
            Dictionary with batch results
        """
        if part_codes is None:
            part_codes = self.data_loader.list_parts()

        batch_results = {
            "total_parts": len(part_codes),
            "complexity_level": complexity_level,
            "parts": {},
        }

        for i, part_code in enumerate(part_codes, 1):
            self.logger.info(f"[{i}/{len(part_codes)}] Processing {part_code}")
            result = self.process_part(part_code, complexity_level)
            batch_results["parts"][part_code] = result

        return batch_results

    def save_batch_report(self, batch_results: Dict, output_path: str) -> None:
        """Save batch processing report

        Args:
            batch_results: Batch results dictionary
            output_path: Path to save report
        """
        report = {
            "summary": {
                "total_parts": batch_results["total_parts"],
                "complexity_level": batch_results["complexity_level"],
                "successful": sum(
                    1
                    for p in batch_results["parts"].values()
                    if p["status"] == "success"
                ),
                "failed": sum(
                    1
                    for p in batch_results["parts"].values()
                    if p["status"] == "failed"
                ),
            },
            "details": batch_results,
        }

        # Add aggregated metrics
        all_metrics = []
        for part_result in batch_results["parts"].values():
            for orient_result in part_result.get("orientations", {}).values():
                if "metrics" in orient_result:
                    all_metrics.append(orient_result["metrics"])

        if all_metrics:
            report["aggregated_metrics"] = self._aggregate_metrics(all_metrics)

        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        self.logger.info(f"Saved batch report to {output_path}")

    @staticmethod
    def _aggregate_metrics(metrics_list: List[Dict]) -> Dict:
        """Aggregate metrics across parts

        Args:
            metrics_list: List of metric dictionaries

        Returns:
            Aggregated metrics with mean/std/min/max
        """
        aggregated = {}

        # Collect all metric values
        metric_dict = {}
        for metrics in metrics_list:
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    if key not in metric_dict:
                        metric_dict[key] = []
                    metric_dict[key].append(value)

        # Compute statistics
        for key, values in metric_dict.items():
            aggregated[key] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "count": len(values),
            }

        return aggregated


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Batch point cloud reconstruction")
    parser.add_argument(
        "--dataset", default=DATASET_ROOT, help="Dataset root directory"
    )
    parser.add_argument("--output", default=OUTPUT_ROOT, help="Output root directory")
    parser.add_argument(
        "--max-frames", type=int, default=50, help="Maximum frames to process per video"
    )
    parser.add_argument(
        "--complexity", default="1_single", help="Complexity level to process"
    )
    parser.add_argument(
        "--parts", nargs="+", help="Specific parts to process (None = all)"
    )
    parser.add_argument("--limit", type=int, help="Limit number of parts to process")

    args = parser.parse_args()

    # Initialize pipeline
    pipeline = BatchReconstructionPipeline(
        dataset_root=args.dataset,
        output_root=args.output,
        max_frames=args.max_frames,
        log_file=str(Path(args.output) / "logs" / "batch_processing.log"),
    )

    # Get parts to process
    parts_to_process = args.parts if args.parts else pipeline.data_loader.list_parts()
    if args.limit:
        parts_to_process = parts_to_process[: args.limit]

    # Process
    pipeline.logger.info(f"Starting batch processing of {len(parts_to_process)} parts")
    batch_results = pipeline.batch_process(parts_to_process, args.complexity)

    # Save report
    report_path = Path(args.output) / "batch_report.json"
    pipeline.save_batch_report(batch_results, str(report_path))

    pipeline.logger.info("Batch processing complete!")


if __name__ == "__main__":
    main()
