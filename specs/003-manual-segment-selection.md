# Spec 003: Manual Segment Selection From Heatmap List

## Status
Draft

## Problem
`ambil_most_replayed` sorts qualifying heatmap segments by `score` descending, and the run simply takes the top N of that order (Spec 002). In practice, YouTube's "Most Replayed" heatmap is skewed toward the very beginning of a video — most viewers start playback at 0:00, so the opening seconds often register as high (or the highest) engagement even when nothing noteworthy happens there. Auto-picking by score alone can silently hand the user a batch of clips dominated by the misleading intro instead of the video's actual highlights.

## Goals
- When more than one qualifying segment exists, show the user every segment's timeframe (start second, end second) before any downloading happens, so they can judge for themselves which moments look like real highlights vs. artifacts of the "everyone starts at 0:00" bias.
- Let the user choose exactly which segment(s) to turn into clips, by number, instead of only being able to choose *how many* (top-N) as today.

## Non-Goals
- Changing heatmap scoring, filtering (`MIN_SCORE`), or padding (`PADDING`) logic — this spec only changes what the user sees and picks from, not how segments are computed.
- Removing scores from the display — score is still shown as context, just no longer the sole/silent selection mechanism.
- Automatic detection/exclusion of "intro bias" segments. The user makes that call visually from the listed timeframes; no heuristic is added to guess it.
- A `--clips` CLI flag or non-interactive selection mode — stays consistent with the script's existing interactive-prompt style.

## Requirements
1. This replaces Spec 002's `prompt_clip_count` ("how many clips do you want?") prompt. Clip count is no longer entered as a number up front — it falls out of how many segments the user selects.
2. If exactly one qualifying segment exists, skip listing/selection entirely and proceed with that single segment (no meaningful choice to make).
3. If more than one qualifying segment exists, display them as a numbered list, ordered by **start time ascending** (chronological), not by score — chronological order is what makes an intro-heavy skew visually obvious. Each row shows:
   - Index (1-based, used for selection)
   - Start and end time, formatted as `MM:SS` (or `HH:MM:SS` for videos ≥1 hour), plus the raw start/end in seconds
   - Heatmap score (as already computed, unchanged)
   - The displayed range is the raw heatmap segment (`start` .. `start + duration`), *before* `PADDING` is applied — padding is still added later at download time exactly as it is today, so the actual downloaded clip will be a bit wider than what's listed.
4. Prompt the user to enter which segments to clip, accepting comma-separated indices and ranges (e.g. `2,4,7` or `2-5,9`).
5. Validate: every index must resolve to an integer within `1..len(heatmap_data)`. Invalid input (non-numeric, out-of-range index, empty input) re-prompts, mirroring the existing crop-mode validation loop style.
6. Duplicate indices (e.g. `2,2,3`) are de-duplicated.
7. `MAX_CLIPS` remains the sanity upper bound, now applied to the *selection* instead of a typed count: if the user selects more segments than `MAX_CLIPS`, inform them once and keep only the first `MAX_CLIPS` selected segments in chronological order (same "inform and cap" style as Spec 002's over-request case), rather than re-prompting.
8. Selected segments are processed in chronological (start-time ascending) order — i.e. the same order they were listed in — regardless of the order indices were typed, so `clip_1.mp4`, `clip_2.mp4`, … line up with the displayed list top-to-bottom.
9. Unlike today's behavior (which falls through to the next-highest-score segment on a failed download/crop to still hit a target count), a failed clip is **not** backfilled with a non-selected segment. The run attempts exactly the selected segments and reports however many succeeded out of however many were selected — since the user deliberately chose these moments, silently substituting a different one (e.g. the misleading intro) would defeat the point of this feature.

## Acceptance Criteria
- A video with only 1 qualifying segment generates that clip directly, with no list/prompt shown.
- A video with several qualifying segments shows a chronologically-ordered list (e.g. `1) 00:12–00:34 (score 0.81)`, `2) 03:05–03:40 (score 0.92)`, …) before any download starts.
- Entering `1,3` generates clips only for list items 1 and 3, produced as `clip_1.mp4` (item 1) and `clip_2.mp4` (item 3) in that order.
- Entering an out-of-range index (e.g. `99` when only 5 segments qualify), non-numeric text, or empty input re-prompts instead of crashing.
- Selecting more segments than `MAX_CLIPS` keeps only the first `MAX_CLIPS` in chronological order and tells the user why fewer than requested were kept.
- If a selected segment's download/crop fails, the run continues with the other selected segments and reports the final success count — it does not pull in an unselected segment to compensate.
