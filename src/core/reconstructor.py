"""Point cloud reconstruction module"""
import numpy as np
import cv2
import open3d as o3d
from typing import List, Tuple, Dict, Optional
from tqdm import tqdm


class PointCloudReconstructor:
    """Reconstructs 3D point clouds from video frames"""
    
    def __init__(self, K: np.ndarray = None):
        """Initialize reconstructor
        
        Args:
            K: Camera intrinsic matrix (3x3)
        """
        self.K = K
        self.points_3d = []
        self.colors = []
        self.camera_poses = []
        
    def triangulate_points(self, keypoint_data: List[Dict], matches_list: List, 
                          frames: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
        """Triangulate 3D points from matched keypoints using simplified approach
        
        Args:
            keypoint_data: Keypoint detection results
            matches_list: Feature matches between frames
            frames: Original frames for color information
            
        Returns:
            Tuple of (3D points array, colors array)
        """
        all_points_3d = []
        all_colors = []
        
        if self.K is None:
            raise ValueError("Camera intrinsic matrix K not set")
        
        # Simple triangulation: use pairs of frames
        for i in range(min(len(matches_list), 5)):  # Use first few frame pairs
            if len(matches_list[i]) < 8:
                continue
            
            # Get matched keypoints
            kp1 = keypoint_data[i]['keypoints']
            kp2 = keypoint_data[i + 1]['keypoints']
            matches = matches_list[i]
            
            if len(matches) < 8:
                continue
            
            # Extract matching point pairs
            pts1 = np.array([kp1[m.queryIdx][:2] for m in matches], dtype=np.float32)
            pts2 = np.array([kp2[m.trainIdx][:2] for m in matches], dtype=np.float32)
            
            # Estimate fundamental matrix
            try:
                F, mask = cv2.findFundamentalMat(pts1, pts2, cv2.FM_RANSAC, 1.0, 0.99)
                if F is None or mask is None:
                    continue
                
                # Filter points by RANSAC mask
                mask = mask.ravel() == 1
                if mask.sum() < 8:
                    continue
                    
                pts1_inliers = pts1[mask]
                pts2_inliers = pts2[mask]
                
                # Compute essential matrix from filtered points
                E, _ = cv2.findEssentialMat(pts1_inliers, pts2_inliers, self.K, cv2.FM_RANSAC, 0.999, 1.0)
                if E is None:
                    continue
                
                # Recover pose from essential matrix
                _, R, t, mask_pose = cv2.recoverPose(E, pts1_inliers, pts2_inliers, self.K)
                
                # Triangulate points
                P1 = self.K @ np.hstack([np.eye(3), np.zeros((3, 1))])
                P2 = self.K @ np.hstack([R, t.reshape(3, 1)])
                
                # Normalize coordinates for triangulation
                pts1_norm = cv2.undistortPoints(pts1_inliers.reshape(-1, 1, 2), self.K, None)[:, 0, :]
                pts2_norm = cv2.undistortPoints(pts2_inliers.reshape(-1, 1, 2), self.K, None)[:, 0, :]
                
                points_4d = cv2.triangulatePoints(P1, P2, pts1_norm.T, pts2_norm.T)
                points_3d = (points_4d[:3] / points_4d[3]).T
                
                # Filter points - VERY LENIENT to collect anything reasonable
                valid_points = []
                valid_colors = []
                
                for j, pt_3d in enumerate(points_3d):
                    # Accept any point with positive depth (z > 0) and reasonable bounds
                    if pt_3d[2] > 0.001:  # Must be in front of camera
                        # Clamp outliers but don't reject them
                        if pt_3d[2] > 500:  # Far points
                            continue
                        
                        valid_points.append(pt_3d)
                        
                        # Get color from frame
                        x, y = int(pts1_inliers[j][0]), int(pts1_inliers[j][1])
                        if 0 <= y < frames[i].shape[0] and 0 <= x < frames[i].shape[1]:
                            color = frames[i][y, x]
                            valid_colors.append(color)
                        else:
                            valid_colors.append([128, 128, 128])
                
                if valid_points:
                    all_points_3d.extend(valid_points)
                    all_colors.extend(valid_colors)
            
            except Exception as e:
                # Silent failure - just skip this frame pair
                continue
        
        if not all_points_3d:
            return np.array([]), np.array([])
            
        return np.array(all_points_3d), np.array(all_colors)
    
    def sift_based_reconstruction(self, frames: List[np.ndarray], 
                                  keypoint_data: List[Dict],
                                  matches_list: List) -> Tuple[np.ndarray, np.ndarray]:
        """Simple SIFT-based reconstruction using multiple frame pairs
        
        Args:
            frames: List of frames
            keypoint_data: Keypoint detections
            matches_list: Matched features
            
        Returns:
            Tuple of (points, colors)
        """
        all_points = []
        all_colors = []
        
        n_pairs = min(len(matches_list), 10)  # Use multiple frame pairs
        
        for i in tqdm(range(n_pairs), desc="Triangulating frames"):
            try:
                points, colors = self.triangulate_points(
                    keypoint_data, matches_list[:i+2], frames[:i+2]
                )
                if len(points) > 0:
                    all_points.extend(points)
                    all_colors.extend(colors)
            except Exception as e:
                print(f"Triangulation failed for frame {i}: {e}")
                continue
        
        return np.array(all_points), np.array(all_colors)
    
    def create_point_cloud(self, points: np.ndarray, colors: np.ndarray = None) -> o3d.geometry.PointCloud:
        """Create Open3D point cloud object
        
        Args:
            points: Array of 3D points (N x 3)
            colors: Optional array of RGB colors (N x 3), values 0-255
            
        Returns:
            Open3D point cloud
        """
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        
        if colors is not None:
            # Normalize colors to 0-1 range
            if colors.max() > 1:
                colors = colors.astype(float) / 255.0
            pcd.colors = o3d.utility.Vector3dVector(colors)
        
        return pcd
    
    def filter_outliers(self, pcd: o3d.geometry.PointCloud, 
                       nb_neighbors: int = 10, std_ratio: float = 10.0) -> o3d.geometry.PointCloud:
        """Remove outliers from point cloud using statistical filtering
        
        Args:
            pcd: Input point cloud
            nb_neighbors: Number of neighbors for statistical filter
            std_ratio: Standard deviation ratio threshold
            
        Returns:
            Filtered point cloud
        """
        if len(pcd.points) < nb_neighbors:
            return pcd  # Not enough points to filter
            
        try:
            cl, ind = pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors, std_ratio=std_ratio)
            if len(ind) > 0:
                return pcd.select_by_index(ind)
        except:
            pass
            
        return pcd  # Return unfiltered if filtering fails
    
    def downsample(self, pcd: o3d.geometry.PointCloud, 
                   voxel_size: float = 0.005) -> o3d.geometry.PointCloud:
        """Downsample point cloud using voxel grid
        
        Args:
            pcd: Input point cloud
            voxel_size: Size of voxel for downsampling
            
        Returns:
            Downsampled point cloud
        """
        return pcd.voxel_down_sample(voxel_size=voxel_size)
    
    def estimate_normals(self, pcd: o3d.geometry.PointCloud, 
                        search_param=None) -> None:
        """Estimate surface normals
        
        Args:
            pcd: Point cloud
            search_param: Search parameters (default: KNN with 20 neighbors)
        """
        if search_param is None:
            search_param = o3d.geometry.KDTreeSearchParamKNN(knn=20)
        
        pcd.estimate_normals(search_param=search_param)
    
    def crop_by_bounds(self, pcd: o3d.geometry.PointCloud, 
                      min_bound: np.ndarray, max_bound: np.ndarray) -> o3d.geometry.PointCloud:
        """Crop point cloud to specified bounds
        
        Args:
            pcd: Input point cloud
            min_bound: Minimum coordinates [x, y, z]
            max_bound: Maximum coordinates [x, y, z]
            
        Returns:
            Cropped point cloud
        """
        bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound, max_bound)
        return pcd.crop(bbox)
    
    def register_to_ground_truth(self, source_pcd: o3d.geometry.PointCloud,
                                target_pcd: o3d.geometry.PointCloud,
                                max_correspondence_distance: float = 0.1) -> Tuple:
        """Register reconstructed point cloud to ground truth
        
        Args:
            source_pcd: Reconstructed point cloud
            target_pcd: Ground truth point cloud
            max_correspondence_distance: Max distance for correspondence
            
        Returns:
            Registration result (transformation, rmse, iterations)
        """
        # Use ICP for registration
        reg_p2p = o3d.pipelines.registration.registration_icp(
            source_pcd, target_pcd,
            max_correspondence_distance,
            np.eye(4),
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50)
        )
        
        return reg_p2p
    
    def save_point_cloud(self, pcd: o3d.geometry.PointCloud, output_path: str) -> None:
        """Save point cloud to file
        
        Args:
            pcd: Point cloud to save
            output_path: Output file path (PLY format recommended)
        """
        o3d.io.write_point_cloud(output_path, pcd)
