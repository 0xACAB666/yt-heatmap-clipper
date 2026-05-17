import json
import re

from .config import MAX_DURATION, MIN_SCORE
from .models import HeatmapSegment


def fetch_most_replayed(video_id: str) -> list[HeatmapSegment]:
    import requests

    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {"User-Agent": "Mozilla/5.0"}

    print("Reading YouTube heatmap data...")

    try:
        html = requests.get(url, headers=headers, timeout=20).text
    except Exception:
        return []

    match = re.search(
        r'"markers":\s*(\[.*?\])\s*,\s*"?markersMetadata"?',
        html,
        re.DOTALL,
    )

    if not match:
        return []

    try:
        markers = json.loads(match.group(1).replace('\\"', '"'))
    except Exception:
        return []

    results = []

    for marker in markers:
        if "heatMarkerRenderer" in marker:
            marker = marker["heatMarkerRenderer"]

        try:
            score = float(marker.get("intensityScoreNormalized", 0))
            if score >= MIN_SCORE:
                results.append(
                    HeatmapSegment(
                        start=float(marker["startMillis"]) / 1000,
                        duration=min(float(marker["durationMillis"]) / 1000, MAX_DURATION),
                        score=score,
                    )
                )
        except Exception:
            continue

    results.sort(key=lambda item: item.score, reverse=True)
    return results
