from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
from lightglue import LightGlue, SuperPoint
from lightglue.utils import rbd

from src.config import LightGlueConfig, SuperPointConfig


@dataclass
class FrameFeatures:
    """SuperPoint features for a single frame, in batched form ready for LightGlue."""
    feats: dict          # batched dict from SuperPoint.extract(), stays on device
    frame_idx: int
    image_size: tuple[int, int]  # (H, W)

    @property
    def num_keypoints(self) -> int:
        return self.feats["keypoints"].shape[1]

    def cpu_keypoints(self) -> torch.Tensor:
        """Return keypoints [N, 2] on CPU (unbatched)."""
        return rbd(self.feats)["keypoints"].cpu()

    def cpu_descriptors(self) -> torch.Tensor:
        """Return descriptors [N, D] on CPU (unbatched)."""
        return rbd(self.feats)["descriptors"].cpu()

    def cpu_scores(self) -> torch.Tensor:
        """Return keypoint confidence scores [N] on CPU (unbatched)."""
        return rbd(self.feats)["keypoint_scores"].cpu()


@dataclass
class MatchResult:
    matches: torch.Tensor          # [K, 2] — (idx_in_frame0, idx_in_frame1)
    matching_scores: torch.Tensor  # [K]
    frame0_idx: int
    frame1_idx: int

    @property
    def num_matches(self) -> int:
        return len(self.matches)


class FeatureExtractor:
    """SuperPoint detector/descriptor + LightGlue matcher."""

    def __init__(
        self,
        cfg_sp: SuperPointConfig,
        cfg_lg: LightGlueConfig,
        device: str = "cuda",
    ):
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.extractor = (
            SuperPoint(
                max_num_keypoints=cfg_sp.max_num_keypoints,
                detection_threshold=cfg_sp.detection_threshold,
                nms_radius=cfg_sp.nms_radius,
            )
            .eval()
            .to(self.device)
        )
        self.matcher = (
            LightGlue(
                features="superpoint",
                depth_confidence=cfg_lg.depth_confidence,
                width_confidence=cfg_lg.width_confidence,
                filter_threshold=cfg_lg.filter_threshold,
            )
            .eval()
            .to(self.device)
        )

    @torch.no_grad()
    def extract(self, image_rgb: np.ndarray, frame_idx: int = 0) -> FrameFeatures:
        """Extract SuperPoint features from an H×W×3 uint8 RGB numpy array."""
        # [3, H, W] float32 in [0, 1]
        tensor = torch.from_numpy(image_rgb).permute(2, 0, 1).float().div(255.0)
        feats = self.extractor.extract(tensor.to(self.device))
        return FrameFeatures(
            feats=feats,
            frame_idx=frame_idx,
            image_size=(image_rgb.shape[0], image_rgb.shape[1]),
        )

    @torch.no_grad()
    def match(self, feat0: FrameFeatures, feat1: FrameFeatures) -> MatchResult:
        """Run LightGlue between two sets of SuperPoint features."""
        result = self.matcher({"image0": feat0.feats, "image1": feat1.feats})
        result = rbd(result)

        # LightGlue >= 0.1 returns 'matches' [K, 2] and 'scores' [K]
        # Fall back to 'matches0' [M] (with -1 for unmatched) for older versions
        if "matches" in result:
            matches = result["matches"]              # [K, 2]
            scores = result.get("scores", torch.ones(len(matches)))
        else:
            m0 = result["matches0"]                  # [M], -1 = unmatched
            valid = m0 >= 0
            idx0 = torch.where(valid)[0]
            idx1 = m0[valid]
            matches = torch.stack([idx0, idx1], dim=1)
            scores = result.get("matching_scores0", torch.ones(len(matches)))[valid]

        return MatchResult(
            matches=matches.cpu(),
            matching_scores=scores.cpu(),
            frame0_idx=feat0.frame_idx,
            frame1_idx=feat1.frame_idx,
        )
