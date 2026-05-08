"""Visualization utilities for point clouds and results"""
import numpy as np
import open3d as o3d
import cv2
from pathlib import Path
from typing import List, Optional
import matplotlib.pyplot as plt


class PointCloudVisualizer:
    """Utilities for visualizing point clouds and reconstruction results"""
    
    @staticmethod
    def visualize_point_clouds(pred_pcd: o3d.geometry.PointCloud,
                              gt_pcd: o3d.geometry.PointCloud = None,
                              title: str = "Point Cloud Visualization") -> None:
        """Visualize point clouds in 3D
        
        Args:
            pred_pcd: Predicted point cloud
            gt_pcd: Ground truth point cloud (optional)
            title: Window title
        """
        geometries = [pred_pcd]
        
        if gt_pcd is not None:
            # Color GT in red, prediction in blue
            pred_pcd.paint_uniform_color([0, 0, 1])  # Blue
            gt_pcd.paint_uniform_color([1, 0, 0])     # Red
            geometries = [pred_pcd, gt_pcd]
        
        o3d.visualization.draw_geometries(geometries, window_name=title)
    
    @staticmethod
    def save_point_cloud_visualization(pred_pcd: o3d.geometry.PointCloud,
                                      gt_pcd: o3d.geometry.PointCloud,
                                      output_path: str,
                                      voxel_size: float = 0.005) -> None:
        """Save visualization of point clouds as image
        
        Args:
            pred_pcd: Predicted point cloud
            gt_pcd: Ground truth point cloud
            output_path: Path to save visualization
            voxel_size: Voxel size for rendering
        """
        vis = o3d.visualization.Visualizer()
        vis.create_window(visible=False, width=1280, height=960)
        
        # Color clouds differently
        pred_pcd_copy = o3d.geometry.PointCloud(pred_pcd)
        gt_pcd_copy = o3d.geometry.PointCloud(gt_pcd)
        
        pred_pcd_copy.paint_uniform_color([0, 0, 1])  # Blue
        gt_pcd_copy.paint_uniform_color([1, 0, 0])     # Red
        
        vis.add_geometry(pred_pcd_copy)
        vis.add_geometry(gt_pcd_copy)
        
        # Adjust view
        vis.reset_view_point()
        vis.capture_screen_image(output_path)
        vis.destroy_window()
    
    @staticmethod
    def plot_metrics_comparison(metrics_list: List[dict], 
                               part_names: List[str],
                               output_path: str = None) -> None:
        """Plot comparison of metrics across multiple parts
        
        Args:
            metrics_list: List of metric dictionaries
            part_names: List of part names
            output_path: Optional path to save figure
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Point Cloud Reconstruction Metrics', fontsize=16)
        
        # Extract metrics
        chamfer_distances = [m.get('chamfer_distance', np.nan) for m in metrics_list]
        hausdorff_distances = [m.get('hausdorff_distance', np.nan) for m in metrics_list]
        completeness = [m.get('completeness_@0.1', np.nan) for m in metrics_list]
        accuracy = [m.get('accuracy_@0.1', np.nan) for m in metrics_list]
        
        # Plot 1: Chamfer Distance
        axes[0, 0].bar(range(len(part_names)), chamfer_distances)
        axes[0, 0].set_ylabel('Chamfer Distance (m)')
        axes[0, 0].set_title('Chamfer Distance')
        axes[0, 0].set_xticklabels(part_names, rotation=45, ha='right')
        
        # Plot 2: Hausdorff Distance
        axes[0, 1].bar(range(len(part_names)), hausdorff_distances)
        axes[0, 1].set_ylabel('Hausdorff Distance (m)')
        axes[0, 1].set_title('Hausdorff Distance')
        axes[0, 1].set_xticklabels(part_names, rotation=45, ha='right')
        
        # Plot 3: Completeness
        axes[1, 0].bar(range(len(part_names)), completeness)
        axes[1, 0].set_ylabel('Completeness (%)')
        axes[1, 0].set_ylim([0, 100])
        axes[1, 0].set_title('Completeness @ 0.1m')
        axes[1, 0].set_xticklabels(part_names, rotation=45, ha='right')
        
        # Plot 4: Accuracy
        axes[1, 1].bar(range(len(part_names)), accuracy)
        axes[1, 1].set_ylabel('Accuracy (%)')
        axes[1, 1].set_ylim([0, 100])
        axes[1, 1].set_title('Accuracy @ 0.1m')
        axes[1, 1].set_xticklabels(part_names, rotation=45, ha='right')
        
        plt.tight_layout()
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"Saved metrics plot to {output_path}")
        
        plt.show()
    
    @staticmethod
    def plot_distance_histogram(distances: np.ndarray, 
                               output_path: str = None,
                               threshold: float = 0.1) -> None:
        """Plot histogram of per-point distances
        
        Args:
            distances: Array of per-point distances
            output_path: Optional path to save figure
            threshold: Distance threshold for highlighting
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.hist(distances, bins=50, edgecolor='black', alpha=0.7)
        ax.axvline(threshold, color='r', linestyle='--', linewidth=2, 
                  label=f'Threshold ({threshold}m)')
        ax.set_xlabel('Distance (m)')
        ax.set_ylabel('Number of Points')
        ax.set_title('Distribution of Per-Point Distances to Ground Truth')
        ax.legend()
        ax.grid(alpha=0.3)
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"Saved distance histogram to {output_path}")
        
        plt.show()
    
    @staticmethod
    def visualize_keypoints_in_frame(frame: np.ndarray, 
                                    keypoints: np.ndarray,
                                    output_path: str = None,
                                    max_keypoints: int = 100) -> np.ndarray:
        """Visualize detected keypoints on a frame
        
        Args:
            frame: Input frame image
            keypoints: Array of keypoints (N x 4) with [x, y, size, angle]
            output_path: Optional path to save image
            max_keypoints: Maximum keypoints to draw
            
        Returns:
            Frame with drawn keypoints
        """
        frame_copy = frame.copy()
        
        for i, kp in enumerate(keypoints[:max_keypoints]):
            x, y, size, angle = kp
            x, y = int(x), int(y)
            size = int(size)
            
            # Draw circle at keypoint
            cv2.circle(frame_copy, (x, y), size, (0, 255, 0), 2)
            
            # Draw angle indicator
            end_x = int(x + size * np.cos(np.radians(angle)))
            end_y = int(y + size * np.sin(np.radians(angle)))
            cv2.line(frame_copy, (x, y), (end_x, end_y), (0, 255, 0), 2)
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(output_path, frame_copy)
            print(f"Saved keypoint visualization to {output_path}")
        
        return frame_copy
    
    @staticmethod
    def draw_keypoint_matches(frame1: np.ndarray, frame2: np.ndarray,
                             keypoints1: np.ndarray, keypoints2: np.ndarray,
                             matches: List, output_path: str = None,
                             max_matches: int = 50) -> np.ndarray:
        """Visualize matched keypoints between two frames
        
        Args:
            frame1: First frame
            frame2: Second frame
            keypoints1: Keypoints in frame 1 (N x 4)
            keypoints2: Keypoints in frame 2 (M x 4)
            matches: List of match objects from OpenCV
            output_path: Optional path to save image
            max_matches: Maximum matches to draw
            
        Returns:
            Combined frame showing matches
        """
        h1, w1 = frame1.shape[:2]
        h2, w2 = frame2.shape[:2]
        
        # Create combined image
        combined = np.zeros((max(h1, h2), w1 + w2, 3), dtype=np.uint8)
        combined[:h1, :w1] = frame1
        combined[:h2, w1:] = frame2
        
        # Draw matches
        for i, match in enumerate(matches[:max_matches]):
            x1, y1 = keypoints1[match.queryIdx][:2].astype(int)
            x2, y2 = keypoints2[match.trainIdx][:2].astype(int)
            
            # Draw circles
            cv2.circle(combined, (x1, y1), 5, (0, 255, 0), 2)
            cv2.circle(combined, (x2 + w1, y2), 5, (0, 255, 0), 2)
            
            # Draw line
            cv2.line(combined, (x1, y1), (x2 + w1, y2), (0, 255, 0), 1)
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(output_path, combined)
            print(f"Saved match visualization to {output_path}")
        
        return combined
