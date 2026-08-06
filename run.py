import os
import re
import json
import sys
import subprocess
import requests
import shutil
import wave
import io
from urllib.parse import urlparse, parse_qs
import warnings
from tqdm import tqdm

sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings("ignore")

OUTPUT_DIR = "clips"      # Directory where generated clips will be saved
MAX_DURATION = 60         # Maximum duration (in seconds) for each clip
MIN_SCORE = 0.40          # Minimum heatmap intensity score to be considered viral
MAX_CLIPS = 10            # Upper bound accepted for the user's requested clip count
MAX_WORKERS = 1           # Number of parallel workers (reserved for future concurrency)
PADDING = 10              # Extra seconds added before and after each detected segment
TOP_HEIGHT = 960          # Height for top section (center content) in split mode
BOTTOM_HEIGHT = 320       # Height for bottom section (facecam) in split mode (Total: 1280px)
USE_SUBTITLE = True       # Enable auto subtitle using Faster-Whisper (4-5x faster)
WHISPER_MODEL = "small"   # Whisper model size: tiny, base, small, medium, large

# speaker_follow crop mode tuning (see specs/008-speaker-follow-crop.md)
FACE_SAMPLE_INTERVAL_SEC = 0.2        # How often (in video seconds) to sample frames for face/mouth tracking
MAX_TRACKED_FACES = 4                 # Cap on simultaneously tracked faces
MIN_SPEAKER_TURN_SEC = 1.5            # Minimum duration a speaker turn must hold before the crop switches again
SPEAKER_CORRELATION_WINDOW_SEC = 1.5  # Sliding-window size for scoring mouth-movement vs. audio-energy correlation

# Needed for yt-dlp's Deno-based JS challenge solver (see cek_dependensi),
# regardless of which player client ends up being used.
YTDLP_REMOTE_COMPONENTS = ["--remote-components", "ejs:github"]

# Resolutions above ~360p are typically only served as DASH (separate
# video-only + audio-only) streams. Trying to network-trim a DASH stream to
# just the padded clip range via ffmpeg (`-ss`/`-to` against the raw format
# URL, or yt-dlp's own --download-sections) hangs indefinitely regardless of
# player client — only a full, sequential download of the format is
# reliable. So the video is downloaded once in full (download_full_video)
# at the chosen resolution, and each clip is trimmed/cropped locally with
# ffmpeg afterward (proses_satu_clip) instead of being fetched individually
# over the network.

