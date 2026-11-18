# YouTube Heatmap & Custom Clip Maker

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Required-green.svg](https://ffmpeg.org/)
[![yt-dlp](https://img.shields.io/badge/Downloader-yt--dlp-orange.svg)](https://github.com/yt-dlp/yt-dlp)

Download selected sections from YouTube videos using exact timestamps, or automatically find engaging moments using YouTube's **Most Replayed** heatmap.

There are two workflows:

- **Custom clipping:** paste a YouTube URL and specify the exact start and end times.
- **Automatic heatmap clipping:** detect high-engagement moments and create vertical clips using the original workflow.

---

## Download the project

Choose either method.

### Option 1 — Download ZIP (easiest on Windows)

1. Open the [latest source ZIP](https://github.com/hellocloudwebdev/yt-heatmap-clipper/archive/refs/heads/main.zip).
2. Extract the downloaded ZIP file.
3. Open the extracted `yt-heatmap-clipper-main` folder.
4. Open PowerShell or Command Prompt in that folder.

### Option 2 — Clone with Git

```bash
git clone https://github.com/hellocloudwebdev/yt-heatmap-clipper.git
cd yt-heatmap-clipper
```

---

## Requirements

- Python **3.10 or newer**
- FFmpeg installed and available on your system PATH
- An internet connection

### Install Python dependencies

Run this from the project folder:

```bash
python -m pip install -r requirements.txt
```

On Windows, you can use `py` instead of `python` if that is how Python is installed:

```powershell
py -m pip install -r requirements.txt
```

### Install FFmpeg

FFmpeg is required to process and export video clips. Installing the Python packages alone is not enough.

- **Windows:** download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html), extract it, and add its `bin` folder (for example, `C:\\ffmpeg\\bin`) to your PATH. Restart your terminal afterwards.
- **macOS:** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt update && sudo apt install ffmpeg`

Verify that both commands work:

```bash
python --version
ffmpeg -version
```

If your terminal says that `ffmpeg` is not recognized or not found, check the PATH setup and restart the terminal.

---

## Start the clipper

From the project folder, run:

```bash
python launcher.py
```

On Windows, this also works:

```powershell
py launcher.py
```

The launcher displays two options:

```text
=== YouTube Clipper ===
1. Automatic heatmap clipping (original workflow)
2. Custom time-range clipping
Choose mode (1-2):
```

Choose **2** for manual clipping or **1** for automatic heatmap clipping.

---

## Custom clipping — choose your own timestamps

Use this mode when you already know which part of a video you want to save.

1. Start the launcher with `python launcher.py`.
2. Enter `2` to select **Custom time-range clipping**.
3. Paste a YouTube video URL.
4. Enter the start time.
5. Enter the end time. The end time must be later than the start time.
6. The selected section is downloaded and saved as an MP4.

### Example

To save the video from **1 minute to 1 minute 40 seconds**:

```text
=== YouTube Clipper ===
1. Automatic heatmap clipping (original workflow)
2. Custom time-range clipping
Choose mode (1-2): 2

YouTube URL: https://www.youtube.com/watch?v=VIDEO_ID
Start time (e.g. 01:00 or 00:01:00): 01:00
End time (e.g. 01:40 or 00:01:40): 01:40

Requested range: 60.000s → 100.000s (40.000s)
Downloading selected section with yt-dlp + FFmpeg...

Clip saved: clips/custom_VIDEO_ID_00-01-00_to_00-01-40.mp4
```

Replace the example URL with the video you want to clip.

### Supported timestamp formats

| Format | Example | Meaning |
| --- | --- | --- |
| Seconds | `75` | 1 minute 15 seconds |
| Minutes:Seconds | `01:15` | 1 minute 15 seconds |
| Hours:Minutes:Seconds | `00:01:15` | 1 minute 15 seconds |
| Fractional seconds | `01:15.5` | 1 minute 15.5 seconds |

The start and end can use different supported formats. For example, start at `60` and end at `01:40`.

Supported URL types include standard YouTube watch links, `youtu.be` links, Shorts, embeds and live URLs. The video must be accessible to yt-dlp; private, age-restricted or otherwise restricted videos may not be downloadable.

### Where are my clips saved?

Custom clips are saved in the project's `clips/` folder. The output filename includes the video ID and selected time range. If a file with that name already exists, a numbered suffix is added rather than overwriting it.

### Custom mode notes

- The custom mode keeps the original video's aspect ratio; it does not automatically crop the result to vertical 9:16.
- It does not generate or burn subtitles.
- It uses yt-dlp's FFmpeg section download and keyframe handling. FFmpeg may fetch nearby media data to make the cut; the resulting cut boundaries can vary slightly depending on the source video's encoding.
- If a download fails, check that the video is accessible, the timestamps are within the video's duration, and FFmpeg is installed correctly.

---

## Automatic heatmap clipping

Choose **1** in the launcher to run the original `run.py` workflow.

This mode reads YouTube's Most Replayed heatmap data and selects high-engagement segments. It can then download, crop and optionally subtitle the selected moments.

The original workflow supports:

- Automatic detection of high-engagement moments from heatmap data
- Configurable clip duration, engagement threshold and padding
- Three vertical crop layouts: center, split-left and split-right
- Optional AI subtitles using Faster-Whisper
- MP4 output in the `clips/` folder

The original script can also be started directly:

```bash
python run.py
```

The automatic workflow has additional processing requirements for video cropping and optional transcription. If you enable AI subtitles, Faster-Whisper and its speech-recognition model may be installed/downloaded on first use. Model downloads can require substantial disk space and memory.

---

## Output

Both workflows save generated clips in:

```text
yt-heatmap-clipper/
└── clips/
    ├── custom_VIDEO_ID_00-01-00_to_00-01-40.mp4
    ├── clip_1.mp4
    └── clip_2.mp4
```

Custom clipping preserves the source aspect ratio. Automatic heatmap clipping creates vertical-ready output according to the selected crop mode.

---

## Troubleshooting

### `python` or `py` is not recognized

Install Python from [python.org](https://www.python.org/downloads/) and enable the option to add Python to PATH during installation. Reopen your terminal after installation.

### FFmpeg not found

Install FFmpeg and add its `bin` directory to PATH. Restart the terminal and run `ffmpeg -version` to verify it.

### The custom clip does not download

- Check that the URL opens and the video is publicly accessible.
- Confirm that the end timestamp is later than the start timestamp.
- Make sure the timestamps are within the video's duration.
- Update yt-dlp: `python -m pip install -U yt-dlp`.
- Confirm FFmpeg works with `ffmpeg -version`.

### No heatmap segments found in automatic mode

Some videos do not have Most Replayed heatmap data. Try another video or adjust `MIN_SCORE` in `run.py`.

### Automatic subtitles fail

Check your internet connection, free disk space and available RAM. A smaller Whisper model (such as `tiny`) uses fewer resources than larger models.

---

## Configuration

The automatic heatmap workflow can be configured near the top of `run.py`:

```python
MAX_DURATION = 60    # Maximum duration for each detected segment
MIN_SCORE = 0.40     # Minimum heatmap intensity score
MAX_CLIPS = 10       # Maximum number of clips to generate
PADDING = 10         # Extra seconds before and after a detected segment
WHISPER_MODEL = "small"
```

These settings apply to the automatic heatmap workflow. Custom clipping uses the start and end times entered in the launcher.

---

## Important

Only download and use videos that you have permission to download and edit. You are responsible for complying with YouTube's terms, copyright law and any rights applicable to the source content.

## Contributing

Bug reports, feature suggestions and pull requests are welcome. Please open an issue on this repository for questions or problems.

## License

MIT License.
