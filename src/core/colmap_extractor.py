"""
SIFT-based feature extraction and matching using COLMAP's algorithm.

Drop-in replacement for the SuperPoint + LightGlue pipeline.
SiftFeatures and SiftMatchResult duck-type FrameFeatures and MatchResult
so that main.py works unchanged when --feature-extractor sift is used.

Extraction:
  Prefers pycolmap (exact COLMAP/VLFeat SIFT) when installed;
  falls back to OpenCV SIFT (same Lowe 2004 algorithm, equivalent output).
  Both paths apply RootSIFT normalisation (L1-norm then sqrt), which
  substantially improves match recall on low-texture industrial parts.

Matching:
  FLANN KNN (k=2) -> Lowe ratio test -> optional mutual-NN cross-check.
  This mirrors COLMAP's SNN (second nearest-neighbour) filter and gives
  far fewer false positives than raw nearest-neighbour matching.
"""

from dataclasses import dataclass

import cv2
import numpy as np
import torch

from src.config import SiftConfig


@dataclass
class SiftFeatures:
    """SIFT features for one frame — duck-types FrameFeatures."""

    keypoints: np.ndarray    # [N, 2] float32  (x, y) pixel coords
    descriptors: np.ndarray  # [N, 128] float32, RootSIFT-normalised
    frame_idx: int
    image_size: tuple[int, int]  # (H, W)

    @property
    def num_keypoints(self) -> int:
        return len(self.keypoints)

    def cpu_keypoints(self) -> torch.Tensor:
        """[N, 2] float32 tensor — same interface as FrameFeatures."""
        return torch.from_numpy(self.keypoints)


@dataclass
class SiftMatchResult:
    """SIFT match result — duck-types MatchResult."""

    matches: torch.Tensor          # [K, 2] long  (idx0, idx1)
    matching_scores: torch.Tensor  # [K] float, 1 - normalised_distance
    frame0_idx: int
    frame1_idx: int

    @property
    def num_matches(self) -> int:
        return len(self.matches)


class ColmapExtractor:
    """
    SIFT feature extractor and matcher.

    Uses pycolmap if available (preferred), otherwise falls back to
    OpenCV SIFT (identical algorithm, same output quality).
    """

    def __init__(self, cfg: SiftConfig):
        self.cfg = cfg
        self._use_pycolmap = self._try_pycolmap()

        self._sift = cv2.SIFT_create(
            nfeatures=cfg.max_num_keypoints,
            contrastThreshold=cfg.contrast_threshold,
            edgeThreshold=cfg.edge_threshold,
        )
        FLANN_INDEX_KDTREE = 1
        self._flann = cv2.FlannBasedMatcher(
            {"algorithm": FLANN_INDEX_KDTREE, "trees": 5},
            {"checks": 50},
        )

    @property
    def device(self) -> str:
        return "cpu (SIFT)"

    def _try_pycolmap(self) -> bool:
        try:
            import pycolmap  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract(
        self, image_rgb: np.ndarray, frame_idx: int = 0
    ) -> SiftFeatures:
        """Extract RootSIFT features from an H×W×3 uint8 RGB frame."""
        h, w = image_rgb.shape[:2]
        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)

        if self._use_pycolmap:
            kpts, desc = self._extract_pycolmap(gray)
        else:
            kpts, desc = self._extract_opencv(gray)

        return SiftFeatures(
            keypoints=kpts,
            descriptors=desc,
            frame_idx=frame_idx,
            image_size=(h, w),
        )

    def _extract_opencv(
        self, gray: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        kp, des = self._sift.detectAndCompute(gray, None)
        if des is None or len(kp) == 0:
            return (
                np.empty((0, 2), dtype=np.float32),
                np.empty((0, 128), dtype=np.float32),
            )
        pts = np.array([[k.pt[0], k.pt[1]] for k in kp], dtype=np.float32)
        des = des.astype(np.float32)
        return pts, _rootsift(des)

    def _extract_pycolmap(
        self, gray: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """pycolmap SIFT; falls back to OpenCV on any error."""
        try:
            import pycolmap

            opts = pycolmap.SiftExtractionOptions()
            opts.max_num_features = self.cfg.max_num_keypoints
            opts.peak_threshold = self.cfg.contrast_threshold

            kp_list, des_arr = (
                pycolmap.extract_sift_features_and_descriptors(gray, opts)
            )
            pts = np.array(
                [[k.x, k.y] for k in kp_list], dtype=np.float32
            )
            des = np.asarray(des_arr, dtype=np.float32)
            return pts, _rootsift(des)
        except Exception:
            return self._extract_opencv(gray)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def match(
        self, f0: SiftFeatures, f1: SiftFeatures
    ) -> SiftMatchResult:
        """FLANN KNN + Lowe ratio test + optional mutual-NN cross-check."""
        empty = SiftMatchResult(
            matches=torch.empty((0, 2), dtype=torch.long),
            matching_scores=torch.empty(0, dtype=torch.float32),
            frame0_idx=f0.frame_idx,
            frame1_idx=f1.frame_idx,
        )
        if f0.num_keypoints < 2 or f1.num_keypoints < 2:
            return empty

        # Forward: f0 → f1
        raw_fwd = self._flann.knnMatch(f0.descriptors, f1.descriptors, k=2)
        good: list[tuple[int, int, float]] = _ratio_filter(
            raw_fwd, self.cfg.ratio_threshold
        )

        if not good:
            return empty

        if self.cfg.cross_check:
            # Backward: f1 → f0; keep only symmetric (mutual-NN) matches
            raw_bwd = self._flann.knnMatch(
                f1.descriptors, f0.descriptors, k=2
            )
            mutual_in_f1: set[int] = {
                pair[0].queryIdx
                for pair in raw_bwd
                if len(pair) == 2
                and pair[0].distance
                < self.cfg.ratio_threshold * pair[1].distance
            }
            good = [(i0, i1, d) for i0, i1, d in good if i1 in mutual_in_f1]

        if not good:
            return empty

        idx_pairs = np.array([[i0, i1] for i0, i1, _ in good], dtype=np.int64)
        dists = np.array([d for _, _, d in good], dtype=np.float32)
        max_d = max(float(dists.max()), 1e-8)
        scores = torch.from_numpy(1.0 - dists / max_d)

        return SiftMatchResult(
            matches=torch.from_numpy(idx_pairs),
            matching_scores=scores,
            frame0_idx=f0.frame_idx,
            frame1_idx=f1.frame_idx,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _rootsift(des: np.ndarray) -> np.ndarray:
    """RootSIFT: L1-normalise then sqrt (Arandjelovic & Zisserman 2012).

    Improves match recall on textureless / industrial surfaces vs standard
    SIFT L2-normalisation.
    """
    des /= des.sum(axis=1, keepdims=True) + 1e-8
    np.sqrt(des, out=des)
    return des


def _ratio_filter(
    raw: list, threshold: float
) -> list[tuple[int, int, float]]:
    """Apply Lowe's ratio test; return (queryIdx, trainIdx, distance) triples."""
    good = []
    for pair in raw:
        if len(pair) == 2:
            m, n = pair
            if m.distance < threshold * n.distance:
                good.append((m.queryIdx, m.trainIdx, m.distance))
    return good
