import os
import subprocess
import sys
import warnings

from .config import OUTPUT_DIR, PADDING, WHISPER_MODEL
from .capabilities import detect_capabilities
from .engine import run_clip_job
from .models import ClipJobRequest
from .subtitles import get_model_size
from .youtube import extract_video_id


def check_dependencies(install_whisper: bool = False) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if install_whisper:
        selected_model = detect_capabilities(configured_model=WHISPER_MODEL).whisper_model.name
        try:
            import faster_whisper  # noqa: F401

            print("✅ Faster-Whisper package installed.")
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            model_name = f"faster-whisper-{selected_model}"

            model_cached = False
            if os.path.exists(cache_dir):
                try:
                    cached_items = os.listdir(cache_dir)
                    model_cached = any(model_name in item.lower() for item in cached_items)
                except Exception:
                    pass

            if model_cached:
                print(f"✅ Model '{selected_model}' already cached and ready.\n")
            else:
                print(f"⚠️  Model '{selected_model}' not found in cache.")
                print(f"   📥 Will auto-download ~{get_model_size(selected_model)} on first transcribe.")
                print("   ⏱️  Download happens only once, then cached for future use.\n")
        except ImportError:
            print("📦 Installing Faster-Whisper package...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("✅ Faster-Whisper package installed successfully.")
            print(
                f"⚠️  Model '{selected_model}' (~{get_model_size(selected_model)}) "
                "will be downloaded on first use.\n"
            )

    if not detect_capabilities(configured_model=WHISPER_MODEL).ffmpeg_available:
        print("FFmpeg not found. Please install FFmpeg and ensure it is in PATH.")
        sys.exit(1)


def main() -> None:
    _configure_runtime()
    crop_mode, crop_description = _select_crop_mode()
    use_subtitle = _select_subtitle()

    print()
    check_dependencies(install_whisper=use_subtitle)

    link = input("Link YT: ").strip()
    video_id = extract_video_id(link)

    if not video_id:
        print("Invalid YouTube link.")
        return

    def handle_event(event) -> None:
        if event.type == "running":
            print(f"Found {event.total_segments} high-engagement segments.")
            print(f"Processing clips with {PADDING}s pre-padding and {PADDING}s post-padding.")
            print(f"Using crop mode: {crop_description}")

    result = run_clip_job(
        ClipJobRequest(video_id, crop_mode, use_subtitle),
        on_event=handle_event,
    )

    if result.total_segments == 0:
        print("No high-engagement segments found.")
        return

    print(
        f"Finished processing. {result.success_count} clip(s) successfully saved to '{OUTPUT_DIR}'."
    )


def _configure_runtime() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    warnings.filterwarnings("ignore")


def _select_crop_mode() -> tuple[str, str]:
    print("\n=== Crop Mode ===")
    print("1. Default (center crop)")
    print("2. Split 1 (top: center, bottom: bottom-left (facecam))")
    print("3. Split 2 (top: center, bottom: bottom-right ((facecam))")

    while True:
        choice = input("\nSelect crop mode (1-3): ").strip()
        if choice == "1":
            return "default", "Default center crop"
        if choice == "2":
            return "split_left", "Split crop (bottom-left facecam)"
        if choice == "3":
            return "split_right", "Split crop (bottom-right facecam)"
        print("Invalid choice. Please enter 1, 2, or 3.")


def _select_subtitle() -> bool:
    print("\n=== Auto Subtitle ===")
    selected_model = detect_capabilities(configured_model=WHISPER_MODEL).whisper_model.name
    print(f"Available model: {selected_model} (~{get_model_size(selected_model)})")
    subtitle_choice = input("Add auto subtitle using Faster-Whisper? (y/n): ").strip().lower()
    use_subtitle = subtitle_choice in ["y", "yes"]

    if use_subtitle:
        print(f"✅ Subtitle enabled (Model: {selected_model}, Bahasa Indonesia)")
    else:
        print("❌ Subtitle disabled")

    return use_subtitle
