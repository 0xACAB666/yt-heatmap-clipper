# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-script CLI tool (`run.py`) that turns a YouTube video into vertical short-form clips: it reads YouTube's "Most Replayed" heatmap data (no API key needed), finds the highest-engagement moments, downloads the video once at a user-chosen (or highest-available) resolution, crops the selected moments to 9:16, and optionally burns in AI-generated subtitles.

## Commands

```bash
# Verify environment (FFmpeg + Deno + Python deps) before running
python check_setup.py

# Run the tool (interactive prompts: crop mode, subtitle on/off, YouTube URL)
python run.py

# Install dependencies
pip install -r requirements.txt          # requests, yt-dlp (base)
pip install faster-whisper               # add for AI subtitles
pip install mediapipe opencv-python      # add for the speaker-follow crop mode

# Deno (https://deno.land) must also be on PATH — required by yt-dlp to solve
# YouTube's JS challenge; see cek_dependensi/YTDLP_REMOTE_COMPONENTS below for why.
```

There is no build step, test suite, or linter configured in this repo.

## Architecture

Everything lives in `run.py` as a linear pipeline, run top-to-bottom from `main()`:

1. **`extract_video_id`** — parses a YouTube URL (watch, youtu.be, or /shorts/) into a video ID.
2. **`ambil_most_replayed`** — fetches the video's watch page HTML and regex-extracts the `markers` JSON blob embedded in it (this is YouTube's internal heatmap data, not a public API). Filters segments by `MIN_SCORE` and sorts by engagement score descending. This scraping approach is brittle to YouTube markup changes — if it starts returning `[]` unexpectedly, the regex in this function is the first place to check.
3. **`get_duration`** — shells out to `yt-dlp --get-duration` to get total video length, used to clamp clip end times.
4. **`cek_dependensi`** — self-updates `yt-dlp` via pip on every run, checks/installs `faster-whisper` if subtitles are enabled, checks/installs `mediapipe`+`opencv-python` if the `speaker_follow` crop mode is selected (non-fatal if that install fails — `proses_satu_clip` falls back to the default center crop per-clip), and hard-exits if FFmpeg or Deno isn't on PATH (Deno runs yt-dlp's JS challenge solver — see `YTDLP_REMOTE_COMPONENTS` below).
5. **`list_available_heights` / `prompt_resolution`** — once the video link is entered, queries `yt-dlp -F` (no player-client restriction) for the video-track heights actually available, and lets the user pick one (Enter defaults to the highest) once per run. Falls back to a `1080` cap with a warning if discovery fails, or skips the prompt if only one height is offered.
6. **`download_full_video`** — downloads the *entire* video once, via `yt-dlp`'s ordinary sequential downloader (`bestvideo[height<=N]+bestaudio`, merged to a single mp4), capped at the resolution chosen above. This intentionally does **not** use network-level time-range trimming (`--downloader ffmpeg` with `-ss`/`-to`, or yt-dlp's own `--download-sections`) — testing showed that hangs indefinitely on DASH formats (the only way most videos serve >360p) regardless of which player client is used; only a full, sequential download is reliable. A failed download aborts the run before any clip processing starts (see `main`).
7. **`proses_satu_clip`** — the per-clip worker, called once per heatmap segment (up to `MAX_CLIPS`). Trims and crops the clip's padded time range directly out of the already-downloaded full video in one local FFmpeg pass (`-ss`/`-to` against the local file, then the crop filter) — fast and reliable regardless of source resolution/codec, since no network access is involved:
   - Crops via FFmpeg according to `crop_mode`:
     - `default`: simple center crop to 720x1280.
     - `split_left` / `split_right`: uses `filter_complex` to `split` the scaled frame into two streams, crops one for the top (center content, `TOP_HEIGHT`) and one for the bottom (facecam corner, `BOTTOM_HEIGHT`), then `vstack`s them — for streamer/gaming content where a facecam occupies a corner. `TOP_HEIGHT + BOTTOM_HEIGHT` must equal 1280.
     - `speaker_follow`: for multi-person, single-camera content (podcast/interview style) where no camera operator is choosing who to frame. `detect_speaker_turns` samples frames (`FACE_SAMPLE_INTERVAL_SEC`) via `mediapipe` FaceMesh, tracks up to `MAX_TRACKED_FACES` faces frame-to-frame by nearest normalized position, computes a mouth-aspect-ratio series per face track, and correlates it against the clip's audio RMS energy (extracted via a `ffmpeg`→WAV pipe) over `SPEAKER_CORRELATION_WINDOW_SEC` windows — the best-correlating face per window is that window's active speaker. Consecutive same-speaker windows merge into turns; turns shorter than `MIN_SPEAKER_TURN_SEC` get absorbed into a neighboring turn so the crop doesn't flicker. `build_speaker_follow_expr` turns the resulting turn list into a single piecewise ffmpeg `crop` `x` expression (`if(lt(t,...),...)` chain) — one ffmpeg pass, discrete holds rather than a smooth pan, jumping to the next speaker's horizontal position at each turn boundary. If detection can't find at least 2 distinguishable speaking faces (too few faces, `mediapipe`/`opencv` unavailable, any error), `detect_speaker_turns` returns `None` and `proses_satu_clip` silently falls back to `default` center crop for that clip with a printed notice — never aborts the run. See `specs/008-speaker-follow-crop.md`.
     - If `use_subtitle`: transcribes the cropped clip with `faster-whisper` (`generate_subtitle`), writes an SRT, and burns it in via FFmpeg's `subtitles` filter (path must be escaped for FFmpeg — see the backslash/colon handling before use). Falls back to the unsubtitled clip if transcription fails. Each segment is logged live as it's transcribed (`segments` from `model.transcribe()` is a lazy generator, so the SRT-writing loop doubles as live progress). `generate_subtitle` returns the transcribed caption texts (not just a success flag); on success with non-empty captions, `proses_satu_clip` also writes them to `clip_{i}.txt` (one caption per line, no timestamps) alongside `clip_{i}.mp4` — skipped entirely if transcription failed or subtitles are off.
   - Crop/subtitle-burn subprocesses all run through `stream_subprocess`, which streams their combined stdout+stderr live via `tqdm.write()` as it arrives (not just on failure) — this is the default, always-on verbosity, not a flag. It relies on Python's universal-newline text mode splitting `readline()` on a bare `\r` (not just `\n`), since ffmpeg's `-stats` progress line is `\r`-terminated.
   - Per-clip temp files (`temp_cropped_{i}.mp4`, `temp_{i}.srt`) are cleaned up on both success and failure paths; the shared full-video temp file is cleaned up once in `main` after all clips are processed.