def extract_video_id(url):
    """
    Extract the YouTube video ID from a given URL.
    Supports standard YouTube URLs, shortened URLs, and Shorts URLs.
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


def get_model_size(model):
    """
    Get the approximate size of a Whisper model.
    """
    sizes = {
        "tiny": "75 MB",
        "base": "142 MB",
        "small": "466 MB",
        "medium": "1.5 GB",
        "large-v1": "2.9 GB",
        "large-v2": "2.9 GB",
        "large-v3": "2.9 GB"
    }
    return sizes.get(model, "unknown size")


def cek_dependensi(install_whisper=False, install_speaker_follow=False):
    """
    Ensure required dependencies are available.
    Automatically updates yt-dlp and checks FFmpeg availability.
    """
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if install_whisper:
        # Check if faster-whisper package is installed
        try:
            import faster_whisper
            print(f"✅ Faster-Whisper package installed.")
            
            # Check if selected model is cached
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            model_name = f"faster-whisper-{WHISPER_MODEL}"
            
            model_cached = False
            if os.path.exists(cache_dir):
                try:
                    cached_items = os.listdir(cache_dir)
                    model_cached = any(model_name in item.lower() for item in cached_items)
                except Exception:
                    pass
            
            if model_cached:
                print(f"✅ Model '{WHISPER_MODEL}' already cached and ready.\n")
            else:
                print(f"⚠️  Model '{WHISPER_MODEL}' not found in cache.")
                print(f"   📥 Will auto-download ~{get_model_size(WHISPER_MODEL)} on first transcribe.")
                print(f"   ⏱️  Download happens only once, then cached for future use.\n")
                
        except ImportError:
            print("📦 Installing Faster-Whisper package...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "faster-whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"✅ Faster-Whisper package installed successfully.")
            print(f"⚠️  Model '{WHISPER_MODEL}' (~{get_model_size(WHISPER_MODEL)}) will be downloaded on first use.\n")

    if install_speaker_follow:
        # Check if mediapipe + opencv are installed (needed for speaker_follow
        # crop mode's face/mouth tracking). Never fatal — proses_satu_clip
        # falls back to the default center crop per-clip if these end up
        # missing/broken, so a failed install here just prints a warning.
        try:
            import mediapipe  # noqa: F401
            import cv2  # noqa: F401
            print("✅ mediapipe + opencv-python installed (speaker_follow crop mode).\n")
        except ImportError:
            print("📦 Installing mediapipe + opencv-python (speaker_follow crop mode)...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "mediapipe", "opencv-python"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if result.returncode == 0:
                print("✅ mediapipe + opencv-python installed successfully.\n")
            else:
                print("⚠️  Could not install mediapipe/opencv-python — speaker_follow")
                print("   will fall back to the default center crop for every clip.\n")

    if not shutil.which("ffmpeg"):
        print("FFmpeg not found. Please install FFmpeg and ensure it is in PATH.")
        sys.exit(1)

    if not shutil.which("deno"):
        print("Deno not found. YouTube downloads need it to solve YouTube's JS")
        print("challenge — without it, downloads can hang indefinitely or silently")
        print("produce clips with no audio.")
        print("Install: https://deno.land/#installation")
        print('  Windows (PowerShell): irm https://deno.land/install.ps1 | iex')
        sys.exit(1)


def ambil_most_replayed(video_id):
    """
    Fetch and parse YouTube 'Most Replayed' heatmap data.
    Returns a list of high-engagement segments.
    """
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
        re.DOTALL
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
                results.append({
                    "start": float(marker["startMillis"]) / 1000,
                    "duration": min(
                        float(marker["durationMillis"]) / 1000,
                        MAX_DURATION
                    ),
                    "score": score
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def list_available_heights(video_id):
    """
    Query yt-dlp for the video-track heights actually available for this
    video (no player-client restriction, since the full-video download this
    feeds into works reliably across formats/clients — see
    download_full_video). Returns a descending-sorted list of unique
    heights, or an empty list if discovery fails/parses to nothing.
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        *YTDLP_REMOTE_COMPONENTS,
        "-F",
        f"https://youtu.be/{video_id}"
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception:
        return []

    heights = set()
    for line in res.stdout.splitlines():
        match = re.search(r'\b(\d+)x(\d+)\b', line)
        if match:
            heights.add(int(match.group(2)))

    return sorted(heights, reverse=True)


def prompt_resolution(video_id):
    """
    Discover available resolutions for this video and let the user pick one,
    defaulting to the highest. Returns the chosen height, or 1080 (today's
    prior hardcoded cap) if discovery fails.
    """
    print("\nChecking available resolutions...")
    heights = list_available_heights(video_id)

    if not heights:
        print("⚠️  Could not determine available resolutions; using default (up to 1080p).")
        return 1080

    if len(heights) == 1:
        print(f"Only one resolution available for this video: {heights[0]}p. Using it.")
        return heights[0]

    print("\n=== Resolution ===")
    print("Available for this video (via SABR-safe clients):")
    for i, h in enumerate(heights, start=1):
        suffix = " (default)" if i == 1 else ""
        print(f"{i}. {h}p{suffix}")

    while True:
        raw = input("Select resolution [Enter for default]: ").strip()

        if raw == "":
            return heights[0]

        if raw.isdigit() and 1 <= int(raw) <= len(heights):
            return heights[int(raw) - 1]

        print(f"Invalid choice. Enter a number between 1 and {len(heights)}, or press Enter for default.")


