"""Data loading and dataset management module"""
import os
from pathlib import Path
from typing import Dict, List, Tuple
import json
import cv2
import open3d as o3d
import numpy as np
from dataclasses import dataclass


@dataclass
class PartMetadata:
    """Metadata for a single industrial part"""
    code: str
    surface_type: str  # R, G, M, T
    size_type: str    # TS, MS, LS
    shape_type: str   # O, I, P
    complexity: str   # HI, LO
    part_number: int
    
    def __str__(self):
        return f"{self.code} ({self.surface_type}-{self.size_type}-{self.shape_type}-{self.complexity})"


class DataLoader:
    """Loads and manages the INNO-GRIP dataset"""
    
    def __init__(self, dataset_root: str):
        """Initialize data loader
        
        Args:
            dataset_root: Path to dataset root directory
        """
        self.dataset_root = Path(dataset_root)
        self.parts = self._discover_parts()
        
    def _discover_parts(self) -> Dict[str, Dict]:
        """Discover all parts in the dataset
        
        Returns:
            Dictionary mapping part codes to their data
        """
        parts = {}
        
        for part_dir in sorted(self.dataset_root.iterdir()):
            if not part_dir.is_dir() or part_dir.name.startswith('.'):
                continue
                
            code = part_dir.name
            metadata = self._parse_metadata(code)
            
            if metadata is None:
                continue
                
            parts[code] = {
                'metadata': metadata,
                'path': part_dir,
                'complexity_levels': self._find_complexity_levels(part_dir)
            }
            
        return parts
    
    def _parse_metadata(self, code: str) -> Tuple[str, ...]:
        """Parse part code into metadata
        
        Example: R-LS-I-HI-36 -> (R, LS, I, HI, 36)
        """
        try:
            parts = code.split('-')
            if len(parts) != 5:
                return None
                
            surface = parts[0]
            size = parts[1]
            shape = parts[2]
            complexity = parts[3]
            number = parts[4]
            
            if surface not in ['R', 'G', 'M', 'T']:
                return None
            if size not in ['TS', 'MS', 'LS']:
                return None
            if shape not in ['O', 'I', 'P']:
                return None
            if complexity not in ['HI', 'LO']:
                return None
                
            return PartMetadata(
                code=code,
                surface_type=surface,
                size_type=size,
                shape_type=shape,
                complexity=complexity,
                part_number=int(number)
            )
        except (ValueError, IndexError):
            return None
    
    def _find_complexity_levels(self, part_dir: Path) -> Dict[str, Path]:
        """Find single/multiple/stacked directories
        
        Args:
            part_dir: Path to part directory
            
        Returns:
            Dictionary mapping complexity level names to their paths
        """
        levels = {}
        for level_dir in part_dir.iterdir():
            if level_dir.is_dir():
                level_name = level_dir.name
                if level_name in ['1_single', '2_multiple', '3_stacked']:
                    levels[level_name] = level_dir
                    
        return levels
    
    def get_part_data(self, part_code: str, complexity_level: str = '1_single') -> Dict:
        """Get data for a specific part and complexity level
        
        Args:
            part_code: Part code (e.g., 'R-LS-I-HI-36')
            complexity_level: '1_single', '2_multiple', or '3_stacked'
            
        Returns:
            Dictionary with video and ground truth paths
        """
        if part_code not in self.parts:
            raise ValueError(f"Part {part_code} not found in dataset")
            
        part_data = self.parts[part_code]
        level_key = complexity_level
        
        if level_key not in part_data['complexity_levels']:
            raise ValueError(f"Complexity level {complexity_level} not found for {part_code}")
            
        level_path = part_data['complexity_levels'][level_key]
        
        # Handle orientations
        orientations = {}
        for item in level_path.iterdir():
            if item.is_dir() and item.name.startswith('orientation_'):
                video_file = item / 'video.MP4'
                gt_file = item / 'ground_truth.ply'
                
                if video_file.exists() and gt_file.exists():
                    orientations[item.name] = {
                        'video': str(video_file),
                        'ground_truth': str(gt_file)
                    }
        
        # If no orientations found, check for files directly in level directory
        if not orientations:
            video_file = level_path / 'video.MP4'
            gt_file = level_path / 'ground_truth.ply'
            
            if video_file.exists() and gt_file.exists():
                orientations['default'] = {
                    'video': str(video_file),
                    'ground_truth': str(gt_file)
                }
        
        return {
            'part_code': part_code,
            'metadata': part_data['metadata'],
            'complexity_level': complexity_level,
            'level_path': str(level_path),
            'orientations': orientations
        }
    
    def list_parts(self, filter_complexity: str = None) -> List[str]:
        """List all available parts
        
        Args:
            filter_complexity: Filter by complexity ('HI' or 'LO'), None for all
            
        Returns:
            List of part codes
        """
        parts = list(self.parts.keys())
        
        if filter_complexity:
            parts = [p for p in parts if self.parts[p]['metadata'].complexity == filter_complexity]
            
        return sorted(parts)
    
    def get_statistics(self) -> Dict:
        """Get dataset statistics
        
        Returns:
            Dictionary with dataset statistics
        """
        stats = {
            'total_parts': len(self.parts),
            'by_surface': {},
            'by_size': {},
            'by_shape': {},
            'by_complexity': {}
        }
        
        for part_code, part_info in self.parts.items():
            meta = part_info['metadata']
            
            # Count by surface
            stats['by_surface'][meta.surface_type] = stats['by_surface'].get(meta.surface_type, 0) + 1
            stats['by_size'][meta.size_type] = stats['by_size'].get(meta.size_type, 0) + 1
            stats['by_shape'][meta.shape_type] = stats['by_shape'].get(meta.shape_type, 0) + 1
            stats['by_complexity'][meta.complexity] = stats['by_complexity'].get(meta.complexity, 0) + 1
        
        return stats
    
    @staticmethod
    def load_ground_truth_pointcloud(ply_path: str) -> np.ndarray:
        """Load ground truth point cloud from PLY file
        
        Args:
            ply_path: Path to PLY file
            
        Returns:
            Numpy array of shape (N, 3) with point coordinates
        """
        pcd = o3d.io.read_point_cloud(ply_path)
        return np.asarray(pcd.points)
    
    @staticmethod
    def load_video(video_path: str) -> Tuple[List[np.ndarray], Dict]:
        """Load video and extract frames
        
        Args:
            video_path: Path to video file
            
        Returns:
            Tuple of (list of frames, video metadata)
        """
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")
        
        frames = []
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        
        cap.release()
        
        metadata = {
            'total_frames': frame_count,
            'fps': fps,
            'width': width,
            'height': height,
            'actual_frames_loaded': len(frames)
        }
        
        return frames, metadata
