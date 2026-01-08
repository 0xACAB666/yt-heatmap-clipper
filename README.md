# yt-heatmap-clipper

Automatically extract the most engaging segments from YouTube videos using
**Most Replayed (heatmap) data** and convert them into vertical-ready clips with AI-powered subtitles.

This tool parses YouTube audience engagement markers to detect high-interest
moments and generates short vertical videos suitable for YouTube Shorts,
Instagram Reels, and TikTok.

---

## Features

### Core Features

- Extracts YouTube **Most Replayed (heatmap)** segments
- Automatically selects **high-engagement moments**
- Configurable **pre and post padding** for each clip
- Outputs **9:16 vertical video format** (720x1280)
- **No YouTube API key required**
- Supports standard YouTube videos and Shorts

### Advanced Features

- **3 Crop Modes**:
- **Default**: Center crop from original video
- **Split Left**: Top = center content, Bottom = bottom-left (facecam)
- **Split Right**: Top = center content, Bottom = bottom-right (facecam)
- **AI Auto Subtitle** (Faster-Whisper):
- 4-5x faster than standard Whisper
- Support for Indonesian language (and 99+ languages)
- Multiple model sizes: tiny, base, small, medium, large
- Automatic transcription and subtitle burning
- Customizable subtitle style

---

## How It Works

1. **Parse Heatmap Data**: Fetches YouTube watch page and extracts "Most Replayed" markers
2. **Filter Segments**: Identifies high-engagement moments based on score threshold
3. **User Selection**: Interactive menu for crop mode and subtitle preferences
4. **Smart Download**: Downloads only the required time ranges (with padding)
5. **Video Processing**:
   - Scales to 1920px width (maintains aspect ratio)
   - Applies selected crop mode (center, split-left, or split-right)
   - Converts to 720x1280 vertical format
6. **AI Transcription** (optional):
   - Transcribes audio using Faster-Whisper
   - Generates SRT subtitle file
   - Burns subtitles with customizable style
7. **Export**: Saves optimized MP4 clips ready for social media

---

## Requirements

- Python **3.8 or higher**
- **FFmpeg** (must be installed and available in PATH)
- Internet connection

### Python Dependencies:

- `requests` - HTTP requests
- `yt-dlp` - YouTube video downloader
- `faster-whisper` - AI transcription (optional, for subtitles)

### Hardware Requirements:

- **Minimum**: 2 GB RAM, 1 GB free disk space
- **Recommended** (with subtitle): 4 GB RAM, 2 GB free disk space
- Internet bandwidth: ~10 MB/s for smooth downloading

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/0xACAB666/yt-heatmap-clipper.git
cd yt-heatmap-clipper
```

### 2. Install Python Dependencies

**Basic installation** (without subtitle support):

```bash
pip install requests yt-dlp
```

**Full installation** (with AI subtitle support):

```bash
pip install requests yt-dlp faster-whisper
```

Or use requirements file if available:

```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

FFmpeg must be installed separately and added to system PATH.

**Windows:**

1. Download from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to system PATH
4. Restart terminal

**macOS:**

```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install ffmpeg
```

**Verify installation:**

```bash
ffmpeg -version
```

### 4. (Optional) Check Installation

Create `check_setup.py`:

```python
import subprocess
import sys

# Check FFmpeg
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True)
    print("✅ FFmpeg installed")
except FileNotFoundError:
    print("❌ FFmpeg not found")

# Check Python packages
packages = ["requests", "yt_dlp", "faster_whisper"]
for pkg in packages:
    try:
        __import__(pkg)
        print(f"✅ {pkg} installed")
    except ImportError:
        print(f"⚠️  {pkg} not installed")
```

Run: `python check_setup.py`

---

## Usage

### Basic Usage

```bash
python run.py
```

### Interactive Workflow

The script will guide you through an interactive setup:

1. **Select Crop Mode** (1-3):

   - `1` - Default (center crop)
   - `2` - Split 1 (top: center, bottom: bottom-left facecam)
   - `3` - Split 2 (top: center, bottom: bottom-right facecam)

2. **Enable Auto Subtitle** (y/n):

   - `y` - Generate AI-powered subtitles
   - `n` - Skip subtitle generation

3. **Enter YouTube URL**

4. **Processing**:
   - Fetches heatmap data
   - Downloads high-engagement segments
   - Applies selected crop mode
   - Generates and burns subtitles (if enabled)
   - Saves clips to `clips/` directory

### Example Session

```
=== Crop Mode ===
1. Default (center crop)
2. Split 1 (top: center, bottom: bottom-left (facecam))
3. Split 2 (top: center, bottom: bottom-right (facecam))

Select crop mode (1-3): 3
Selected: Split crop (bottom-right facecam)

=== Auto Subtitle ===
Available model: tiny (~75 MB)
Add auto subtitle using Faster-Whisper? (y/n): y
✅ Subtitle enabled (Model: tiny, Bahasa Indonesia)

✅ Faster-Whisper package installed.
✅ Model 'tiny' already cached and ready.

Link YT: https://www.youtube.com/watch?v=...
Reading YouTube heatmap data...
Found 6 high-engagement segments.
Processing clips with 10s pre-padding and 10s post-padding.
[Clip 1] Processing segment (230s - 268s, padding 10s)
  Cropping video...
  Generating subtitle...
  ✅ Model loaded. Transcribing audio...
  Burning subtitle to video...
Clip successfully generated.
```

Generated clips will be saved in the `clips/` directory.

---

## Configuration

You can modify these settings at the top of `run.py`:

### Basic Settings

