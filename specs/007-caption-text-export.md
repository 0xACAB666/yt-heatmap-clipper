# Spec 007: Plain-Text Caption Export Alongside Each Clip

## Status
Draft → Implemented on `feature/caption-text-export`

## Problem
When subtitles are enabled, `generate_subtitle` writes an SRT file used only to burn captions into the clip, then deletes it (`os.remove(subtitle_file)` in `proses_satu_clip`). The transcribed text itself — useful on its own for writing video descriptions, social captions, or repurposing the transcript elsewhere — isn't preserved anywhere once the run finishes.

## Goals
- For every clip that gets subtitles burned in, also save the caption text (no timestamps) to a `.txt` file next to the clip, sharing the same base name (`clip_1.mp4` → `clip_1.txt`).
- Keep the text easy to reuse: one caption segment per line, in chronological order — same segmentation as the SRT, just without index numbers or timecodes.

## Non-Goals
- Changing the SRT generation/burn-in logic itself, or keeping the `.srt` file around (it's still a transient temp file, deleted as today).
- Producing a caption file when there's no caption content: subtitles disabled for the run, or transcription failed for that clip. No `clip_N.txt` is written in either case — not even an empty one.
- Any new user-facing prompt/flag. This is unconditional whenever subtitles are actually burned into a clip, consistent with subtitle burn-in itself being controlled by the existing subtitle on/off prompt.
- Merging captions across clips into one combined file, or any format other than plain `.txt` (e.g. `.vtt`, `.json`).

## Requirements
1. In `proses_satu_clip`, after `generate_subtitle` succeeds and before the SRT file is deleted, write a plain-text caption file: `os.path.join(OUTPUT_DIR, f"clip_{index}.txt")` — matching `output_file`'s naming exactly, just with a `.txt` extension instead of `.mp4`.
2. Content: one line per subtitle segment's text (the same `segment.text.strip()` already used when writing the SRT), in the same order, with no index numbers, timestamps, or blank separator lines. A trailing newline after the last line is fine.
3. This only happens on the success path of subtitle generation. If `generate_subtitle` returns `False` (transcription failed) or `use_subtitle` is `False` for the run, no `clip_N.txt` is written at all.
4. The caption text file is written to disk as a real output artifact (like `clip_N.mp4`) — it is not a temp file and must not be deleted by the existing temp-file cleanup logic (which only ever targeted `cropped_file`/`subtitle_file`, so this doesn't change that cleanup).
5. Simplest implementation path: capture the list of transcribed segment texts while `generate_subtitle` iterates them (it already loops over `segments` to write the SRT), and reuse that same list to write the `.txt` file in `proses_satu_clip` — avoids re-parsing the SRT file back apart to strip timestamps.

## Acceptance Criteria
- Running the tool with subtitles enabled produces, for each successfully subtitled clip, both `clips/clip_N.mp4` and `clips/clip_N.txt`, with matching `N`.
- `clips/clip_N.txt` contains only caption text, one segment per line, no timestamps or index numbers.
- Running with subtitles disabled produces no `.txt` files at all.
- A clip where transcription fails (falls back to the unsubtitled clip) produces no `clip_N.txt` for that clip, while other clips in the same run that succeeded still get theirs.