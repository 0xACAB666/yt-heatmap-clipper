from dataclasses import dataclass
from typing import Literal, Optional

CropMode = Literal["default", "split_left", "split_right"]
EventType = Literal[
    "queued",
    "running",
    "clip_started",
    "clip_finished",
    "completed",
    "failed",
]


@dataclass(frozen=True)
class HeatmapSegment:
    start: float
    duration: float
    score: float


@dataclass(frozen=True)
class ClipJobRequest:
    video_id: str
    crop_mode: CropMode = "default"
    use_subtitle: bool = False
    requested_model: Optional[str] = None
    output_dir: Optional[str] = None
    work_dir: Optional[str] = None


@dataclass(frozen=True)
class ProgressEvent:
    type: EventType
    clip_index: Optional[int] = None
    success: Optional[bool] = None
    message: Optional[str] = None
    total_segments: Optional[int] = None


@dataclass(frozen=True)
class ClipJobResult:
    video_id: str
    success_count: int
    total_segments: int