```python
OUTPUT_DIR = "clips"      # Output directory for generated clips
MAX_DURATION = 60         # Maximum clip duration (seconds)
MIN_SCORE = 0.40          # Minimum heatmap score threshold (0.0-1.0)
MAX_CLIPS = 10            # Maximum number of clips per video
PADDING = 10              # Seconds added before and after each segment
```

### Crop Mode Settings

```python
TOP_HEIGHT = 960          # Height for top section in split mode (px)
BOTTOM_HEIGHT = 320       # Height for bottom section (facecam) in split mode (px)
```

> **Note**: `TOP_HEIGHT + BOTTOM_HEIGHT = 1280` (total vertical resolution)

### Subtitle Settings

```python
USE_SUBTITLE = True       # Enable auto subtitle (can be overridden at runtime)
WHISPER_MODEL = "tiny"    # Whisper model: tiny, base, small, medium, large
```

### Whisper Model Comparison

| Model        | Size   | RAM     | Speed (60s) | Accuracy  | Best For                |
| ------------ | ------ | ------- | ----------- | --------- | ----------------------- |
| **tiny**     | 75 MB  | ~500 MB | ~5-7s       | Good      | Quick clips, low-end PC |
| **base**     | 142 MB | ~700 MB | ~8-10s      | Better    | General purpose         |
| **small**    | 466 MB | ~1.5 GB | ~15-20s     | Great     | Quality content         |
| **medium**   | 1.5 GB | ~3 GB   | ~40-50s     | Excellent | Professional work       |
| **large-v3** | 2.9 GB | ~6 GB   | ~90-120s    | Best      | Production quality      |

> **Recommendation**: Use `tiny` for speed, `small` for quality balance

---

## Output

### Video Specifications

- **Format**: MP4 (H.264 video + AAC audio)
- **Resolution**: 720x1280 (9:16 vertical)
- **Video Codec**: libx264, CRF 26, ultrafast preset
- **Audio Codec**: AAC, 128 kbps
- **Subtitle**: Burned-in (if enabled), white text with black outline

### File Naming

```
clips/
├── clip_1.mp4
├── clip_2.mp4
└── clip_3.mp4
```

Clips are numbered based on their engagement score (highest first).

---

## Crop Mode Visualization

### Mode 1: Default (Center Crop)

```
Original Video (16:9)         Output (9:16)
┌─────────────────────┐       ┌──────┐
│   [   CONTENT   ]   │  -->  │CONTENT│
└─────────────────────┘       └──────┘
       crop center             full height
```

### Mode 2: Split Left (Facecam Bottom-Left)

```
Original Video (16:9)                Output (9:16)
┌─────────────────────────┐         ┌──────────┐
│                         │         │  GAME    │ 960px
│       GAME AREA         │   -->   │ CONTENT  │
│  [👤]                   │         ├──────────┤
└─────────────────────────┘         │ 👤 FACE  │ 350px
    facecam bottom-left             └──────────┘
```

### Mode 3: Split Right (Facecam Bottom-Right)

```
Original Video (16:9)                Output (9:16)
┌─────────────────────────┐         ┌──────────┐
│                         │         │  GAME    │ 960px
│       GAME AREA         │   -->   │ CONTENT  │
│                   [👤]  │         ├──────────┤
└─────────────────────────┘         │ FACE 👤  │ 350px
    facecam bottom-right            └──────────┘
```

---

## Troubleshooting

### FFmpeg not found

```bash
# Windows: Download from https://ffmpeg.org/download.html
# Add to PATH or place ffmpeg.exe in script directory

# macOS:
brew install ffmpeg

# Linux:
sudo apt install ffmpeg
```

### No high-engagement segments found

- Video might not have "Most Replayed" data yet (needs views/engagement)
- Try lowering `MIN_SCORE` (e.g., from 0.40 to 0.30)
- Check if video URL is correct

### Subtitle generation fails

- Ensure internet connection for first-time model download
- Check available RAM (whisper needs ~500MB-2GB depending on model)
- Try smaller model: change `WHISPER_MODEL` from `small` to `tiny`

### Slow transcription

- Use smaller model (`tiny` instead of `small`)
- Faster-Whisper is already 4-5x faster than standard Whisper
- Consider upgrading RAM or using GPU version

### Video download fails

- Check internet connection
- Verify YouTube URL is accessible
- Some videos might be region-locked or have restrictions
- Try updating yt-dlp: `pip install -U yt-dlp`

---

## Tips & Best Practices

### For Gaming Content

- Use **Split Right** or **Split Left** mode (facecam in corner)
- Keep `PADDING = 10` for context before/after action
- Use `small` or `base` model for accurate gaming terminology

### For Tutorial/Vlog Content

- Use **Default** center crop mode
- Increase `MAX_DURATION = 90` for longer explanations
- Enable subtitles with `tiny` model for fast processing

### For Fast-Paced Content

- Reduce `PADDING = 5` to keep clips tight
- Increase `MIN_SCORE = 0.50` for only peak moments
- Use `tiny` model to match quick content style

### Subtitle Customization

Edit line ~368 in `run.py` to customize subtitle style:

```python
# Current style (white text, black outline):
BorderStyle=1,Outline=3,Shadow=2,MarginV=30

# Large text:
FontSize=28,Outline=4

# Position higher (avoid facecam):
MarginV=400

# Different color (yellow):
PrimaryColour=&H00FFFF
```

---

## Contributing

Contributions are welcome! Feel free to:

- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

---

## License

MIT License

---

## Credits

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube video downloader
- [FFmpeg](https://ffmpeg.org/) - Video processing
- [Faster-Whisper](https://github.com/guillaumekln/faster-whisper) - AI transcription
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition model

---

## Support

If you find this tool useful, please ⭐ star this repository!

For issues and questions, please open an issue on GitHub.
