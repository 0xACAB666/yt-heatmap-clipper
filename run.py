import os
import re
import json
import sys
import subprocess
import requests
import shutil
from urllib.parse import urlparse, parse_qs

OUTPUT_DIR = "clips"      # Directory where generated clips will be saved
MAX_DURATION = 60         # Maximum duration (in seconds) for each clip
MIN_SCORE = 0.40          # Minimum heatmap intensity score to be considered viral
MAX_CLIPS = 10            # Maximum number of clips to generate per video
MAX_WORKERS = 1           # Number of parallel workers (reserved for future concurrency)
PADDING = 10              # Extra seconds added before and after each detected segment


def extract_video_id(url):
    """
    Extract the YouTube video ID from a given URL.
    Supports standard, shortened, and Shorts URLs.
    """
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path[1:]
    if parsed.hostname in ("youtube.com", "www.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/")[2]
    return None


def cek_dependensi():
    """
    Ensure yt-dlp and FFmpeg are available.
    """
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not shutil.which("ffmpeg"):
        print("FFmpeg not found. Please install FFmpeg.")
        sys.exit()


def ambil_most_replayed(video_id):
    """
    Fetch YouTube 'Most Replayed' heatmap data and
    return high-engagement segments.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        html = requests.get(url, headers=headers, timeout=20).text
    except Exception:
        return []

    match = re.search(
        r'"markers":\s*(\[.*?\])\s*,\s*"?markersMetadata"?',
        html,
        re.DOTALL
    )
    if not match:
        return []

    try:
        markers = json.loads(match.group(1).replace('\\"', '"'))
    except Exception:
        return []

    results = []
    for m in markers:
        if "heatMarkerRenderer" in m:
            m = m["heatMarkerRenderer"]
        try:
            score = float(m.get("intensityScoreNormalized", 0))
            if score >= MIN_SCORE:
                results.append({
                    "start": float(m["startMillis"]) / 1000,
                    "duration": min(
                        float(m["durationMillis"]) / 1000,
                        MAX_DURATION
                    ),
                    "score": score
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_duration(video_id):
    """
    Get total video duration in seconds using yt-dlp.
    """
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--get-duration",
        f"https://youtu.be/{video_id}"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        t = res.stdout.strip().split(":")
        if len(t) == 2:
            return int(t[0]) * 60 + int(t[1])
        if len(t) == 3:
            return int(t[0]) * 3600 + int(t[1]) * 60 + int(t[2])
        return 3600
    except Exception:
        return 3600


def proses_satu_clip(video_id, item, index, total_durasi):
    """
    Download, crop, and export a single vertical clip.
    """
    start_original = item["start"]
    end_original = item["start"] + item["duration"]

    start = max(0, start_original - PADDING)
    end = min(end_original + PADDING, total_durasi)

    if end - start < 3:
        return False

    temp_file = f"temp_{index}.mp4"
    output_file = os.path.join(OUTPUT_DIR, f"clip_{index}.mp4")

    cmd_download = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        "--quiet", "--no-warnings",
        "--downloader", "ffmpeg",
        "--downloader-args",
        f"ffmpeg_i:-ss {start} -to {end} -hide_banner -loglevel error",
        "-f",
        "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", temp_file,
        f"https://youtu.be/{video_id}"
    ]

    try:
        subprocess.run(
            cmd_download,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if not os.path.exists(temp_file):
            return False

        cmd_convert = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", temp_file,
            "-vf", "scale=-2:1280,crop=720:1280",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-c:a", "aac", "-b:a", "128k",
            output_file
        ]

        subprocess.run(
            cmd_convert,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if os.path.exists(temp_file):
            os.remove(temp_file)

        return True

    except Exception:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        return False


def main():
    """
    Main entry point.
    """
    cek_dependensi()

    link = input("Enter YouTube link: ").strip()
    video_id = extract_video_id(link)
    if not video_id:
        print("Invalid YouTube link.")
        return

    heatmap_data = ambil_most_replayed(video_id)
    if not heatmap_data:
        print("No heatmap data found.")
        return

    duration = get_duration(video_id)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    count = 0
    for item in heatmap_data:
        if count >= MAX_CLIPS:
            break
        if proses_satu_clip(video_id, item, count + 1, duration):
            count += 1

    print(f"Finished. {count} clips saved to '{OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()
