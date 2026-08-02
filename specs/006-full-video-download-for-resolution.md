# Spec 006: Download Full Video Once, Trim Clips Locally

## Status
Draft → Implemented on `feature/resolution-selection`

## Problem
Spec 005 added resolution selection, but for many videos it can't actually deliver anything above 360p. Root-cause testing (against a real video, `R1e0VCMMrD4`) showed:

- Under the SABR-safe client restriction (`YTDLP_CLIENT_ARGS`), some videos serve *no* muxed/progressive format above 360p at all — heights above that only exist as video-only DASH streams requiring a separate audio track merge.
- The hang the original SABR bugfix worked around isn't actually about *which player client* is used — it's that `ffmpeg`-driven network-level time-range trimming (`--downloader ffmpeg` with `-ss`/`-to` against the raw format URL, or yt-dlp's own `--download-sections`, which falls back to the same mechanism) hangs on DASH formats regardless of client. Only the legacy muxed progressive format tolerates it.
- A **full, sequential** download of the same DASH format (no time-range trimming at the network level) works fine and fast — confirmed on two different videos, including the user's (1080p60, 505MB, sustained double-digit MiB/s, no stall).

So the per-clip "download only the padded range via a network-level ffmpeg trim" approach (used since the original SABR bugfix) is what caps resolution, not player-client selection. Restricting client selection doesn't actually prevent hangs for the case that matters (DASH formats) — it just hides the problem by falling back to whatever muxed low-res format happens to still exist for a given video, which for many videos is only 360p.

## Goals
- Reliably support resolutions above 360p for videos that only expose them as DASH (video-only + audio-only) streams — i.e. most modern uploads.
- Keep the run reliable: no reintroducing indefinite hangs or silent-audio clips.
- Keep Spec 005's UX (resolution prompt once per run, defaulting to highest available) working, now backed by real availability.

## Non-Goals
- Any attempt to resurrect per-clip network-range trimming for DASH formats. Testing showed this doesn't work reliably regardless of client, so this spec replaces it rather than patching it further.
- Byte-range/partial-fetch optimization of the full download (e.g. only fetching the byte ranges covering selected clips). Out of scope — the full file is fetched once, in full, via yt-dlp's ordinary sequential downloader.
- Caching the full download across runs or clips of the same video processed at different times. Each run downloads fresh and cleans up after itself.
- Changing crop/subtitle logic, `MAX_CLIPS`, `PADDING`, or heatmap scoring — this only changes *how the source video reaches disk* and *how clip ranges are cut out of it*.

## Requirements
1. Add `download_full_video(video_id, target_height)`: runs a plain (no `--downloader ffmpeg`, no `-ss`/`-to`) `yt-dlp` download of `bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]` with `--merge-output-format mp4`, to a fixed temp path (`temp_full_video.mp4`). Streamed live via the existing `stream_subprocess` helper, consistent with Spec 004. Raises/returns failure clearly if the file doesn't end up on disk.
2. Drop the `--extractor-args youtube:player_client=...` client restriction from both `list_available_heights` and the new full-download command — it no longer serves its original purpose (avoiding network-range-trim hangs, which no longer happen since there's no network-range trim) and was actively hiding higher resolutions that are genuinely downloadable via a full sequential fetch. Keep `--remote-components ejs:github` (still needed for the Deno-based JS challenge solver regardless of client).
3. `list_available_heights` must reflect what's really downloadable via the new method — i.e. query formats without the client restriction, so a video like `R1e0VCMMrD4` correctly lists 1080p60 as available instead of reporting only 360p.
4. `main()` calls `download_full_video` once (after `target_height` is chosen, before the per-clip loop), and passes the resulting file path into `proses_satu_clip` for every selected segment — replacing each clip's own network download.
5. `proses_satu_clip` no longer downloads anything itself. It takes `full_video_path` and directly runs a single local `ffmpeg -ss {start} -to {end} -i {full_video_path} <existing crop filter> ...` invocation per clip — combining what used to be a network download + a separate local crop pass into one local trim+crop pass, since there's no longer a network fetch step to keep separate. Subtitle generation/burn behavior is unchanged.
6. If `download_full_video` fails (network error, disk full, no file produced), abort the run immediately with a clear message — no clips can be produced without the source file. This mirrors the existing "no heatmap data" early-exit style in `main()`.
7. The full video temp file is deleted after the clip-processing loop finishes, on both success and failure paths (matches the existing temp-file cleanup discipline for `temp_{i}.mp4`/`temp_cropped_{i}.mp4`/`temp_{i}.srt`).
8. Update the CLAUDE.md architecture description (`cek_dependensi`/`proses_satu_clip`/`YTDLP_CLIENT_ARGS` sections) to describe the new full-download-then-local-trim flow, replacing the now-inaccurate "capped at 360p" framing from the original SABR bugfix.

## Acceptance Criteria
- Running the tool against `R1e0VCMMrD4` (or any similar video with only DASH streams above 360p) offers resolutions above 360p in the Spec 005 prompt, and selecting one (or accepting the default highest) produces clips actually encoded at that height.
- The video is downloaded exactly once per run, regardless of how many clips are selected.
- A failed full-video download stops the run with a clear error, before attempting any clip processing, rather than partially processing clips against a missing/corrupt source.
- `temp_full_video.mp4` does not linger on disk after the run ends, whether it ended in success or failure.
- No regression to crop modes, subtitle burning, or segment selection — only the source of the video data and the trim mechanism change.