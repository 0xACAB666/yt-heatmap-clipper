from .config import MODEL_SIZES, WHISPER_MODEL
from .capabilities import detect_capabilities


def get_model_size(model: str) -> str:
    return MODEL_SIZES.get(model, "unknown size")


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_subtitle(
    video_file: str,
    subtitle_file: str,
    requested_model: str | None = None,
) -> bool:
    try:
        from faster_whisper import WhisperModel

        capabilities = detect_capabilities(
            requested_model=requested_model,
            configured_model=WHISPER_MODEL,
        )
        model_name = capabilities.whisper_model.name
        acceleration = capabilities.acceleration

        print(f"  Loading Faster-Whisper model '{model_name}'...")
        print(f"  (If this is first time, downloading ~{get_model_size(model_name)}...)")
        print(
            f"  Using {acceleration.device}/{acceleration.compute_type}: "
            f"{acceleration.reason}"
        )
        model = WhisperModel(
            model_name,
            device=acceleration.device,
            compute_type=acceleration.compute_type,
        )

        print("  ✅ Model loaded. Transcribing audio (4-5x faster than standard Whisper)...")
        segments, _ = model.transcribe(video_file, language="id")

        print("  Generating subtitle file...")
        with open(subtitle_file, "w", encoding="utf-8") as handle:
            for index, segment in enumerate(segments, start=1):
                handle.write(f"{index}\n")
                handle.write(f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}\n")
                handle.write(f"{segment.text.strip()}\n\n")

        return True
    except Exception as error:
        print(f"  Failed to generate subtitle: {str(error)}")
        return False