def get_duration(video_id):
    """
    Retrieve the total duration of a YouTube video in seconds.
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
        time_parts = res.stdout.strip().split(":")

        if len(time_parts) == 2:
            return int(time_parts[0]) * 60 + int(time_parts[1])
        if len(time_parts) == 3:
            return (
                int(time_parts[0]) * 3600 +
                int(time_parts[1]) * 60 +
                int(time_parts[2])
            )
    except Exception:
        pass

    return 3600


def generate_subtitle(model, video_file, subtitle_file):
    """
    Generate subtitle file using a pre-loaded Faster-Whisper model.
    Returns the list of transcribed caption texts (in order, may be empty)
    on success, or None if transcription failed.
    """
    try:
        tqdm.write("  Transcribing audio (4-5x faster than standard Whisper)...")
        segments, info = model.transcribe(video_file, language="id")

        captions = []

        # Generate SRT format. segments is a lazy generator — each is only
        # actually transcribed as we iterate here, so this loop doubles as
        # live transcription progress.
        with open(subtitle_file, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_time = format_timestamp(segment.start)
                end_time = format_timestamp(segment.end)
                text = segment.text.strip()

                tqdm.write(f"    [{start_time} --> {end_time}] {text}")

                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")

                captions.append(text)

        return captions
    except Exception as e:
        tqdm.write(f"  Failed to generate subtitle: {str(e)}")
        return None


def format_timestamp(seconds):
    """
    Convert seconds to SRT timestamp format (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def stream_subprocess(cmd):
    """
    Run cmd, streaming its combined stdout+stderr live via tqdm.write() as it
    arrives, instead of only showing output after the process exits. Needed
    so the user sees what yt-dlp/ffmpeg are actually doing (extraction steps,
    download/encode progress) instead of a silent wait behind the tqdm bar.

    Python's universal-newline text mode splits readline() on a bare '\r' as
    well as '\n', which is what ffmpeg's '-stats' progress line ends with —
    so this streams that live too, not just newline-terminated messages.

    Raises subprocess.CalledProcessError on non-zero exit. Unlike
    subprocess.run(..., capture_output=True), the exception carries no
    captured output — it was already shown live before the process exited.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in iter(process.stdout.readline, ""):
        line = line.rstrip()
        if line:
            tqdm.write(f"    {line}")

    process.stdout.close()
    returncode = process.wait()

    if returncode != 0:
        raise subprocess.CalledProcessError(returncode, cmd)


def download_full_video(video_id, target_height, full_video_path):
    """
    Download the entire video once, at the given max height, via yt-dlp's
    ordinary sequential downloader (no network-level time-range trimming —
    see the module-level comment above YTDLP_REMOTE_COMPONENTS for why).
    Raises subprocess.CalledProcessError on failure; returns nothing on
    success. Caller is responsible for deleting full_video_path afterward.
    """
    cmd_download = [
        sys.executable, "-m", "yt_dlp",
        "--force-ipv4",
        *YTDLP_REMOTE_COMPONENTS,
        "--merge-output-format", "mp4",
        "-f",
        f"bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]",
        "-o", full_video_path,
        f"https://youtu.be/{video_id}"
    ]

    tqdm.write(f"Downloading full video (up to {target_height}p)...")
    stream_subprocess(cmd_download)

    if not os.path.exists(full_video_path):
        raise RuntimeError("yt-dlp reported success but no output file was found.")


def _extract_audio_energy(video_path, start, end, sample_times):
    """
    Extract mono 16kHz PCM audio for [start, end) and return a list of RMS
    energy values, one per entry in sample_times (seconds, relative to
    start), each measured over [t, t + FACE_SAMPLE_INTERVAL_SEC).
    """
    import numpy as np

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(start), "-to", str(end), "-i", video_path,
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1"
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=120)
    if res.returncode != 0 or not res.stdout:
        raise RuntimeError("ffmpeg audio extraction failed")

    with wave.open(io.BytesIO(res.stdout), "rb") as wf:
        sample_rate = wf.getframerate()
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float64)

    energies = []
    for t in sample_times:
        lo = int(t * sample_rate)
        hi = int((t + FACE_SAMPLE_INTERVAL_SEC) * sample_rate)
        window = samples[lo:hi]
        energies.append(float(np.sqrt(np.mean(window ** 2))) if window.size else 0.0)
    return energies


def _track_faces_and_mouths(video_path, start, end, sample_times):
    """
    Sample frames at sample_times (seconds, relative to start) and run
    mediapipe FaceMesh on each. Faces are matched frame-to-frame into stable
    tracks by nearest normalized center position.

    Returns dict: track_id -> list of (sample_index, mar, center_x_fraction)
    """
    import cv2
    import mediapipe as mp

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video for face tracking: {video_path}")

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=MAX_TRACKED_FACES,
        refine_landmarks=False,
        min_detection_confidence=0.5,
    )

    # track_id -> {"center": (x, y) normalized, "last_seen": sample_index}
    tracks = {}
    next_track_id = 0
    MATCH_THRESHOLD = 0.2   # normalized-distance threshold to match a face to an existing track
    STALE_AFTER = 10        # samples without a match before a track is considered gone

    track_data = {}

    try:
        for i, t in enumerate(sample_times):
            cap.set(cv2.CAP_PROP_POS_MSEC, (start + t) * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = face_mesh.process(rgb)
            if not result.multi_face_landmarks:
                continue

            for landmarks in result.multi_face_landmarks:
                pts = landmarks.landmark
                xs = [p.x for p in pts]
                center_x = sum(xs) / len(xs)
                center_y = sum(p.y for p in pts) / len(pts)

                # MAR = vertical mouth opening / horizontal mouth width
                mouth_w = abs(pts[61].x - pts[291].x) + 1e-6
                mouth_h = abs(pts[13].y - pts[14].y)
                mar = mouth_h / mouth_w

                best_id, best_dist = None, MATCH_THRESHOLD
                for tid, tstate in tracks.items():
                    dist = ((tstate["center"][0] - center_x) ** 2 + (tstate["center"][1] - center_y) ** 2) ** 0.5
                    if dist < best_dist:
                        best_id, best_dist = tid, dist

                if best_id is None:
                    if len(tracks) >= MAX_TRACKED_FACES:
                        continue
                    best_id = next_track_id
                    next_track_id += 1
                    track_data[best_id] = []

                tracks[best_id] = {"center": (center_x, center_y), "last_seen": i}
                track_data[best_id].append((i, mar, center_x))

            # Drop tracks that haven't been seen in a while so a departed
            # face's old position doesn't keep absorbing new detections.
            stale = [tid for tid, tstate in tracks.items() if i - tstate["last_seen"] > STALE_AFTER]
            for tid in stale:
                del tracks[tid]
    finally:
        face_mesh.close()
        cap.release()

    return track_data


def detect_speaker_turns(video_path, start, end):
    """
    Detect active-speaker turns within [start, end) of video_path by
    correlating each tracked face's mouth movement against audio energy over
    a sliding window. See specs/008-speaker-follow-crop.md.

    Returns a list of {"start", "end", "face_x"} dicts (times relative to
    `start`, face_x a 0..1 fraction of frame width), covering the full
    [0, end - start) range with no gaps, or None if detection is unavailable
    or inconclusive (fewer than 2 distinguishable speaking faces).
    """
    try:
        import numpy as np

        duration = end - start
        num_samples = int(duration / FACE_SAMPLE_INTERVAL_SEC)
        if num_samples < 4:
            return None
        sample_times = [i * FACE_SAMPLE_INTERVAL_SEC for i in range(num_samples)]

        track_data = _track_faces_and_mouths(video_path, start, end, sample_times)
        # Need at least 2 faces with a meaningful number of samples to have
        # anything to distinguish between.
        usable_tracks = {tid: pts for tid, pts in track_data.items() if len(pts) >= 4}
        if len(usable_tracks) < 2:
            return None

        energies = _extract_audio_energy(video_path, start, end, sample_times)

        chunk_size = max(1, round(SPEAKER_CORRELATION_WINDOW_SEC / FACE_SAMPLE_INTERVAL_SEC))
        chunk_winner = []  # winning track_id (or None) per chunk
        chunk_bounds = []  # (start_idx, end_idx) per chunk

        last_winner = None
        for chunk_start in range(0, num_samples, chunk_size):
            chunk_end = min(chunk_start + chunk_size, num_samples)
            chunk_bounds.append((chunk_start, chunk_end))

            best_tid, best_score = None, -2.0
            for tid, pts in usable_tracks.items():
                in_chunk = [(idx, mar) for idx, mar, _cx in pts if chunk_start <= idx < chunk_end]
                if len(in_chunk) < 3:
                    continue
                mar_vals = np.array([m for _idx, m in in_chunk])
                energy_vals = np.array([energies[idx] for idx, _m in in_chunk])
                if np.std(mar_vals) < 1e-9 or np.std(energy_vals) < 1e-9:
                    continue
                score = float(np.corrcoef(mar_vals, energy_vals)[0, 1])
                if score > best_score:
                    best_tid, best_score = tid, score

            # Require a minimally positive correlation to actually switch
            # speakers; otherwise hold on whoever was speaking last.
            if best_tid is not None and best_score > 0.1:
                chunk_winner.append(best_tid)
                last_winner = best_tid
            else:
                chunk_winner.append(last_winner)

        if len(set(w for w in chunk_winner if w is not None)) < 2:
            return None

        # Fill any leading None (no winner determined yet) with the first
        # real winner found.
        first_real = next((w for w in chunk_winner if w is not None), None)
        if first_real is None:
            return None
        chunk_winner = [w if w is not None else first_real for w in chunk_winner]

        def face_x_for(tid, lo_idx, hi_idx):
            pts = [cx for idx, _mar, cx in usable_tracks[tid] if lo_idx <= idx < hi_idx]
            return sum(pts) / len(pts) if pts else 0.5

        # Group consecutive same-winner chunks into turns.
        turns = []
        cur_tid = chunk_winner[0]
        cur_start_idx = chunk_bounds[0][0]
        for i in range(1, len(chunk_winner)):
            if chunk_winner[i] != cur_tid:
                lo, hi = cur_start_idx, chunk_bounds[i - 1][1]
                turns.append({"tid": cur_tid, "lo": lo, "hi": hi})
                cur_tid = chunk_winner[i]
                cur_start_idx = chunk_bounds[i][0]
        turns.append({"tid": cur_tid, "lo": cur_start_idx, "hi": chunk_bounds[-1][1]})

        # Merge turns shorter than MIN_SPEAKER_TURN_SEC into a neighbor.
        min_samples = MIN_SPEAKER_TURN_SEC / FACE_SAMPLE_INTERVAL_SEC
        merged = True
        while merged and len(turns) > 1:
            merged = False
            for i, turn in enumerate(turns):
                if (turn["hi"] - turn["lo"]) >= min_samples:
                    continue
                if i == 0:
                    turns[i + 1]["lo"] = turn["lo"]
                else:
                    turns[i - 1]["hi"] = turn["hi"]
                del turns[i]
                merged = True
                break

        result = []
        for turn in turns:
            result.append({
                "start": turn["lo"] * FACE_SAMPLE_INTERVAL_SEC,
                "end": min(turn["hi"] * FACE_SAMPLE_INTERVAL_SEC, duration),
                "face_x": face_x_for(turn["tid"], turn["lo"], turn["hi"]),
            })
        if result:
            result[0]["start"] = 0.0
            result[-1]["end"] = duration

        if len(set(round(r["face_x"], 2) for r in result)) < 2:
            return None

        return result
    except Exception:
        return None


def build_speaker_follow_expr(turns):
    """
    Build an ffmpeg crop-filter `x` expression that holds the 720px-wide crop
    window on each turn's face position, switching at turn boundaries. `iw`
    refers to the scaled frame's width at filter-eval time.
    """
    def x_for(face_x):
        return f"clip(iw*{face_x:.4f}-360,0,iw-720)"

    expr = x_for(turns[-1]["face_x"])
    for turn in reversed(turns[:-1]):
        expr = f"if(lt(t,{turn['end']:.3f}),{x_for(turn['face_x'])},{expr})"
    return expr


def proses_satu_clip(full_video_path, item, index, total_duration, crop_mode="default", use_subtitle=False, whisper_model=None):
    """
    Crop and export a single vertical clip from the already-downloaded full
    video, based on a heatmap segment.

    Args:
        full_video_path: path to the full video downloaded by download_full_video
        crop_mode: "default", "split_left", "split_right", or "speaker_follow"
        use_subtitle: whether to generate and burn subtitle
        whisper_model: pre-loaded Faster-Whisper model (required if use_subtitle)
    """
    start_original = item["start"]
    end_original = item["start"] + item["duration"]

    start = max(0, start_original - PADDING)
    end = min(end_original + PADDING, total_duration)

    if end - start < 3:
        return False

    cropped_file = f"temp_cropped_{index}.mp4"
    subtitle_file = f"temp_{index}.srt"
    output_file = os.path.join(OUTPUT_DIR, f"clip_{index}.mp4")

    tqdm.write(
        f"[Clip {index}] Processing segment "
        f"({int(start)}s - {int(end)}s, padding {PADDING}s)"
    )

    try:
        speaker_turns = None
        if crop_mode == "speaker_follow":
            speaker_turns = detect_speaker_turns(full_video_path, start, end)
            if not speaker_turns:
                tqdm.write(
                    f"[Clip {index}] Speaker-follow detection unavailable/inconclusive "
                    f"— using default center crop."
                )
                crop_mode = "default"

        # Trim the clip range and crop, in one local ffmpeg pass — no
        # network involved, so -ss/-to against the full local file is fast
        # and reliable regardless of source resolution/codec.
        if crop_mode == "default":
            # Standard center crop - ambil dari tengah video
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
                "-ss", str(start), "-to", str(end), "-i", full_video_path,
                "-vf", "scale=-2:1280,crop=720:1280:(iw-720)/2:(ih-1280)/2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]
        elif crop_mode == "split_left":
            # Split crop:
            # - Top: konten game dari tengah-tengah video (960px)
            # - Bottom: facecam dari kiri bawah video asli (320px)
            vf = (
                f"scale=-2:1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:(ih-1280)/2[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:0:ih-{BOTTOM_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
                "-ss", str(start), "-to", str(end), "-i", full_video_path,
                "-filter_complex", vf,
                "-map", "[out]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]
        elif crop_mode == "split_right":
            # Split crop:
            # - Top: konten game dari tengah-tengah video (960px)
            # - Bottom: facecam dari kanan bawah video asli (320px)
            vf = (
                f"scale=-2:1280[scaled];"
                f"[scaled]split=2[s1][s2];"
                f"[s1]crop=720:{TOP_HEIGHT}:(iw-720)/2:(ih-1280)/2[top];"
                f"[s2]crop=720:{BOTTOM_HEIGHT}:iw-720:ih-{BOTTOM_HEIGHT}[bottom];"
                f"[top][bottom]vstack=inputs=2[out]"
            )
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
                "-ss", str(start), "-to", str(end), "-i", full_video_path,
                "-filter_complex", vf,
                "-map", "[out]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]
        elif crop_mode == "speaker_follow":
            # Crop stays centered on whoever detect_speaker_turns() judged to
            # be talking, jumping to the next speaker's position at each
            # detected turn boundary (discrete holds, not a smooth pan).
            x_expr = build_speaker_follow_expr(speaker_turns)
            cmd_crop = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
                "-ss", str(start), "-to", str(end), "-i", full_video_path,
                "-vf", f"scale=-2:1280,crop=720:1280:{x_expr}:(ih-1280)/2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k",
                cropped_file
            ]

        tqdm.write("  Cropping video...")
        stream_subprocess(cmd_crop)

        # Generate and burn subtitle if enabled
        if use_subtitle:
            tqdm.write("  Generating subtitle...")
            captions = generate_subtitle(whisper_model, cropped_file, subtitle_file)
            if captions is not None:
                tqdm.write("  Burning subtitle to video...")
                # Get absolute path for subtitle file
                abs_subtitle_path = os.path.abspath(subtitle_file)
                # Escape for FFmpeg: replace \ with / and escape special chars
                subtitle_path = abs_subtitle_path.replace("\\", "/").replace(":", "\\:")

                cmd_subtitle = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
                    "-i", cropped_file,
                    "-vf", f"subtitles='{subtitle_path}':force_style='FontName=Arial,FontSize=12,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=100'",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-c:a", "copy",
                    output_file
                ]

                stream_subprocess(cmd_subtitle)

                os.remove(cropped_file)
                os.remove(subtitle_file)

                if captions:
                    caption_file = os.path.join(OUTPUT_DIR, f"clip_{index}.txt")
                    with open(caption_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(captions) + "\n")
            else:
                # If subtitle generation failed, use cropped file as output
                tqdm.write("  Subtitle generation failed, continuing without subtitle...")
                os.rename(cropped_file, output_file)
        else:
            # No subtitle, rename cropped file to output
            os.rename(cropped_file, output_file)

        tqdm.write("Clip successfully generated.")
        return True

    except subprocess.CalledProcessError as e:
        # Cleanup temp files
        for f in [cropped_file, subtitle_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        tqdm.write(f"Failed to generate this clip (exit code {e.returncode}). See output above.")
        return False
    except Exception as e:
        # Cleanup temp files
        for f in [cropped_file, subtitle_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

        tqdm.write("Failed to generate this clip.")
        tqdm.write(f"Error: {str(e)}")
        return False


def format_seconds_display(seconds):
    """
    Format seconds as MM:SS, or HH:MM:SS for durations of an hour or more.
    """
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_selection(raw, max_index):
    """
    Parse a comma-separated list of indices/ranges (e.g. "2,4,7" or "2-5,9")
    into a set of unique integers within 1..max_index.
    Returns None if the input is empty or any token is invalid/out of range.
    """
    indices = set()

    for token in raw.split(","):
        token = token.strip()
        if not token:
            return None

        if "-" in token:
            lo_raw, sep, hi_raw = token.partition("-")
            lo_raw, hi_raw = lo_raw.strip(), hi_raw.strip()
            if not lo_raw.isdigit() or not hi_raw.isdigit():
                return None
            lo, hi = int(lo_raw), int(hi_raw)
            if lo > hi:
                lo, hi = hi, lo
            indices.update(range(lo, hi + 1))
        else:
            if not token.isdigit():
                return None
            indices.add(int(token))

    if not indices or any(i < 1 or i > max_index for i in indices):
        return None

    return indices


def select_segments(heatmap_data):
    """
    If more than one qualifying segment exists, list them chronologically
    (start time ascending) with their timeframe and score, and let the user
    pick which ones to clip — the heatmap tends to over-rate the video's
    opening seconds since most viewers start there, so a plain top-score
    pick can be misleading. With only one qualifying segment there's no
    real choice to make, so it's used directly.

    Returns the selected segments in chronological order.
    """
    if len(heatmap_data) <= 1:
        return list(heatmap_data)

    chronological = sorted(heatmap_data, key=lambda x: x["start"])

    print("\n=== High-Engagement Segments (chronological) ===")
    for i, item in enumerate(chronological, start=1):
        start = item["start"]
        end = item["start"] + item["duration"]
        print(
            f"{i}) {format_seconds_display(start)}-{format_seconds_display(end)} "
            f"({int(start)}s-{int(end)}s, score {item['score']:.2f})"
        )

    while True:
        raw = input(
            f"\nWhich segment(s) do you want to clip? "
            f"(e.g. 1,3 or 2-4; range 1-{len(chronological)}): "
        ).strip()

        indices = parse_selection(raw, len(chronological))
        if indices is None:
            print(
                f"Invalid input. Enter numbers between 1 and {len(chronological)}, "
                f"e.g. 1,3 or 2-4."
            )
            continue

        selected_indices = sorted(indices)

        if len(selected_indices) > MAX_CLIPS:
            print(
                f"Selected {len(selected_indices)} segment(s), but the max per run "
                f"is {MAX_CLIPS} — keeping the first {MAX_CLIPS} in chronological order."
            )
            selected_indices = selected_indices[:MAX_CLIPS]

        return [chronological[i - 1] for i in selected_indices]


def main():
    """
    Main entry point of the application.
    """
    # Select crop mode
    print("\n=== Crop Mode ===")
    print("1. Default (center crop)")
    print("2. Split 1 (top: center, bottom: bottom-left (facecam))")
    print("3. Split 2 (top: center, bottom: bottom-right ((facecam))")
    print("4. Speaker follow (auto-crop to whoever is talking)")

    while True:
        choice = input("\nSelect crop mode (1-4): ").strip()
        if choice == "1":
            crop_mode = "default"
            crop_desc = "Default center crop"
            break
        elif choice == "2":
            crop_mode = "split_left"
            crop_desc = "Split crop (bottom-left facecam)"
            break
        elif choice == "3":
            crop_mode = "split_right"
            crop_desc = "Split crop (bottom-right facecam)"
            break
        elif choice == "4":
            crop_mode = "speaker_follow"
            crop_desc = "Speaker-follow crop (auto-crop to active speaker)"
            break
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")

    print(f"Selected: {crop_desc}")
    
    # Ask for subtitle
    print("\n=== Auto Subtitle ===")
    print(f"Available model: {WHISPER_MODEL} (~{get_model_size(WHISPER_MODEL)})")
    subtitle_choice = input("Add auto subtitle using Faster-Whisper? (y/n): ").strip().lower()
    use_subtitle = subtitle_choice in ["y", "yes"]
    
    if use_subtitle:
        print(f"✅ Subtitle enabled (Model: {WHISPER_MODEL}, Bahasa Indonesia)")
    else:
        print("❌ Subtitle disabled")
    
    print()
    
    # Check dependencies
    cek_dependensi(install_whisper=use_subtitle, install_speaker_follow=(crop_mode == "speaker_follow"))

    link = input("Link YT: ").strip()
    video_id = extract_video_id(link)

    if not video_id:
        print("Invalid YouTube link.")
        return

    target_height = prompt_resolution(video_id)

    heatmap_data = ambil_most_replayed(video_id)

    if not heatmap_data:
        print("No high-engagement segments found.")
        return

    print(f"Found {len(heatmap_data)} high-engagement segments.")

    selected_segments = select_segments(heatmap_data)

    total_duration = get_duration(video_id)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    full_video_path = "temp_full_video.mp4"
    try:
        download_full_video(video_id, target_height, full_video_path)
    except Exception as e:
        print(f"Failed to download the video: {e}")
        return

    whisper_model = None
    if use_subtitle:
        from faster_whisper import WhisperModel
        print(f"Loading Faster-Whisper model '{WHISPER_MODEL}'...")
        print(f"(If this is first time, downloading ~{get_model_size(WHISPER_MODEL)}...)")
        # Use int8 for CPU efficiency, or "float16" for GPU
        whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        print("Model loaded.\n")

    print(
        f"Processing clips with {PADDING}s pre-padding "
        f"and {PADDING}s post-padding."
    )
    print(f"Using crop mode: {crop_desc}")

    success_count = 0

    try:
        with tqdm(total=len(selected_segments), desc="Generating clips", unit="clip") as pbar:
            for item in selected_segments:
                if proses_satu_clip(
                    full_video_path,
                    item,
                    success_count + 1,
                    total_duration,
                    crop_mode,
                    use_subtitle,
                    whisper_model
                ):
                    success_count += 1
                    pbar.update(1)
    finally:
        if os.path.exists(full_video_path):
            os.remove(full_video_path)

    print(
        f"Finished processing. "
        f"{success_count} clip(s) successfully saved to '{OUTPUT_DIR}'."
    )


if __name__ == "__main__":
    main()