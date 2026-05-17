# yt-heatmap-clipper

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg)](https://ffmpeg.org/)
[![Whisper](https://img.shields.io/badge/AI-Faster--Whisper-orange.svg)](https://github.com/guillaumekln/faster-whisper)

Automatically extract the most engaging segments from YouTube videos using **Most Replayed (heatmap) data** and convert them into vertical-ready clips with AI-powered subtitles.

This tool parses YouTube audience engagement markers to detect high-interest moments and generates short vertical videos suitable for **YouTube Shorts**, **Instagram Reels**, and **TikTok**.

---

## ✨ Features

### core-engine (Shared Logic)
- **Reusable engine**: The CLI and Dashboard both use a shared core for heatmap parsing, video processing, and transcription.
- **Isolated Job Execution**: Each browser session or dashboard job runs in its own workspace, preventing file conflicts during concurrent use.
- **Dynamic Device Detection**: Automatically selects between CUDA and CPU for transcription based on local hardware capabilities.
- **Intelligent Model Fallback**: Recommends appropriate Whisper models (e.g., `small` for GPU, `base` for CPU) to balance quality and speed.

---

## ⚙️ How It Works

1.  **Parse Heatmap Data**: Fetches YouTube watch page and extracts "Most Replayed" markers.
2.  **Filter Segments**: Identifies high-engagement moments based on score threshold.
3.  **Job Orchestration**: Hands off the request to a shared engine that manages downloading and rendering.
4.  **Smart Download**: Downloads only the required time ranges (with padding).
5.  **Video Processing**:
    - Scales to 1920px width (maintains aspect ratio).
    - Applies selected crop mode (center, split-left, or split-right).
    - Converts to 720x1280 vertical format.
6.  **AI Transcription** (optional):
    - Transcribes audio using Faster-Whisper.
    - Automatically recommends the best compute type (e.g., `float16` for GPU or `int8` for CPU).
    - Burns subtitles with customizable style.
7.  **Export**: Saves optimized MP4 clips ready for social media.

---

## 🛠️ Requirements

- Python **3.8 or higher**
- **FFmpeg** (must be installed and available in PATH)
- Internet connection

### Python Dependencies:
- `requests` - HTTP requests
- `yt-dlp` - YouTube video downloader
- `fastapi` - local dashboard web framework
- `uvicorn` - local ASGI server for the dashboard
- `python-multipart` - HTML form parsing for the dashboard
- `httpx` - HTTP client used by the dashboard test client
- `faster-whisper` - AI transcription (optional)

### Hardware Requirements:
- **Minimum**: 2 GB RAM, 1 GB free disk space
- **Recommended**: 4 GB RAM, NVIDIA GPU (for CUDA acceleration)
- Internet bandwidth: ~10 MB/s for smooth downloading

---

## 🚀 Installation

### Clone Repository

```bash
git clone https://github.com/0xACAB666/yt-heatmap-clipper.git
cd yt-heatmap-clipper
```

### Install Dependencies

**Basic installation** (without subtitle support):
```bash
pip install -r requirements.txt
```

**Full installation** (with AI subtitle support):
```bash
pip install -r requirements.txt faster-whisper
```

### Install FFmpeg

FFmpeg is the core engine for video processing and **must** be installed.

#### 🪟 Windows
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html).
2. Extract to `C:\ffmpeg`.
3. Add `C:\ffmpeg\bin` to system PATH.
4. Restart terminal.

#### 🍎 macOS
```bash
brew install ffmpeg
```

#### 🐧 Linux
```bash
sudo apt update && sudo apt install ffmpeg
```

### 🩺 Verify Installation

Run the included check script to verify if **FFmpeg** and dependencies are ready:

```bash
python check_setup.py
```

---

## 📖 Usage

### Basic Usage (CLI)

```bash
python run.py
```

The script will guide you through an interactive setup:
1.  **Select Crop Mode** (1-3).
2.  **Enable Auto Subtitle** (y/n).
3.  **Enter YouTube URL**.

### Local Dashboard (Web)

For a browser-based experience with job tracking:

```bash
uvicorn yt_heatmap_clipper.web.app:app
```

Then open `http://127.0.0.1:8000` in your browser.

**Dashboard Features:**
- **Job Status Tracking**: Monitor progress from "queued" to "completed".
- **Real-time Logs**: See which clip is currently being processed.
- **Workspace Isolation**: Each job is stored in its own directory (`clips/web/<job-id>/`).
- **Downloadable Outputs**: Download generated clips directly from the dashboard.
- **Environment Summary**: Displays detected hardware acceleration and recommended models.

### 💻 CLI Example Session

```text
=== Crop Mode ===
1. Default (center crop)
2. Split 1 (top: center, bottom: bottom-left (facecam))
3. Split 2 (top: center, bottom: bottom-right (facecam))

Select crop mode (1-3): 3
Selected: Split crop (bottom-right facecam)

=== Auto Subtitle ===
Available model: base (~142 MB)
Add auto subtitle using Faster-Whisper? (y/n): y
✅ Subtitle enabled (Model: base, Bahasa Indonesia)

✅ Faster-Whisper package installed.
✅ Model 'base' already cached and ready.

Link YT: https://www.youtube.com/watch?v=dQw4w9WgXcQ
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

Generated clips are saved in the `clips/` directory.

---

## 🦾 Hardware Acceleration & Recommendations

The tool automatically detects your hardware and configures the best path for AI transcription.

### Acceleration Detection
- **CUDA**: If an NVIDIA GPU is detected, the tool uses `float16` compute type for high-throughput transcription.
- **CPU**: Fallback to `int8` quantization for efficient processing on standard processors.

### Model Selection Logic
- **Requested Model**: Overrides everything if you specify a model for a run (for example, the dashboard model override).
- **Configured Model**: `WHISPER_MODEL` is an optional shared override. Leave it as `None` to use automatic hardware-based recommendation in ordinary CLI/dashboard flows.
- **CUDA Default**: Recommends `small` for a balance of quality and speed.
- **CPU Default**: Recommends `base` to keep transcription practical on most machines.

---

## 🔧 Configuration

You can modify these shared settings in `yt_heatmap_clipper/config.py`:

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
WHISPER_MODEL = None      # Optional override: tiny, base, small, medium, large; None = auto recommendation
```

### Whisper Model Comparison

| Model | Size | RAM | Speed (60s) | Accuracy | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **tiny** | 75 MB | ~500 MB | ~5-7s | Good | Quick clips, low-end PC |
| **base** | 142 MB | ~700 MB | ~8-10s | Better | General purpose |
| **small** | 466 MB | ~1.5 GB | ~15-20s | Great | Quality content |
| **medium** | 1.5 GB | ~3 GB | ~40-50s | Excellent | Professional work |
| **large-v3** | 2.9 GB | ~6 GB | ~90-120s | Best | Production quality |

> **Recommendation**: Use `tiny` for speed, `small` for quality balance.

---

## 📂 Output

### Video Specifications
- **Format**: MP4 (H.264 video + AAC audio)
- **Resolution**: 720x1280 (9:16 vertical)
- **Video Codec**: libx264, CRF 26, ultrafast preset
- **Audio Codec**: AAC, 128 kbps
- **Subtitle**: Burned-in (if enabled), white text with black outline

### File Naming
```text
clips/
├── clip_1.mp4
├── clip_2.mp4
└── clip_3.mp4
```

---

## 📐 Visualization

### Mode 1: Default (Center Crop)
Best for Vlogs, Podcasts, or general videos.
**Output Resolution:** 720 x 1280 px.

```text
[ Original 16:9 ]             [ Output 9:16 ]
┌───────────────────────┐     ┌───────────┐
│           │           │     │           │
│           │           │     │           │
│        CONTENT        │ ──► │  CONTENT  │ ↕ 1280px
│           │           │     │           │
│           │           │     │           │
└───────────────────────┘     └───────────┘
        (Center)
```

### Mode 2: Split Left (Gaming/Reaction)
Best for streamers with **Facecam on the Bottom-Left**.
**Output Resolution:** 720 x 1280 px.

```text
[ Original 16:9 ]             [ Output 9:16 ]
┌───────────────────────┐     ┌───────────┐
│           │           │     │  CONTENT  │ ↕ 960px
│        CONTENT        │ ──► │ (Center)  │
│           │           │     ├───────────┤
├───┐                   │     │  FACECAM  │ ↕ 320px
│CAM│                   │     │ (Bot-Left)│
└───┴───────────────────┘     └───────────┘
```

### Mode 3: Split Right (Gaming/Reaction)
Best for streamers with **Facecam on the Bottom-Right**.
**Output Resolution:** 720 x 1280 px.

```text
[ Original 16:9 ]             [ Output 9:16 ]
┌───────────────────────┐     ┌───────────┐
│           │           │     │  CONTENT  │ ↕ 960px
│        CONTENT        │ ──► │ (Center)  │
│           │           │     ├───────────┤
│                   ┌───┤     │  FACECAM  │ ↕ 320px
│                   │CAM│     │(Bot-Right)│
└───────────────────┴───┘     └───────────┘
```

---

## ❓ Troubleshooting

### FFmpeg not found
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html), add `bin` folder to PATH.
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### No high-engagement segments found
- Video might not have "Most Replayed" data yet (needs views/engagement).
- Try lowering `MIN_SCORE` (e.g., from 0.40 to 0.30).
- Check if video URL is correct.

### Subtitle generation fails
- Ensure internet connection for first-time model download.
- Check available RAM (Whisper needs ~500MB-2GB depending on model).
- Try smaller model: set `WHISPER_MODEL = "tiny"` to override automatic selection.

---

## 💡 Tips & Best Practices

### For Gaming Content
- Use **Split Right** or **Split Left** mode (facecam in corner).
- Keep `PADDING = 10` for context before/after action.
- Use `small` or `base` model for accurate gaming terminology.

### For Tutorial/Vlog Content
- Use **Default** center crop mode.
- Increase `MAX_DURATION = 90` for longer explanations.
- Enable subtitles with `tiny` model for fast processing.

### Subtitle Customization
You can customize the subtitle appearance by editing the `force_style` parameter in `yt_heatmap_clipper/rendering.py`:

```python
# Current default style (white text, black outline):
FontName=Arial,FontSize=12,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=100

# To use larger text:
FontSize=24,Outline=3

# To position higher (avoiding facecam):
MarginV=400

# To change color (e.g., yellow):
PrimaryColour=&H00FFFF
```

---

## 🤝 Contribution

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

---

## 📜 License
MIT License

---

## 🙏 Credits
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - YouTube video downloader
- **[FFmpeg](https://ffmpeg.org/)** - Video processing
- **[Faster-Whisper](https://github.com/guillaumekln/faster-whisper)** - AI transcription
- **[OpenAI Whisper](https://github.com/openai/whisper)** - Speech recognition model

---

## 🌟 Support

If you find this tool useful, please **⭐ star this repository!**

For issues and questions, please open an issue on GitHub.
