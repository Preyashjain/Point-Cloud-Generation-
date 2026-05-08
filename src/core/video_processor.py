"""Video processing module for frame extraction and feature detection"""
import cv2
import numpy as np
from typing import List, Tuple, Dict
from pathlib import Path
from tqdm import tqdm


class VideoProcessor:
    """Handles video frame extraction and preprocessing"""
    
    def __init__(self, sampling_rate: int = 1):
        """Initialize video processor
        
        Args:
            sampling_rate: Extract every nth frame (1 = all frames)
        """
        self.sampling_rate = sampling_rate
        self.sift = cv2.SIFT_create()
        
    def extract_frames(self, video_path: str, output_dir: str = None, 
                      max_frames: int = None) -> Tuple[List[np.ndarray], Dict]:
        """Extract frames from video
        
        Args:
            video_path: Path to video file
            output_dir: Optional directory to save extracted frames
            max_frames: Maximum number of frames to extract
            
        Returns:
            Tuple of (list of frames, metadata)
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        frames = []
        frame_indices = []
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Create output directory if needed
        output_path = None
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        
        frame_idx = 0
        with tqdm(total=frame_count, desc="Extracting frames") as pbar:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_idx % self.sampling_rate == 0:
                    frames.append(frame)
                    frame_indices.append(frame_idx)
                    
                    # Save frame if output dir specified
                    if output_path:
                        cv2.imwrite(
                            str(output_path / f"frame_{len(frames):06d}.jpg"),
                            frame
                        )
                    
                    if max_frames and len(frames) >= max_frames:
                        break
                
                frame_idx += 1
                pbar.update(1)
        
        cap.release()
        
        metadata = {
            'total_frames_in_video': frame_count,
            'extracted_frames': len(frames),
            'sampling_rate': self.sampling_rate,
            'frame_indices': frame_indices,
            'fps': fps,
            'width': width,
            'height': height
        }
        
        return frames, metadata
    
    def detect_keypoints(self, frames: List[np.ndarray]) -> List[Dict]:
        """Detect SIFT keypoints in frames
        
        Args:
            frames: List of frame images
            
        Returns:
            List of dicts with keypoints and descriptors for each frame
        """
        keypoint_data = []
        
        for i, frame in enumerate(tqdm(frames, desc="Detecting keypoints")):
            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            kp, des = self.sift.detectAndCompute(gray, None)
            
            # Convert keypoints to array format
            kp_array = np.array([[k.pt[0], k.pt[1], k.size, k.angle] for k in kp])
            
            keypoint_data.append({
                'frame_idx': i,
                'keypoints': kp_array,
                'descriptors': des,
                'opencv_kp': kp  # Keep original for visualization
            })
        
        return keypoint_data
    
    def match_features(self, keypoint_data: List[Dict], ratio_test: float = 0.7) -> List[Tuple]:
        """Match features between consecutive frames
        
        Args:
            keypoint_data: List of keypoint data from detect_keypoints
            ratio_test: Lowe's ratio test threshold
            
        Returns:
            List of matches between consecutive frames
        """
        matcher = cv2.BFMatcher()
        matches_list = []
        
        for i in range(len(keypoint_data) - 1):
            des1 = keypoint_data[i]['descriptors']
            des2 = keypoint_data[i + 1]['descriptors']
            
            if des1 is None or des2 is None:
                matches_list.append([])
                continue
            
            matches = matcher.knnMatch(des1, des2, k=2)
            
            # Apply Lowe's ratio test
            good_matches = []
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < ratio_test * n.distance:
                        good_matches.append(m)
            
            matches_list.append(good_matches)
        
        return matches_list
    
    def estimate_camera_intrinsics(self, frame_width: int, frame_height: int) -> np.ndarray:
        """Estimate camera intrinsic matrix (simple approach)
        
        Args:
            frame_width: Frame width in pixels
            frame_height: Frame height in pixels
            
        Returns:
            3x3 camera intrinsic matrix K
        """
        # Assume 50mm equivalent focal length on APS-C sensor
        # Typical sensor width: 35.9mm, diagonal: ~43mm
        focal_length = max(frame_width, frame_height)  # Approximation
        
        K = np.array([
            [focal_length, 0, frame_width / 2],
            [0, focal_length, frame_height / 2],
            [0, 0, 1]
        ])
        
        return K
    
    @staticmethod
    def undistort_frames(frames: List[np.ndarray], K: np.ndarray, 
                        distortion_coeffs: np.ndarray = None) -> List[np.ndarray]:
        """Undistort frames using camera intrinsics
        
        Args:
            frames: List of frames
            K: Camera intrinsic matrix
            distortion_coeffs: Distortion coefficients [k1, k2, p1, p2, k3]
            
        Returns:
            List of undistorted frames
        """
        if distortion_coeffs is None:
            distortion_coeffs = np.zeros(5)
        
        undistorted = []
        for frame in tqdm(frames, desc="Undistorting frames"):
            undist_frame = cv2.undistort(frame, K, distortion_coeffs)
            undistorted.append(undist_frame)
        
        return undistorted
