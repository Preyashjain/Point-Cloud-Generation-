"""Point cloud evaluation and comparison module"""
import numpy as np
import open3d as o3d
from typing import Dict, Tuple
from scipy.spatial.distance import cdist
from sklearn.neighbors import NearestNeighbors


class PointCloudEvaluator:
    """Evaluates point cloud reconstruction quality"""
    
    @staticmethod
    def chamfer_distance(pred_points: np.ndarray, gt_points: np.ndarray) -> Tuple[float, float, float]:
        """Compute Chamfer distance between two point clouds
        
        Args:
            pred_points: Predicted points (N x 3)
            gt_points: Ground truth points (M x 3)
            
        Returns:
            Tuple of (chamfer_distance, pred_to_gt, gt_to_pred)
        """
        # Distance from predicted to ground truth
        distances_pred_to_gt = cdist(pred_points, gt_points).min(axis=1)
        pred_to_gt = distances_pred_to_gt.mean()
        
        # Distance from ground truth to predicted
        distances_gt_to_pred = cdist(gt_points, pred_points).min(axis=1)
        gt_to_pred = distances_gt_to_pred.mean()
        
        # Chamfer distance (symmetric)
        chamfer = (pred_to_gt + gt_to_pred) / 2
        
        return chamfer, pred_to_gt, gt_to_pred
    
    @staticmethod
    def hausdorff_distance(pred_points: np.ndarray, gt_points: np.ndarray) -> float:
        """Compute Hausdorff distance between two point clouds
        
        Args:
            pred_points: Predicted points (N x 3)
            gt_points: Ground truth points (M x 3)
            
        Returns:
            Hausdorff distance
        """
        distances_pred_to_gt = cdist(pred_points, gt_points).min(axis=1)
        distances_gt_to_pred = cdist(gt_points, pred_points).min(axis=1)
        
        return max(distances_pred_to_gt.max(), distances_gt_to_pred.max())
    
    @staticmethod
    def completeness_accuracy(pred_points: np.ndarray, gt_points: np.ndarray, 
                             threshold: float = 0.1) -> Tuple[float, float]:
        """Compute completeness and accuracy metrics
        
        Args:
            pred_points: Predicted points (N x 3)
            gt_points: Ground truth points (M x 3)
            threshold: Distance threshold for considering a point as correct
            
        Returns:
            Tuple of (completeness, accuracy)
        """
        # Accuracy: percentage of predicted points within threshold of any GT point
        distances_pred_to_gt = cdist(pred_points, gt_points).min(axis=1)
        accuracy = (distances_pred_to_gt < threshold).sum() / len(pred_points) * 100
        
        # Completeness: percentage of GT points within threshold of any predicted point
        distances_gt_to_pred = cdist(gt_points, pred_points).min(axis=1)
        completeness = (distances_gt_to_pred < threshold).sum() / len(gt_points) * 100
        
        return completeness, accuracy
    
    @staticmethod
    def f_score(pred_points: np.ndarray, gt_points: np.ndarray, 
                threshold: float = 0.1) -> float:
        """Compute F-score (harmonic mean of precision and recall)
        
        Args:
            pred_points: Predicted points (N x 3)
            gt_points: Ground truth points (M x 3)
            threshold: Distance threshold
            
        Returns:
            F-score (0-100)
        """
        completeness, accuracy = PointCloudEvaluator.completeness_accuracy(
            pred_points, gt_points, threshold
        )
        
        if completeness + accuracy == 0:
            return 0.0
        
        f_score = 2 * (completeness * accuracy) / (completeness + accuracy)
        return f_score
    
    @staticmethod
    def point_cloud_metrics(pred_pcd: o3d.geometry.PointCloud, 
                           gt_pcd: o3d.geometry.PointCloud) -> Dict:
        """Compute comprehensive evaluation metrics
        
        Args:
            pred_pcd: Predicted point cloud
            gt_pcd: Ground truth point cloud
            
        Returns:
            Dictionary with evaluation metrics
        """
        pred_points = np.asarray(pred_pcd.points)
        gt_points = np.asarray(gt_pcd.points)
        
        # Basic statistics
        metrics = {
            'pred_point_count': len(pred_points),
            'gt_point_count': len(gt_points),
            'point_count_ratio': len(pred_points) / len(gt_points) if len(gt_points) > 0 else 0
        }
        
        if len(pred_points) == 0:
            print("Warning: Predicted point cloud is empty!")
            return metrics
        
        # Chamfer distance
        chamfer, pred_to_gt, gt_to_pred = PointCloudEvaluator.chamfer_distance(
            pred_points, gt_points
        )
        metrics['chamfer_distance'] = chamfer
        metrics['pred_to_gt_distance'] = pred_to_gt
        metrics['gt_to_pred_distance'] = gt_to_pred
        
        # Hausdorff distance
        metrics['hausdorff_distance'] = PointCloudEvaluator.hausdorff_distance(
            pred_points, gt_points
        )
        
        # Completeness and accuracy at different thresholds
        for threshold in [0.05, 0.1, 0.2]:
            completeness, accuracy = PointCloudEvaluator.completeness_accuracy(
                pred_points, gt_points, threshold
            )
            f_score = PointCloudEvaluator.f_score(pred_points, gt_points, threshold)
            
            metrics[f'completeness_@{threshold}'] = completeness
            metrics[f'accuracy_@{threshold}'] = accuracy
            metrics[f'f_score_@{threshold}'] = f_score
        
        return metrics
    
    @staticmethod
    def print_metrics(metrics: Dict) -> None:
        """Print evaluation metrics in readable format
        
        Args:
            metrics: Dictionary of metrics from point_cloud_metrics()
        """
        print("\n" + "="*50)
        print("Point Cloud Evaluation Metrics")
        print("="*50)
        
        print(f"\nPoint Counts:")
        print(f"  Predicted: {metrics.get('pred_point_count', 'N/A'):,}")
        print(f"  Ground Truth: {metrics.get('gt_point_count', 'N/A'):,}")
        print(f"  Ratio (Pred/GT): {metrics.get('point_count_ratio', 'N/A'):.3f}")
        
        if 'chamfer_distance' in metrics:
            print(f"\nDistances:")
            print(f"  Chamfer Distance: {metrics['chamfer_distance']:.6f}")
            print(f"  Pred -> GT: {metrics['pred_to_gt_distance']:.6f}")
            print(f"  GT -> Pred: {metrics['gt_to_pred_distance']:.6f}")
            print(f"  Hausdorff Distance: {metrics['hausdorff_distance']:.6f}")
        
        print(f"\nAccuracy & Completeness:")
        for threshold in [0.05, 0.1, 0.2]:
            if f'completeness_@{threshold}' in metrics:
                print(f"\n  @ {threshold}m threshold:")
                print(f"    Completeness: {metrics[f'completeness_@{threshold}']:.2f}%")
                print(f"    Accuracy: {metrics[f'accuracy_@{threshold}']:.2f}%")
                print(f"    F-score: {metrics[f'f_score_@{threshold}']:.2f}%")
        
        print("\n" + "="*50 + "\n")
    
    @staticmethod
    def per_point_distance(pred_points: np.ndarray, gt_points: np.ndarray) -> np.ndarray:
        """Compute per-point distance from predictions to nearest GT point
        
        Args:
            pred_points: Predicted points (N x 3)
            gt_points: Ground truth points (M x 3)
            
        Returns:
            Array of distances for each predicted point
        """
        distances = cdist(pred_points, gt_points).min(axis=1)
        return distances
    
    @staticmethod
    def get_dense_reconstruction_metrics(pred_pcd: o3d.geometry.PointCloud,
                                        gt_pcd: o3d.geometry.PointCloud,
                                        voxel_size: float = 0.01) -> Dict:
        """Compute metrics on voxelized (denser) reconstruction
        
        Args:
            pred_pcd: Predicted point cloud
            gt_pcd: Ground truth point cloud
            voxel_size: Voxel size for downsampling
            
        Returns:
            Dictionary with voxel-based metrics
        """
        # Downsample both point clouds to the same voxel grid
        pred_down = pred_pcd.voxel_down_sample(voxel_size=voxel_size)
        gt_down = gt_pcd.voxel_down_sample(voxel_size=voxel_size)
        
        return PointCloudEvaluator.point_cloud_metrics(pred_down, gt_down)
