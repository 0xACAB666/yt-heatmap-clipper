# Custom time-range clipping

The repository now includes an optional launcher with two modes:

1. **Automatic heatmap clipping** — starts the original `run.py` workflow unchanged.
2. **Custom time-range clipping** — paste a YouTube URL and enter exact start/end timestamps.

## Run

Install the repository requirements and ensure FFmpeg is installed and available on PATH:

```bash
pip install -r requirements.txt
python launcher.py
```

Choose option `2`, then enter for example:

```text
YouTube URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Start time: 01:00
End time: 01:40
```

The resulting MP4 is saved in `clips/`. Timestamps accept seconds, `MM:SS`, or `HH:MM:SS` (fractional seconds are accepted). The custom mode preserves the source aspect ratio and does not apply the automatic mode's vertical crop or subtitles.

The downloader uses yt-dlp's FFmpeg section download (`--download-sections`) and `--force-keyframes-at-cuts` for accurate cut boundaries. FFmpeg may need to fetch nearby media data to seek correctly; it does not intentionally download the entire video.

## Tests

```bash
python -m unittest discover -s tests -v
```
