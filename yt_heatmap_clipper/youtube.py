import subprocess
import sys
import re
from urllib.parse import parse_qs, urlparse

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _validated_video_id(candidate: str | None) -> str | None:
    if candidate and VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return _validated_video_id(parsed.path[1:])

    if parsed.hostname in ("youtube.com", "www.youtube.com"):
        if parsed.path == "/watch":
            return _validated_video_id(parse_qs(parsed.query).get("v", [None])[0])
        if parsed.path.startswith("/shorts/"):
            return _validated_video_id(parsed.path.split("/")[2])

    return None


def get_duration(video_id: str) -> int:
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--get-duration",
        f"https://youtu.be/{video_id}",
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True)
        time_parts = result.stdout.strip().split(":")

        if len(time_parts) == 2:
            return int(time_parts[0]) * 60 + int(time_parts[1])
        if len(time_parts) == 3:
            return (
                int(time_parts[0]) * 3600
                + int(time_parts[1]) * 60
                + int(time_parts[2])
            )
    except Exception:
        pass

    return 3600
