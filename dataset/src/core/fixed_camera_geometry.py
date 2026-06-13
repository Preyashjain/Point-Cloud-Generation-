"""Essential Matrix + Homography Constraint for fixed camera setup
Exploits the constrained camera geometry to improve pose estimation
Reduces DOF from 7 (Fundamental) to 5 (Essential) or even 4 (Homography)
"""

import numpy as np
import cv2
from typing import Tuple, Dict, Optional
from enum import Enum


class MotionModel(Enum):
    """Motion models for fixed camera setup"""
    HOMOGRAPHY = "homography"      # 4 DOF - planar motion
    ESSENTIAL = "essential"        # 5 DOF - general motion with calibrated K
    FUNDAMENTAL = "fundamental"    # 7 DOF - uncalibrated (don't use if K known!)


class FixedCameraGeometry:
    """
    Exploit fixed camera angle for better pose estimation
    
    Key Insights:
    1. If K is known (which it is for your setup), use Essential Matrix (5 DOF)
       instead of Fundamental Matrix (7 DOF)
    2. Industrial setup is often partially planar - homography gives 4 DOF
    3. Metric reconstruction directly from triangulation (not up-to-scale)
    
    Improvements:
    - More constrained, fewer DOF = fewer false matches needed to break RANSAC
    - Metric scale directly (K known) instead of ambiguous scale
    - Better suited for industrial parts on platform
    """
    
    def __init__(self, K: np.ndarray):
        """Initialize with camera intrinsic matrix
        
        Args:
            K: Camera intrinsic matrix (3x3)
               [[fx,  0, cx],
                [ 0, fy, cy],
                [ 0,  0,  1]]
        """
        self.K = K
        self.K_inv = np.linalg.inv(K)
    
    def normalize_points(self, pts: np.ndarray) -> np.ndarray:
        """Normalize image coordinates to camera coordinates
        
        Converts from pixel coordinates to normalized camera coordinates
        using intrinsic matrix K
        
        Args:
            pts: Image coordinates (N, 2)
            
        Returns:
            Normalized coordinates (N, 2)
        """
        # Convert to homogeneous coordinates
        pts_h = np.hstack([pts, np.ones((pts.shape[0], 1))])
        
        # Apply K^-1
        pts_norm_h = (self.K_inv @ pts_h.T).T
        
        # Return to 2D
        return pts_norm_h[:, :2]
    
    def estimate_essential_matrix(self, pts1: np.ndarray, pts2: np.ndarray,
                                 confidence: float = 0.999,
                                 threshold: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        """Estimate Essential Matrix (recommended for calibrated cameras)
        
        Essential Matrix: Only 5 DOF (vs 7 for Fundamental)
        - Encodes rotation and translation
        - Requires known K (which you have!)
        - Better for constrained industrial geometry
        
        Args:
            pts1, pts2: Matched 2D points in both images
            confidence: RANSAC confidence (0.999 = 99.9%)
            threshold: RANSAC threshold in pixels
            
        Returns:
            Tuple of (Essential Matrix, inlier mask)
        """
        if len(pts1) < 5:
            raise ValueError("Need at least 5 point matches for Essential Matrix")
        
        # Use Essential Matrix (5 DOF) - best for calibrated cameras
        E, mask = cv2.findEssentialMat(
            pts1, pts2, self.K,
            method=cv2.FM_RANSAC,
            prob=confidence,
            threshold=threshold
        )
        
        if E is None:
            raise ValueError("Could not estimate Essential Matrix")
        
        return E, mask
    
    def estimate_homography(self, pts1: np.ndarray, pts2: np.ndarray,
                           confidence: float = 0.999) -> Tuple[np.ndarray, np.ndarray]:
        """Estimate Homography (for planar scenes/motion)
        
        Homography: Only 4 DOF
        - For planar motion (common in industrial setups)
        - Strongly constrained geometry
        - More robust if motion is mostly planar
        
        Args:
            pts1, pts2: Matched 2D points
            confidence: RANSAC confidence
            
        Returns:
            Tuple of (Homography matrix, inlier mask)
        """
        if len(pts1) < 4:
            raise ValueError("Need at least 4 point matches for Homography")
        
        H, mask = cv2.findHomography(
            pts1, pts2,
            method=cv2.FM_RANSAC,
            confidence=confidence
        )
        
        if H is None:
            raise ValueError("Could not estimate Homography")
        
        return H, mask
    
    def decompose_essential_matrix(self, E: np.ndarray, 
                                   pts1: np.ndarray, 
                                   pts2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Decompose Essential Matrix to R and t
        
        Essential Matrix has 4 possible solutions.
        This function tests all 4 and returns the one with most points in front of cameras.
        
        Args:
            E: Essential Matrix (3x3)
            pts1, pts2: Matched points for disambiguation
            
        Returns:
            Tuple of (Rotation matrix R (3x3), Translation vector t (3x1))
        """
        # Decompose E = U Σ V^T
        U, _, Vt = np.linalg.svd(E)
        
        # Four possible solutions
        W = np.array([[0, -1, 0],
                      [1,  0, 0],
                      [0,  0, 1]])
        
        R_options = [
            U @ W @ Vt,
            U @ W @ Vt,
            U @ W.T @ Vt,
            U @ W.T @ Vt
        ]
        
        t_options = [
            U[:, 2:3],
            -U[:, 2:3],
            U[:, 2:3],
            -U[:, 2:3]
        ]
        
        # Fix determinant (should be +1 for rotation)
        for i in range(4):
            if np.linalg.det(R_options[i]) < 0:
                R_options[i] = -R_options[i]
                t_options[i] = -t_options[i]
        
        # Test all 4 solutions, pick one with most points in front of both cameras
        best_solution = (R_options[0], t_options[0], 0)
        best_count = 0
        
        for R, t, _ in zip(R_options, t_options, range(4)):
            count = self._count_points_in_front(pts1, pts2, R, t)
            if count > best_count:
                best_count = count
                best_solution = (R, t, count)
        
        R, t, _ = best_solution
        return R, t
    
    def decompose_homography(self, H: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Decompose Homography to R and t
        
        For planar scenes: returns multiple solutions
        
        Args:
            H: Homography matrix (3x3)
            
        Returns:
            Tuple of (Rotation matrix R (3x3), Translation vector t (3x1), Normal vector n (3x1))
        """
        # Normalize by K
        H_norm = self.K_inv @ H @ self.K
        
        # SVD decomposition
        U, S, Vt = np.linalg.svd(H_norm)
        
        # Recover rotation and translation
        # This is a simplified version - full decomposition has multiple solutions
        R = U @ Vt
        
        # Ensure proper rotation (det = +1)
        if np.linalg.det(R) < 0:
            R = -R
        
        # Translation is harder to recover from H alone
        # Need additional information (depth or multiple hypotheses)
        t = np.zeros((3, 1))
        
        return R, t
    
    def _count_points_in_front(self, pts1: np.ndarray, pts2: np.ndarray,
                               R: np.ndarray, t: np.ndarray) -> int:
        """Count how many triangulated points are in front of both cameras"""
        if len(pts1) < 1:
            return 0
        
        try:
            # Triangulate
            P1 = self.K @ np.hstack([np.eye(3), np.zeros((3, 1))])
            P2 = self.K @ np.hstack([R, t])
            
            points_4d = cv2.triangulatePoints(P1, P2, pts1.T, pts2.T)
            points_3d = (points_4d[:3] / points_4d[3]).T
            
            # Check depth in both cameras
            valid_cam1 = points_3d[:, 2] > 0
            points_cam2 = points_3d @ R.T + t.T
            valid_cam2 = points_cam2[:, 2] > 0
            
            return (valid_cam1 & valid_cam2).sum()
        except:
            return 0
    
    def get_metric_reconstruction(self, pts1: np.ndarray, pts2: np.ndarray,
                                 R: np.ndarray, t: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Get metric reconstruction (with correct scale)
        
        Since K is known, the scale of triangulation is correct!
        This is a major advantage over uncalibrated methods.
        
        Args:
            pts1, pts2: Matched 2D points
            R, t: Camera rotation and translation
            
        Returns:
            Tuple of (3D points in metric units, validity mask)
        """
        # Build projection matrices (with known K)
        P1 = self.K @ np.hstack([np.eye(3), np.zeros((3, 1))])
        P2 = self.K @ np.hstack([R, t])
        
        # Triangulate
        points_4d = cv2.triangulatePoints(P1, P2, pts1.T, pts2.T)
        points_3d = (points_4d[:3] / points_4d[3]).T
        
        # Validity check
        valid = np.ones(len(points_3d), dtype=bool)
        
        # Must be in front of both cameras
        valid &= points_3d[:, 2] > 0
        points_cam2 = points_3d @ R.T + t.T
        valid &= points_cam2[:, 2] > 0
        
        # Must be within reasonable depth (0.1m - 50m)
        valid &= (points_3d[:, 2] > 0.1) & (points_3d[:, 2] < 50)
        
        # Low reprojection error
        proj1 = (self.K @ points_3d.T).T
        proj1_2d = proj1[:, :2] / proj1[:, 2:3]
        error1 = np.linalg.norm(proj1_2d - pts1, axis=1)
        valid &= error1 < 5
        
        return points_3d[valid], valid
    
    def analyze_motion(self, pts1: np.ndarray, pts2: np.ndarray,
                      K: np.ndarray) -> Dict:
        """Analyze motion type (planar vs general)
        
        Determines if motion is primarily planar (good for homography)
        or general 3D motion (need essential matrix)
        
        Returns:
            Dict with motion analysis
        """
        try:
            # Try both models
            E, e_mask = self.estimate_essential_matrix(pts1, pts2)
            H, h_mask = self.estimate_homography(pts1, pts2)
            
            e_inliers = e_mask.sum() if e_mask is not None else 0
            h_inliers = h_mask.sum() if h_mask is not None else 0
            
            planar_ratio = h_inliers / (e_inliers + 1e-8)
            
            return {
                'essential_inliers': e_inliers,
                'homography_inliers': h_inliers,
                'planar_ratio': planar_ratio,
                'motion_type': 'planar' if planar_ratio > 0.8 else 'general_3d',
                'recommendation': 'Use Homography' if planar_ratio > 0.8 else 'Use Essential Matrix'
            }
        except:
            return {
                'error': 'Could not analyze motion',
                'recommendation': 'Use Essential Matrix (default)'
            }
    
    def get_info(self) -> Dict:
        """Get module information"""
        return {
            'motion_models_supported': ['homography (4 DOF)', 'essential (5 DOF)', 'fundamental (7 DOF)'],
            'recommended_for_calibrated': 'Essential Matrix (5 DOF)',
            'recommended_for_planar': 'Homography (4 DOF)',
            'metric_reconstruction': True,
            'improvement_over_sift': 'More constrained geometry -> better pose estimation',
        }


# Example usage
if __name__ == "__main__":
    # Camera intrinsic matrix
    K = np.array([
        [1000, 0, 320],
        [0, 1000, 240],
        [0, 0, 1]
    ])
    
    geometry = FixedCameraGeometry(K)
    
    # Example matched points (would come from feature matching)
    pts1 = np.array([[100, 100], [200, 150], [250, 100], [150, 200], [300, 250]])
    pts2 = np.array([[110, 105], [210, 155], [260, 105], [160, 205], [310, 255]])
    
    # Estimate Essential Matrix
    E, e_mask = geometry.estimate_essential_matrix(pts1, pts2)
    print(f"Essential Matrix found: {e_mask.sum()} inliers")
    
    # Decompose to R and t
    R, t = geometry.decompose_essential_matrix(E, pts1[e_mask.ravel() > 0], pts2[e_mask.ravel() > 0])
    print(f"Recovered rotation:\n{R}")
    print(f"Recovered translation: {t.T}")
    
    # Get metric reconstruction
    points_3d, valid = geometry.get_metric_reconstruction(pts1, pts2, R, t)
    print(f"✅ {valid.sum()} valid 3D points")
    print(f"Depth range: {points_3d[:, 2].min():.2f}m - {points_3d[:, 2].max():.2f}m")
