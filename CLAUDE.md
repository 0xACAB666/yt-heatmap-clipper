# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-script CLI tool (`run.py`) that turns a YouTube video into vertical short-form clips: it reads YouTube's "Most Replayed" heatmap data (no API key needed), finds the highest-engagement moments, downloads only those time ranges, crops them to 9:16, and optionally burns in AI-generated subtitles.

## Commands

```bash
# Verify environment (FFmpeg + Python deps) before running
python check_setup.py

# Run the tool (interactive prompts: crop mode, subtitle on/off, YouTube URL)
python run.py

# Install dependencies
pip install -r requirements.txt          # requests, yt-dlp (base)
pip install faster-whisper               # add for AI subtitles
```

There is no build step, test suite, or linter configured in this repo.

## Architecture

Everything lives in `run.py` as a linear pipeline, run top-to-bottom from `main()`:

1. **`extract_video_id`** — parses a YouTube URL (watch, youtu.be, or /shorts/) into a video ID.
2. **`ambil_most_replayed`** — fetches the video's watch page HTML and regex-extracts the `markers` JSON blob embedded in it (this is YouTube's internal heatmap data, not a public API). Filters segments by `MIN_SCORE` and sorts by engagement score descending. This scraping approach is brittle to YouTube markup changes — if it starts returning `[]` unexpectedly, the regex in this function is the first place to check.
3. **`get_duration`** — shells out to `yt-dlp --get-duration` to get total video length, used to clamp clip end times.
4. **`cek_dependensi`** — self-updates `yt-dlp` via pip on every run, checks/installs `faster-whisper` if subtitles are enabled, and hard-exits if FFmpeg isn't on PATH.
5. **`proses_satu_clip`** — the per-clip worker, called once per heatmap segment (up to `MAX_CLIPS`):
   - Downloads *only* the padded time range via `yt-dlp` using `ffmpeg`-based partial download (`--downloader ffmpeg` with `-ss`/`-to` args), not the full video.
   - Crops via FFmpeg according to `crop_mode`:
     - `default`: simple center crop to 720x1280.
     - `split_left` / `split_right`: uses `filter_complex` to `split` the scaled frame into two streams, crops one for the top (center content, `TOP_HEIGHT`) and one for the bottom (facecam corner, `BOTTOM_HEIGHT`), then `vstack`s them — for streamer/gaming content where a facecam occupies a corner. `TOP_HEIGHT + BOTTOM_HEIGHT` must equal 1280.
     - If `use_subtitle`: transcribes the cropped clip with `faster-whisper` (`generate_subtitle`), writes an SRT, and burns it in via FFmpeg's `subtitles` filter (path must be escaped for FFmpeg — see the backslash/colon handling before use). Falls back to the unsubtitled clip if transcription fails.
   - All temp files (`temp_{i}.mp4`, `temp_cropped_{i}.mp4`, `temp_{i}.srt`) are cleaned up on both success and failure paths.
6. **`select_segments`** — if more than one segment qualifies, lists them **chronologically** (start time ascending, not score) with timeframe (`MM:SS` and raw seconds) and score, then lets the user pick which ones to clip by index/range (`1,3` or `2-4`), re-prompting on invalid input and capping the selection at `MAX_CLIPS`. This exists because the heatmap tends to over-rate a video's opening seconds (most viewers start playback at 0:00), so blindly taking the top-scoring segments can be misleading — chronological listing makes that bias visible so the user can pick around it. With exactly one qualifying segment, it's returned directly with no prompt. `parse_selection` and `format_seconds_display` are its helpers.
7. **`main`** — interactive entrypoint: prompts for crop mode, subtitle preference, and (after the heatmap is fetched) segment selection via `select_segments`, then drives the loop over exactly the selected segments — in chronological order — calling `proses_satu_clip` for each. Unlike the old top-N approach, a failed clip is **not** backfilled with a different (unselected) segment; the run reports however many of the selected segments actually succeeded. The loop is wrapped in a `tqdm` progress bar (`Generating clips: n/N`) that advances once per successful clip; see spec below for why `tqdm.write()` is used for logging instead of `print()` inside `proses_satu_clip`/`generate_subtitle` while the bar is active.

Tunable constants are declared at the top of `run.py` (`OUTPUT_DIR`, `MAX_DURATION`, `MIN_SCORE`, `MAX_CLIPS`, `PADDING`, `TOP_HEIGHT`/`BOTTOM_HEIGHT`, `WHISPER_MODEL`, etc.) rather than via config file or CLI flags — edit these directly to change default behavior.

## Spec-driven development

Feature work in this repo follows a specs-first process: each backlog item gets a short spec in `specs/` (problem, goals/non-goals, requirements, acceptance criteria) before implementation. See `specs/001-progress-bar.md`, `specs/002-user-defined-clip-count.md`, and `specs/003-manual-segment-selection.md` for the format to follow on future features.

Output clips are written to `clips/clip_{n}.mp4`.