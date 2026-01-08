# yt-heatmap-clipper

Automatically extract the most engaging segments from YouTube videos using
**Most Replayed (heatmap) data** and convert them into vertical-ready clips.

This tool parses YouTube audience engagement markers to detect high-interest
moments and generates short vertical videos suitable for YouTube Shorts,
Instagram Reels, and TikTok.

---

## Features

- Extracts YouTube **Most Replayed (heatmap)** segments
- Automatically selects **high-engagement moments**
- Configurable **pre and post padding** for each clip
- Outputs **9:16 vertical video format**
- No YouTube API key required
- Supports standard YouTube videos and Shorts

---

## How It Works

1. Fetches the YouTube watch page
2. Parses heatmap (Most Replayed) markers
3. Filters segments based on engagement score
4. Downloads only the required time ranges
5. Crops and exports vertical clips using FFmpeg

---

## Requirements

- Python **3.8 or higher**
- **FFmpeg** (must be installed and available in PATH)
- Internet connection

Python dependencies:
- `requests`
- `yt-dlp`

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/0xACAB666/yt-heatmap-clipper.git
cd yt-heatmap-clipper
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

FFmpeg must be installed separately.

- Windows: https://ffmpeg.org/download.html
- macOS: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

Verify installation:

```bash
ffmpeg -version
```

---

## Usage

```bash
python run.py
```

Then enter a YouTube URL when prompted.

Generated clips will be saved in the `clips/` directory.

---

## Configuration

```python
OUTPUT_DIR = "clips"      # Output directory
MAX_DURATION = 60         # Maximum clip duration (seconds)
MIN_SCORE = 0.40          # Minimum heatmap score threshold
MAX_CLIPS = 10            # Maximum clips per video
MAX_WORKERS = 1           # Reserved for future concurrency
PADDING = 10              # Seconds added before and after each segment
```

---

## Output

- Format: MP4 (H.264 + AAC)
- Resolution: 720x1280 (9:16)

---

## License

MIT License
