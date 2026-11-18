#!/usr/bin/env python3
"""Interactive launcher for automatic heatmap and manual YouTube clipping."""

from __future__ import annotations

import importlib.util
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "clips"


def parse_timestamp(value: str) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS (fractional seconds are accepted)."""
    raw = value.strip()
    if not raw:
        raise ValueError("Timestamp cannot be empty.")
    parts = raw.split(":")
    if len(parts) > 3:
        raise ValueError("Use seconds, MM:SS, or HH:MM:SS.")
    try:
        if len(parts) == 1:
            total = float(parts[0])
        elif len(parts) == 2:
            minutes, seconds = int(parts[0]), float(parts[1])
            if minutes < 0 or not 0 <= seconds < 60:
                raise ValueError
            total = minutes * 60 + seconds
        else:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), float(parts[2])
            if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
                raise ValueError
            total = hours * 3600 + minutes * 60 + seconds
    except (TypeError, ValueError):
        raise ValueError("Invalid timestamp. Examples: 01:00, 01:40, 00:01:40.") from None
    if not math.isfinite(total) or total < 0:
        raise ValueError("Timestamp must be a finite, non-negative time.")
    return total


def timestamp_label(seconds: float) -> str:
    whole = int(seconds)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}-{minutes:02d}-{secs:02d}"


def extract_video_id(url: str) -> str | None:
    """Validate common YouTube watch, Shorts, live, embed and short URLs."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    allowed = {"youtube.com", "www.youtube.com", "m.youtube.com",
               "music.youtube.com", "youtu.be", "www.youtu.be"}
    if host not in allowed:
        return None
    video_id = None
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
    else:
        match = re.match(r"^/(?:shorts|embed|live)/([^/?#]+)", parsed.path)
        if match:
            video_id = match.group(1)
    return video_id if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) else None


def ensure_dependencies() -> bool:
    if not shutil.which("ffmpeg"):
        print("FFmpeg was not found. Install FFmpeg and add it to PATH.")
        return False
    if importlib.util.find_spec("yt_dlp") is None:
        print("yt-dlp is missing. Installing it...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"], check=False
        )
        if result.returncode:
            print("Install yt-dlp with: python -m pip install -U yt-dlp")
            return False
    return True


def make_output_path(video_id: str, start: float, end: float) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"custom_{video_id}_{timestamp_label(start)}_to_{timestamp_label(end)}"
    candidate = OUTPUT_DIR / f"{stem}.mp4"
    suffix = 2
    while candidate.exists():
        candidate = OUTPUT_DIR / f"{stem}_{suffix}.mp4"
        suffix += 1
    return candidate


def download_custom_clip(url: str, start: float, end: float) -> int:
    """Download only the selected section via yt-dlp's FFmpeg section downloader."""
    video_id = extract_video_id(url)
    if not video_id:
        print("Invalid YouTube URL.")
        return 2
    if start < 0 or end <= start:
        print("End time must be later than start time.")
        return 2
    if not ensure_dependencies():
        return 2

    output_path = make_output_path(video_id, start, end)
    command = [
        sys.executable, "-m", "yt_dlp", "--no-playlist",
        "--download-sections", f"*{start:.3f}-{end:.3f}",
        "--force-keyframes-at-cuts",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4", "--output", str(output_path), url.strip(),
    ]
    print(f"\nRequested range: {start:.3f}s → {end:.3f}s ({end - start:.3f}s)")
    print("Downloading selected section with yt-dlp + FFmpeg...\n")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        print("Clip download failed. Check the URL, timestamps, and FFmpeg.")
        return result.returncode
    if output_path.is_file() and output_path.stat().st_size:
        print(f"\nClip saved: {output_path.relative_to(ROOT)}")
        return 0
    matches = [p for p in OUTPUT_DIR.glob(output_path.stem + ".*")
               if p.is_file() and p.stat().st_size]
    if matches:
        print(f"\nClip saved: {matches[0].relative_to(ROOT)}")
        return 0
    print("yt-dlp finished, but the output file was not found.")
    return 1


def prompt_timestamp(label: str) -> float:
    while True:
        try:
            return parse_timestamp(input(f"{label} time (e.g. 01:00 or 00:01:00): "))
        except ValueError as exc:
            print(exc)


def run_custom_mode() -> int:
    url = input("YouTube URL: ").strip()
    if not extract_video_id(url):
        print("Invalid YouTube URL. Paste a video, Shorts, or youtu.be link.")
        return 2
    while True:
        start, end = prompt_timestamp("Start"), prompt_timestamp("End")
        if end > start:
            return download_custom_clip(url, start, end)
        print("End time must be later than start time. Enter the range again.\n")


def main() -> int:
    print("\n=== YouTube Clipper ===")
    print("1. Automatic heatmap clipping (original workflow)")
    print("2. Custom time-range clipping")
    choice = input("Choose mode (1-2): ").strip()
    if choice == "1":
        script = ROOT / "run.py"
        if not script.is_file():
            print("Could not find run.py beside launcher.py.")
            return 2
        return subprocess.run([sys.executable, str(script)], cwd=ROOT, check=False).returncode
    if choice == "2":
        return run_custom_mode()
    print("Invalid choice. Enter 1 or 2.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
