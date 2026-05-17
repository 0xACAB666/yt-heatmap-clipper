import os
import subprocess
import sys

from .config import BOTTOM_HEIGHT, OUTPUT_DIR, PADDING, TOP_HEIGHT
from .models import CropMode, HeatmapSegment
from .subtitles import generate_subtitle


def build_crop_command(crop_mode: CropMode, temp_file: str, cropped_file: str) -> list[str]:
    if crop_mode == "default":
        return [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            temp_file,
            "-vf",
            "scale=-2:1280,crop=720:1280:(iw-720)/2:(ih-1280)/2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "26",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            cropped_file,
        ]

    bottom_x = "0" if crop_mode == "split_left" else "iw-720"
    filter_graph = (
        "scale=-2:1280[scaled];"
        "[scaled]split=2[s1][s2];"
        f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:(ih-1280)/2[top];"
        f"[s2]crop=720:{BOTTOM_HEIGHT}:{bottom_x}:ih-{BOTTOM_HEIGHT}[bottom];"
        "[top][bottom]vstack=inputs=2[out]"
    )
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        temp_file,
        "-filter_complex",
        filter_graph,
        "-map",
        "[out]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "26",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        cropped_file,
    ]


def process_clip(
    video_id: str,
    item: HeatmapSegment,
    index: int,
    total_duration: int,
    crop_mode: CropMode = "default",
    use_subtitle: bool = False,
    requested_model: str | None = None,
    output_dir: str = OUTPUT_DIR,
    work_dir: str | None = None,
) -> bool:
    start_original = item.start
    end_original = item.start + item.duration

    start = max(0, start_original - PADDING)
    end = min(end_original + PADDING, total_duration)

    if end - start < 3:
        return False

    work_dir = work_dir or "."
    os.makedirs(work_dir, exist_ok=True)
    temp_file = os.path.join(work_dir, f"temp_{index}.mp4")
    cropped_file = os.path.join(work_dir, f"temp_cropped_{index}.mp4")
    subtitle_file = os.path.join(work_dir, f"temp_{index}.srt")
    output_file = os.path.join(output_dir, f"clip_{index}.mp4")

    print(f"[Clip {index}] Processing segment ({int(start)}s - {int(end)}s, padding {PADDING}s)")

    download_command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--force-ipv4",
        "--quiet",
        "--no-warnings",
        "--downloader",
        "ffmpeg",
        "--downloader-args",
        f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
        "-f",
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o",
        temp_file,
        f"https://youtu.be/{video_id}",
    ]

    try:
        subprocess.run(
            download_command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if not os.path.exists(temp_file):
            print("Failed to download video segment.")
            return False

        print("  Cropping video...")
        subprocess.run(
            build_crop_command(crop_mode, temp_file, cropped_file),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        os.remove(temp_file)

        if use_subtitle:
            print("  Generating subtitle...")
            if generate_subtitle(cropped_file, subtitle_file, requested_model):
                print("  Burning subtitle to video...")
                subtitle_path = os.path.abspath(subtitle_file).replace("\\", "/").replace(":", "\\:")
                subtitle_command = [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    cropped_file,
                    "-vf",
                    f"subtitles='{subtitle_path}':force_style='FontName=Arial,FontSize=12,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=100'",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-crf",
                    "26",
                    "-c:a",
                    "copy",
                    output_file,
                ]
                subprocess.run(
                    subtitle_command,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                os.remove(cropped_file)
                os.remove(subtitle_file)
            else:
                print("  Subtitle generation failed, continuing without subtitle...")
                os.rename(cropped_file, output_file)
        else:
            os.rename(cropped_file, output_file)

        print("Clip successfully generated.")
        return True
    except subprocess.CalledProcessError as error:
        _cleanup(temp_file, cropped_file, subtitle_file)
        print("Failed to generate this clip.")
        print(f"Error details: {error.stderr if error.stderr else error.stdout}")
        return False
    except Exception as error:
        _cleanup(temp_file, cropped_file, subtitle_file)
        print("Failed to generate this clip.")
        print(f"Error: {str(error)}")
        return False


def _cleanup(*paths: str) -> None:
    for path in paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
