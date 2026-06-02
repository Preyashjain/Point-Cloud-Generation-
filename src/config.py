from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DatasetConfig:
    root: Path = field(default_factory=lambda: Path("dataset"))
    frame_stride: int = 5  # extract every Nth frame from each video


@dataclass
class CameraConfig:
    # Intrinsics in pixels — derived from mm values when not set explicitly
    fx: Optional[float] = None
    fy: Optional[float] = None
    cx: Optional[float] = None  # default: width / 2
    cy: Optional[float] = None  # default: height / 2
    # Nikon D780 full-frame sensor dimensions
    sensor_width_mm: float = 35.9
    sensor_height_mm: float = 24.0
    # Focal length of the lens used during recording — override as needed.
    # 147 mm confirmed by iterative scale-hint corrections (scale=0.9639 at 147 mm).
    focal_length_mm: float = 100.0


@dataclass
class RANSACConfig:
    threshold: float = 1.0  # reprojection threshold in pixels
    confidence: float = 0.999
    max_iters: int = 1000


@dataclass
class SuperPointConfig:
    max_num_keypoints: int = 4096
    detection_threshold: float = 0.003
    nms_radius: int = 3


@dataclass
class LightGlueConfig:
    depth_confidence: float = 0.95
    width_confidence: float = 0.99
    filter_threshold: float = 0.1


@dataclass
class DepthConfig:
    # Depth Anything v2 model size — "Small" is cheapest/fastest (~25 M params)
    model_size: str = "Small"  # "Small" | "Base" | "Large"
    max_depth: float = 5.0  # clip depth beyond this (metres)


@dataclass
class SiftConfig:
    max_num_keypoints: int = 8000
    # COLMAP default contrast threshold is 0.02; lower → more keypoints
    contrast_threshold: float = 0.02
    edge_threshold: float = 10.0
    # Lowe's ratio test threshold (0.75 = COLMAP default)
    ratio_threshold: float = 0.75
    # Mutual nearest-neighbour cross-check (COLMAP: enabled by default)
    cross_check: bool = True


@dataclass
class OrbitConfig:
    # Nikon D780 orbit-rig geometry (source: dataset/README.txt)
    radius_mm: float = 400.0  # horizontal distance to platform centre
    height_mm: float = 410.0  # camera height above platform surface
    # Assume the video covers exactly one full 360° revolution.
    # Set coverage_deg < 360 if the video is a partial orbit.
    coverage_deg: float = 360.0


@dataclass
class Config:
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    ransac: RANSACConfig = field(default_factory=RANSACConfig)
    superpoint: SuperPointConfig = field(default_factory=SuperPointConfig)
    lightglue: LightGlueConfig = field(default_factory=LightGlueConfig)
    sift: SiftConfig = field(default_factory=SiftConfig)
    depth: DepthConfig = field(default_factory=DepthConfig)
    orbit: OrbitConfig = field(default_factory=OrbitConfig)
    device: str = "cuda"
    output_dir: Path = field(default_factory=lambda: Path("outputs"))
