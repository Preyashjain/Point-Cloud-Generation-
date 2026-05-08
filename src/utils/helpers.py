"""Helper utility functions"""
import os
import json
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import open3d as o3d


def create_output_dirs(base_dir: str) -> Dict[str, Path]:
    """Create output directory structure
    
    Args:
        base_dir: Base output directory
        
    Returns:
        Dictionary with paths to various output directories
    """
    base = Path(base_dir)
    
    dirs = {
        'point_clouds': base / 'point_clouds',
        'evaluations': base / 'evaluations',
        'visualizations': base / 'visualizations',
        'logs': base / 'logs'
    }
    
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    
    return dirs


def save_metrics_json(metrics: Dict, output_path: str) -> None:
    """Save metrics to JSON file
    
    Args:
        metrics: Dictionary of metrics
        output_path: Path to save JSON file
    """
    # Convert numpy types to standard Python types for JSON serialization
    metrics_clean = {}
    for k, v in metrics.items():
        if isinstance(v, np.ndarray):
            metrics_clean[k] = v.tolist()
        elif isinstance(v, (np.floating, float)):
            metrics_clean[k] = float(v)
        elif isinstance(v, (np.integer, int)):
            metrics_clean[k] = int(v)
        else:
            metrics_clean[k] = v
    
    with open(output_path, 'w') as f:
        json.dump(metrics_clean, f, indent=2)


def load_metrics_json(input_path: str) -> Dict:
    """Load metrics from JSON file
    
    Args:
        input_path: Path to JSON file
        
    Returns:
        Dictionary of metrics
    """
    with open(input_path, 'r') as f:
        return json.load(f)


def combine_metrics_report(metrics_list: List[Dict], output_path: str) -> Dict:
    """Combine multiple metric dictionaries into a summary report
    
    Args:
        metrics_list: List of metric dictionaries
        output_path: Path to save report
        
    Returns:
        Summary statistics
    """
    summary = {}
    
    if not metrics_list:
        return summary
    
    # Get all keys from first metrics dict
    keys = set(metrics_list[0].keys())
    
    # For numeric values, compute statistics
    for key in keys:
        values = []
        for m in metrics_list:
            if key in m and isinstance(m[key], (int, float)):
                values.append(m[key])
        
        if values:
            summary[key] = {
                'mean': np.mean(values),
                'median': np.median(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'count': len(values)
            }
    
    # Save summary
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    return summary


def align_point_clouds(source: o3d.geometry.PointCloud, 
                       target: o3d.geometry.PointCloud,
                       method: str = 'icp') -> Tuple:
    """Align source point cloud to target
    
    Args:
        source: Source point cloud
        target: Target point cloud
        method: 'icp' or 'ransac'
        
    Returns:
        Aligned point cloud and transformation matrix
    """
    if method == 'icp':
        reg = o3d.pipelines.registration.registration_icp(
            source, target, 0.1, np.eye(4),
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50)
        )
    else:
        raise ValueError(f"Unknown alignment method: {method}")
    
    aligned = source.transform(reg.transformation)
    return aligned, reg.transformation


def normalize_point_cloud(pcd: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """Normalize point cloud to unit cube centered at origin
    
    Args:
        pcd: Input point cloud
        
    Returns:
        Normalized point cloud
    """
    pcd_copy = o3d.geometry.PointCloud(pcd)
    
    # Center at origin
    pcd_copy.translate(-pcd_copy.get_center())
    
    # Scale to fit in unit cube
    max_dist = np.max(np.linalg.norm(np.asarray(pcd_copy.points), axis=1))
    if max_dist > 0:
        pcd_copy.scale(1.0 / max_dist, center=np.array([0, 0, 0]))
    
    return pcd_copy


def get_point_cloud_bounds(points: np.ndarray) -> tuple:
    """Get bounding box of point cloud
    
    Args:
        points: Array of 3D points (N x 3)
        
    Returns:
        Tuple of (min_bounds, max_bounds)
    """
    min_bounds = np.min(points, axis=0)
    max_bounds = np.max(points, axis=0)
    return min_bounds, max_bounds


def filter_by_bounds(points: np.ndarray, min_bound: np.ndarray, 
                    max_bound: np.ndarray) -> np.ndarray:
    """Filter points by bounding box
    
    Args:
        points: Array of 3D points (N x 3)
        min_bound: Minimum coordinates
        max_bound: Maximum coordinates
        
    Returns:
        Filtered points
    """
    mask = np.all((points >= min_bound) & (points <= max_bound), axis=1)
    return points[mask]
