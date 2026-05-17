import os
from collections.abc import Callable

from .config import MAX_CLIPS, OUTPUT_DIR
from .heatmap import fetch_most_replayed
from .models import ClipJobRequest, ClipJobResult, ProgressEvent
from .rendering import process_clip
from .youtube import get_duration

ProgressCallback = Callable[[ProgressEvent], None]


def run_clip_job(
    request: ClipJobRequest,
    on_event: ProgressCallback | None = None,
) -> ClipJobResult:
    _emit(on_event, ProgressEvent("queued"))

    try:
        heatmap_data = fetch_most_replayed(request.video_id)
        if not heatmap_data:
            result = ClipJobResult(request.video_id, success_count=0, total_segments=0)
            _emit(on_event, ProgressEvent("completed"))
            return result

        total_duration = get_duration(request.video_id)
        output_dir = request.output_dir or OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)
        _emit(on_event, ProgressEvent("running", total_segments=len(heatmap_data)))

        success_count = 0
        for item in heatmap_data:
            if success_count >= MAX_CLIPS:
                break

            clip_index = success_count + 1
            _emit(on_event, ProgressEvent("clip_started", clip_index=clip_index))
            success = process_clip(
                request.video_id,
                item,
                clip_index,
                total_duration,
                request.crop_mode,
                request.use_subtitle,
                request.requested_model,
                output_dir,
                request.work_dir,
            )
            _emit(
                on_event,
                ProgressEvent("clip_finished", clip_index=clip_index, success=success),
            )
            if success:
                success_count += 1

        result = ClipJobResult(
            request.video_id,
            success_count=success_count,
            total_segments=len(heatmap_data),
        )
        _emit(on_event, ProgressEvent("completed"))
        return result
    except Exception as error:
        _emit(on_event, ProgressEvent("failed", message=str(error)))
        raise


def _emit(callback: ProgressCallback | None, event: ProgressEvent) -> None:
    if callback is not None:
        callback(event)