8. **`select_segments`** — if more than one segment qualifies, lists them **chronologically** (start time ascending, not score) with timeframe (`MM:SS` and raw seconds) and score, then lets the user pick which ones to clip by index/range (`1,3` or `2-4`), re-prompting on invalid input and capping the selection at `MAX_CLIPS`. This exists because the heatmap tends to over-rate a video's opening seconds (most viewers start playback at 0:00), so blindly taking the top-scoring segments can be misleading — chronological listing makes that bias visible so the user can pick around it. With exactly one qualifying segment, it's returned directly with no prompt. `parse_selection` and `format_seconds_display` are its helpers.
9. **`main`** — interactive entrypoint: prompts for crop mode, subtitle preference, resolution (via `prompt_resolution`), and (after the heatmap is fetched) segment selection via `select_segments`; downloads the full video once via `download_full_video`, then drives the loop over exactly the selected segments — in chronological order — calling `proses_satu_clip` for each. Unlike the old top-N approach, a failed clip is **not** backfilled with a different (unselected) segment; the run reports however many of the selected segments actually succeeded. The loop is wrapped in a `tqdm` progress bar (`Generating clips: n/N`) that advances once per successful clip; see spec below for why `tqdm.write()` is used for logging instead of `print()` inside `proses_satu_clip`/`generate_subtitle` while the bar is active.

Tunable constants are declared at the top of `run.py` (`OUTPUT_DIR`, `MAX_DURATION`, `MIN_SCORE`, `MAX_CLIPS`, `PADDING`, `TOP_HEIGHT`/`BOTTOM_HEIGHT`, `WHISPER_MODEL`, `FACE_SAMPLE_INTERVAL_SEC`, `MAX_TRACKED_FACES`, `MIN_SPEAKER_TURN_SEC`, `SPEAKER_CORRELATION_WINDOW_SEC`, etc.) rather than via config file or CLI flags — edit these directly to change default behavior.

## Spec-driven development

Feature work in this repo follows a specs-first process: each backlog item gets a short spec in `specs/` (problem, goals/non-goals, requirements, acceptance criteria) before implementation. See `specs/001-progress-bar.md`, `specs/002-user-defined-clip-count.md`, `specs/003-manual-segment-selection.md`, `specs/004-verbose-clip-progress.md`, `specs/005-resolution-selection.md`, `specs/006-full-video-download-for-resolution.md`, `specs/007-caption-text-export.md`, and `specs/008-speaker-follow-crop.md` for the format to follow on future features.

Output clips are written to `clips/clip_{n}.mp4`.