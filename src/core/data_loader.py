from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np


@dataclass
class DatasetSample:
    object_id: str       # e.g. "G-TS-O-HI-7"
    scenario: str        # "1_single" | "2_multiple" | "3_stacked"
    orientation: Optional[str]  # "orientation_a/b/c" or None
    video_path: Path
    ground_truth_path: Path

    @property
    def sample_id(self) -> str:
        parts = [self.object_id, self.scenario]
        if self.orientation:
            parts.append(self.orientation)
        return "/".join(parts)

    def __repr__(self) -> str:
        return f"DatasetSample({self.sample_id})"


class DatasetLoader:
    """Discovers all video+ground-truth pairs under the dataset root."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def discover(self) -> list[DatasetSample]:
        samples: list[DatasetSample] = []
        for video_path in sorted(self.root.glob("**/video.MP4")):
            gt_path = video_path.parent / "ground_truth.ply"
            if not gt_path.exists():
                continue
            # relative path parts (without the filename itself)
            rel_parts = video_path.relative_to(self.root).parts
            # structure: [object_id, scenario, "video.MP4"]
            #         or [object_id, scenario, orientation, "video.MP4"]
            object_id = rel_parts[0]
            scenario = rel_parts[1]
            orientation = rel_parts[2] if len(rel_parts) == 4 else None
            samples.append(
                DatasetSample(
                    object_id=object_id,
                    scenario=scenario,
                    orientation=orientation,
                    video_path=video_path,
                    ground_truth_path=gt_path,
                )
            )
        return samples


def extract_frames(
    video_path: Path,
    stride: int = 10,
) -> Iterator[tuple[int, np.ndarray]]:
    """Yield (frame_index, RGB uint8 HxWx3) every `stride` frames."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    try:
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % stride == 0:
                yield frame_idx, cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_idx += 1
    finally:
        cap.release()


def video_info(video_path: Path) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    return info
