# Spec 004: Verbose Live Progress Under the Progress Bar

## Status
Draft → Implemented on `feature/verbose-clip-progress`

## Problem
Spec 001 added a `tqdm` progress bar tracking clips completed, but explicitly scoped out fine-grained progress *within* a single clip: `proses_satu_clip` currently only prints coarse step markers ("Cropping video...", "Clip successfully generated.") while the actual `yt-dlp` download and `ffmpeg` crop/subtitle-burn subprocesses run silently (`--quiet`/`-loglevel error`, output only surfaced on failure). For anything but the shortest clip, the user has no visibility into what's actually happening or whether it's stuck — which matters more now that the download step (Spec/fix for SABR-only clients) involves multiple extraction sub-steps (client selection, JS challenge solving) that can each take a moment.

## Goals
- By default (no flag needed), stream what each subprocess (`yt-dlp` download, `ffmpeg` crop, `ffmpeg` subtitle burn) is actually doing live, as it happens — not just before/after markers.
- Keep this live output visually clean under the `tqdm` bar: printed above it via `tqdm.write()`, matching Spec 001's existing rule, never corrupting/interleaving with the bar's own line.
- Show live per-segment output during subtitle transcription too, since `faster-whisper`'s `transcribe()` already yields segments lazily as they're produced.

## Non-Goals
- A `--quiet`/`--verbose` CLI flag to toggle this off. The user asked for verbose *by default*; a toggle can be added later if it turns out to be too noisy for some use case, but isn't in scope now.
- Structured/machine-readable progress output (e.g. JSON), or updating the `tqdm` bar's own postfix/description with sub-progress. This is plain human-readable log lines interleaved above the bar, nothing fancier.
- Changing what `yt-dlp`/`ffmpeg` actually do (formats, codecs, filters) — this is purely about surfacing their existing output, not altering behavior. Unrelated to the SABR-client-selection fix beyond sharing the same `cmd_download` list.

## Requirements
1. Add a `stream_subprocess(cmd)` helper that runs `cmd` via `subprocess.Popen` with merged `stdout`/`stderr`, reads output as it arrives (line-buffered `text=True`, which Python's universal-newline handling splits on bare `\r` as well as `\n` — needed since `ffmpeg -stats` progress updates are `\r`-terminated, not `\n`-terminated), and forwards each non-empty line through `tqdm.write()` prefixed for readability. Raises `subprocess.CalledProcessError` on non-zero exit (without attached output — it was already shown live, so failure handling no longer needs to re-print `e.stderr`/`e.stdout`).
2. Replace the `subprocess.run(..., stdout=PIPE, stderr=PIPE)` calls in `proses_satu_clip` (download, crop, subtitle burn) with `stream_subprocess`.
3. Download step (`cmd_download`): drop `--quiet` and `--no-warnings` from the `yt-dlp` invocation so its own status lines (webpage/player extraction, JS challenge solving, client fallback warnings, format selection) are visible; add `-stats` to the wrapped `ffmpeg_i` downloader-args (alongside the existing `-loglevel error`) so transfer progress (`time=`/`speed=`) streams live too.
4. Crop and subtitle-burn steps: add `-stats` to each `ffmpeg` command (keeping `-loglevel error` for the rest, since `-stats`'s progress line isn't gated by `-loglevel`) so encode progress streams live.
5. `generate_subtitle`: add a `tqdm.write()` call inside the existing segment-enumeration loop, showing each segment's timestamp + text as it's transcribed (no new subprocess involved — `model.transcribe()`'s returned `segments` is already a lazy generator, this just surfaces what's already happening instead of only writing to the SRT file).
6. Error paths (`except subprocess.CalledProcessError` / generic `Exception` in `proses_satu_clip`) simplify to no longer reference `e.stderr`/`e.stdout` for the subprocess calls now using `stream_subprocess` — the failing command's output was already visible live above the bar before the exception propagated.

## Acceptance Criteria
- Running `python run.py` against a video shows live `yt-dlp` extraction/download status lines and periodic transfer stats, then live `ffmpeg` crop progress (`frame=`/`time=`/`speed=`), then (if subtitles enabled) live per-segment transcription lines and live subtitle-burn progress — all printed above the `tqdm` bar without corrupting its line, exactly matching Spec 001's existing interleaving rule.
- No flag or prompt is needed to see this — it's the default, always-on behavior.
- A failed download/crop/subtitle-burn still shows its live output (now visible as it streamed) and the run continues to the next segment / reports failure exactly as it does today — no change to success/failure semantics, only to what's visible while it happens.
