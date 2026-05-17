from dataclasses import dataclass
import importlib.util
import shutil
from typing import Callable, Optional


@dataclass(frozen=True)
class AccelerationRecommendation:
    device: str
    compute_type: str
    reason: str


@dataclass(frozen=True)
class ModelRecommendation:
    name: str
    reason: str


@dataclass(frozen=True)
class CapabilityReport:
    ffmpeg_available: bool
    subtitle_backend_available: bool
    acceleration: AccelerationRecommendation
    whisper_model: ModelRecommendation


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _cuda_device_count() -> int:
    try:
        import ctranslate2
    except ImportError:
        return 0

    try:
        return ctranslate2.get_cuda_device_count()
    except RuntimeError:
        return 0


def recommend_acceleration(cuda_device_count: int) -> AccelerationRecommendation:
    if cuda_device_count > 0:
        return AccelerationRecommendation(
            device="cuda",
            compute_type="float16",
            reason="CUDA device detected; prefer GPU transcription throughput.",
        )

    return AccelerationRecommendation(
        device="cpu",
        compute_type="int8",
        reason="No CUDA device detected; use the portable CPU fallback.",
    )


def recommend_whisper_model(
    acceleration: AccelerationRecommendation,
    requested_model: Optional[str] = None,
    configured_model: Optional[str] = None,
) -> ModelRecommendation:
    if requested_model:
        return ModelRecommendation(
            name=requested_model,
            reason="Using the model explicitly requested for this run.",
        )

    if configured_model:
        return ModelRecommendation(
            name=configured_model,
            reason="Using the configured default model.",
        )

    if acceleration.device == "cuda":
        return ModelRecommendation(
            name="small",
            reason="CUDA is available, so 'small' is the balanced quality default.",
        )

    return ModelRecommendation(
        name="base",
        reason="CPU fallback selected; 'base' keeps transcription practical on most machines.",
    )


def detect_capabilities(
    requested_model: Optional[str] = None,
    configured_model: Optional[str] = None,
    *,
    ffmpeg_lookup: Callable[[str], Optional[str]] = shutil.which,
    module_available: Callable[[str], bool] = _module_available,
    cuda_device_count: Callable[[], int] = _cuda_device_count,
) -> CapabilityReport:
    acceleration = recommend_acceleration(cuda_device_count())
    return CapabilityReport(
        ffmpeg_available=ffmpeg_lookup("ffmpeg") is not None,
        subtitle_backend_available=module_available("faster_whisper"),
        acceleration=acceleration,
        whisper_model=recommend_whisper_model(
            acceleration,
            requested_model=requested_model,
            configured_model=configured_model,
        ),
    )
