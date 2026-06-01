from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DatasetConfig:
    root: Path = field(default_factory=lambda: Path("dataset"))
    frame_stride: int = 10  # extract every Nth frame from each video


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
    # Focal length of the lens used during recording — override as needed
    focal_length_mm: float = 50.0


@dataclass
class RANSACConfig:
    threshold: float = 1.0    # reprojection threshold in pixels
    confidence: float = 0.999
    max_iters: int = 1000


@dataclass
class SuperPointConfig:
    max_num_keypoints: int = 2048
    detection_threshold: float = 0.005
    nms_radius: int = 4


@dataclass
class LightGlueConfig:
    depth_confidence: float = 0.95
    width_confidence: float = 0.99
    filter_threshold: float = 0.1


@dataclass
class DepthConfig:
    # Depth Anything v2 model size — "Small" is cheapest/fastest (~25 M params)
    model_size: str = "Small"   # "Small" | "Base" | "Large"
    max_depth: float = 5.0      # clip aligned metric depth beyond this (metres)


@dataclass
class Config:
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    ransac: RANSACConfig = field(default_factory=RANSACConfig)
    superpoint: SuperPointConfig = field(default_factory=SuperPointConfig)
    lightglue: LightGlueConfig = field(default_factory=LightGlueConfig)
    depth: DepthConfig = field(default_factory=DepthConfig)
    device: str = "cuda"
    output_dir: Path = field(default_factory=lambda: Path("outputs"))
