# Spec 001: Progress Bar for Clip Generation

## Status
Draft → Implemented on `feature/progress-bar-and-clip-count`

## Problem
`run.py` currently only prints a line per step (`[Clip N] Processing segment...`, `Cropping video...`, etc.). For long runs (many clips, subtitle transcription enabled) the user has no sense of overall progress — how many clips are left, or whether the process has stalled.

## Goals
- Show a live progress bar tracking how many of the requested clips have been successfully generated, out of the target count.
- Keep existing per-step log lines (download/crop/subtitle/burn status, errors) visible without corrupting the progress bar's rendering.

## Non-Goals
- Fine-grained progress *within* a single clip (e.g. FFmpeg's own `time=` encode progress, or yt-dlp's byte-download progress). Out of scope for this iteration — the bar advances at clip granularity, not sub-step granularity.
- A GUI/web progress indicator. This is a CLI-only change.

## Requirements
1. Use `tqdm` for the progress bar (already a transitive dependency via `faster-whisper`/`huggingface-hub`; pin it directly in `requirements.txt` since the base install — without subtitles — must not depend on it transitively).
2. The bar's `total` equals the number of clips actually targeted this run (`min(requested_n, len(heatmap_data))` — see Spec 002).
3. The bar advances by 1 each time `proses_satu_clip` returns `True` (a clip was successfully produced). Failed attempts do not advance it, but do not stop the run either — the loop keeps trying subsequent heatmap segments as it does today.
4. All `print()` calls that can fire while the bar is active (inside `proses_satu_clip` and `generate_subtitle`) are replaced with `tqdm.write()`, which prints above the bar instead of corrupting its line.
5. Prints that only happen before the bar starts or after it closes (crop-mode/subtitle prompts, dependency checks, heatmap fetch, final summary) are left as plain `print()`.

## Acceptance Criteria
- Running `python run.py` against a video with several qualifying heatmap segments shows a single-line progress bar (`Generating clips: X%|████ | n/N [elapsed<remaining]`) that updates as each clip completes.
- Step-by-step log lines (e.g. "Cropping video...", "Clip successfully generated.", error messages) still appear, printed above the bar, not interleaved/garbled with it.
- A clip failure does not crash the bar or the run; the bar simply doesn't advance for that attempt.