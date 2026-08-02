# Spec 005: User-Selectable Download Resolution

## Status
Draft → Implemented on `feature/resolution-selection`

## Problem
`proses_satu_clip` hardcodes the download format string to `bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best`. In practice this rarely reaches 1080p: the SABR-avoidance fix (`YTDLP_CLIENT_ARGS`) restricts extraction to player clients (`web`, `web_safari`, `tv_simply`, `mweb`) that serve formats over plain HTTP instead of YouTube's SABR streaming protocol, and per CLAUDE.md that often caps the *actually available* progressive/DASH formats around 360p for a given video. The user has no visibility into what resolutions are really available for the video they're clipping, and no way to deliberately pick a lower one (e.g. for faster downloads/smaller files) or confirm they're getting the highest one that's actually on offer.

## Goals
- Before downloading any clips, show the user which resolutions are genuinely available for *this* video, using the same SABR-safe client restriction the rest of the script already relies on (`YTDLP_CLIENT_ARGS`) — never a generic/assumed list.
- Default to the highest available resolution with a single Enter keypress, consistent with how a sensible default should require no extra effort.
- Let the user pick a lower resolution instead, if they want.
- Ask once per run (alongside the existing crop-mode/subtitle prompts), not once per clip — the same resolution choice applies to every clip generated in the run.

## Non-Goals
- Loosening `YTDLP_CLIENT_ARGS` to probe additional player clients for higher resolutions. That would reintroduce the SABR hang/silent-audio failure mode the prior bugfix eliminated; this feature only surfaces and lets the user choose among what the existing safe client list already serves.
- A `--resolution` CLI flag — stays consistent with the script's existing interactive-prompt style (crop mode, subtitle on/off).
- Per-clip resolution overrides. One choice governs the whole run.
- Changing crop dimensions (`TOP_HEIGHT`/`BOTTOM_HEIGHT`, the 720x1280 output) — those apply after download/crop regardless of source resolution.

## Requirements
1. Add `list_available_heights(video_id)`: runs `yt-dlp -F` (list-formats) with the same `YTDLP_CLIENT_ARGS` used for the real download, against `https://youtu.be/{video_id}`, and parses the resulting format table for distinct video-track heights (ignore audio-only rows). Returns a sorted (descending) list of unique integer heights actually offered by the safe client list for this video.
2. If discovery fails (network error, empty/unparseable output), skip the prompt entirely, print a one-line warning, and fall back to today's behavior (`height<=1080` cap, whatever the client list actually serves) — never blocks the run over a formats-listing hiccup.
3. If discovery succeeds, prompt once per run. Discovery requires `video_id`, so this prompt happens after the link is entered and `video_id` is extracted, before heatmap fetching/segment selection. (Ordering: crop mode → subtitle choice → link input → resolution prompt → heatmap fetch → segment selection → processing loop.)
4. Resolution prompt lists discovered heights as a numbered menu, highest first, e.g.:
   ```
   === Resolution ===
   Available for this video (via SABR-safe clients):
   1. 1080p (default)
   2. 720p
   3. 480p
   4. 360p
   Select resolution [Enter for default]:
   ```
   Pressing Enter with no input selects option 1 (the highest, i.e. the default). Entering a valid number selects that height. Invalid input (non-numeric, out of range) re-prompts, matching the existing crop-mode validation loop style.
5. The chosen height (`target_height`) is threaded into `proses_satu_clip`'s format string, replacing the hardcoded `1080`: `bestvideo[height<={target_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={target_height}][ext=mp4]/best[height<={target_height}]` — the fallback tiers stay capped at the chosen height too, so a fallback never silently exceeds what the user picked.
6. If only one height is discovered, skip the prompt (nothing to choose between) and use it directly, printing which resolution will be used — mirroring how `select_segments` skips its prompt for a single qualifying segment.

## Acceptance Criteria
- Running `python run.py` against a video shows a resolution menu (or a single-resolution notice) after the video link is entered, before heatmap segments are listed.
- Pressing Enter at the resolution prompt selects the highest discovered resolution with no further input needed.
- Choosing a lower listed resolution (e.g. `3` for 480p) results in downloaded clips capped at that height.
- If format discovery fails for any reason, the run proceeds without prompting, using the prior default behavior (`height<=1080`), with a printed warning explaining why no choice was offered.
- The resolution choice is asked exactly once per run and applies identically to every clip processed in that run.