"""
Monocular depth densification via Depth Anything v2.

Pipeline for one frame:
  1. DepthEstimator.predict()   → relative depth map  [H, W]  (unit-less)
  2. align_depth_to_metric()    → (scale, shift) from sparse triangulated pts
  3. depth_to_pointcloud()      → dense metric 3D points  [N, 3]  + colors

The relative depth is affine-aligned (Z = scale * d + shift) to the metric
scale established by the sparse triangulation step.  At least ~10 sparse
inlier points land inside the image for a stable fit; fewer points fall back
to scale-only alignment, then to the identity.
"""

from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

from src.config import DepthConfig


# ---------------------------------------------------------------------------
# Model wrapper
# ---------------------------------------------------------------------------

class DepthEstimator:
    """Depth Anything v2 wrapper — predict() returns a relative depth map."""

    _MODEL_IDS = {
        "Small": "depth-anything/Depth-Anything-V2-Small-hf",
        "Base":  "depth-anything/Depth-Anything-V2-Base-hf",
        "Large": "depth-anything/Depth-Anything-V2-Large-hf",
    }

    def __init__(self, cfg: DepthConfig, device: str = "cuda"):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        model_id = self._MODEL_IDS[cfg.model_size]
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = (
            AutoModelForDepthEstimation.from_pretrained(model_id)
            .eval()
            .to(self.device)
        )
        self.max_depth = cfg.max_depth

    @torch.no_grad()
    def predict(self, image_rgb: np.ndarray) -> np.ndarray:
        """
        Run Depth Anything v2 on an H×W×3 uint8 RGB array.
        Returns [H, W] float32 relative depth (larger = closer).
        """
        H, W = image_rgb.shape[:2]
        pil = Image.fromarray(image_rgb)
        inputs = self.processor(images=pil, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        outputs = self.model(**inputs)
        # predicted_depth: [1, H', W'] — may differ from input resolution
        depth = F.interpolate(
            outputs.predicted_depth.unsqueeze(1).float(),
            size=(H, W),
            mode="bicubic",
            align_corners=False,
        ).squeeze().cpu().numpy()   # [H, W]

        return depth.astype(np.float32)


# ---------------------------------------------------------------------------
# Metric alignment
# ---------------------------------------------------------------------------

def align_depth_to_metric(
    depth_rel: np.ndarray,     # [H, W] relative depth from model
    pts3d: np.ndarray,         # [N, 3] sparse metric points (camera coords)
    K: np.ndarray,             # [3, 3] intrinsic matrix
) -> tuple[float, float]:
    """
    Estimate affine alignment  Z_metric ≈ scale * d_rel + shift
    by projecting sparse triangulated points into the image and sampling
    the corresponding relative depth values.

    Falls back to scale-only (shift=0) when fewer than 4 points project
    inside the image, and to (1, 0) when there are none.
    """
    H, W = depth_rel.shape
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]

    valid = ~np.isnan(pts3d).any(axis=1) & (pts3d[:, 2] > 0)
    pts = pts3d[valid]
    if len(pts) == 0:
        return 1.0, 0.0

    # Project to pixel grid
    u = np.round(pts[:, 0] * fx / pts[:, 2] + cx).astype(int)
    v = np.round(pts[:, 1] * fy / pts[:, 2] + cy).astype(int)
    in_bounds = (u >= 0) & (u < W) & (v >= 0) & (v < H)

    n = in_bounds.sum()
    if n == 0:
        return 1.0, 0.0

    Z_metric = pts[in_bounds, 2].astype(np.float64)
    d_rel = depth_rel[v[in_bounds], u[in_bounds]].astype(np.float64)

    if n < 4:
        # Scale-only: scale = mean(Z / d)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratios = Z_metric / np.where(d_rel != 0, d_rel, np.nan)
        scale = float(np.nanmedian(ratios))
        return scale, 0.0

    # Affine: Z = scale * d + shift  →  least squares
    A = np.column_stack([d_rel, np.ones(n)])
    (scale, shift), *_ = np.linalg.lstsq(A, Z_metric, rcond=None)
    return float(scale), float(shift)


# ---------------------------------------------------------------------------
# Dense backprojection
# ---------------------------------------------------------------------------

def depth_to_pointcloud(
    depth_metric: np.ndarray,            # [H, W]
    K: np.ndarray,                       # [3, 3]
    image_rgb: Optional[np.ndarray],     # [H, W, 3] uint8, for vertex colours
    max_depth: float = 5.0,
) -> tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Backproject a metric depth map to 3D.
    Returns (pts3d [N,3], colors [N,3] or None).
    """
    H, W = depth_metric.shape
    u_g, v_g = np.meshgrid(np.arange(W, dtype=np.float32),
                            np.arange(H, dtype=np.float32))
    Z = depth_metric
    X = (u_g - K[0, 2]) * Z / K[0, 0]
    Y = (v_g - K[1, 2]) * Z / K[1, 1]

    pts3d = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
    valid = (Z.ravel() > 0) & (Z.ravel() <= max_depth) & \
            ~np.isnan(pts3d).any(axis=1)

    pts3d = pts3d[valid]
    colors = image_rgb.reshape(-1, 3)[valid] if image_rgb is not None else None
    return pts3d, colors


# ---------------------------------------------------------------------------
# Convenience: full densification for one frame
# ---------------------------------------------------------------------------

def densify_frame(
    image_rgb: np.ndarray,      # [H, W, 3]
    sparse_pts3d: np.ndarray,   # [N, 3] metric sparse points in camera coords
    K: np.ndarray,
    estimator: DepthEstimator,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Predict relative depth, align to metric scale, backproject.
    Returns (pts3d [M,3], colors [M,3]).
    """
    depth_rel = estimator.predict(image_rgb)
    scale, shift = align_depth_to_metric(depth_rel, sparse_pts3d, K)
    depth_metric = np.clip(
        scale * depth_rel + shift,
        0.0,
        estimator.max_depth,
    )
    pts3d, colors = depth_to_pointcloud(
        depth_metric, K, image_rgb, max_depth=estimator.max_depth
    )
    return pts3d, colors
