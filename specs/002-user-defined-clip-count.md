# Spec 002: User-Defined Clip Count (Highest → Lowest Heatmap)

## Status
Draft → Implemented on `feature/progress-bar-and-clip-count`

## Problem
The number of clips generated per run is hardcoded (`MAX_CLIPS = 10`). Users can't ask for fewer (to save time) or more (up to however many segments qualify) without editing source.

## Goals
- Let the user specify N (how many clips to generate) interactively, alongside the existing crop-mode and subtitle prompts.
- Preserve existing behavior: segments are already sorted by heatmap `score` descending (`ambil_most_replayed` does this), so "start from the highest heatmap, then lower" falls out naturally from taking the first N of that sorted list — no new sorting logic needed.

## Non-Goals
- Changing how segments are scored, filtered (`MIN_SCORE`), or padded (`PADDING`) — unrelated to clip count.
- A `--clips N` CLI flag. This stays consistent with the script's existing interactive-prompt style (crop mode, subtitle y/n); non-interactive/CLI-arg mode is not in scope.

## Requirements
1. After heatmap data is fetched and the segment count is known (`Found {len} high-engagement segments.`), prompt: `How many clips do you want to generate? (1-{MAX_CLIPS}): `.
2. Validate input is a positive integer within `1..MAX_CLIPS`; re-prompt on invalid input (empty, non-numeric, zero, negative, or above the cap), mirroring the existing crop-mode validation loop style.
3. `MAX_CLIPS` remains in the code, but its role changes from "hardcoded run target" to "sanity upper bound" for the prompt, preventing accidental huge requests.
4. Effective target = `min(user_n, len(heatmap_data))`. If fewer segments qualify than requested, inform the user once (e.g. `Only 4 qualifying segment(s) available — generating 4 clip(s).`) rather than erroring.
5. The generation loop iterates `heatmap_data` in its existing (score-descending) order and stops once the effective target count of successful clips is reached — same logic as today, just parameterized by the user's N instead of the constant.

## Acceptance Criteria
- Entering `3` when 8 segments qualify produces clips `clip_1.mp4..clip_3.mp4` sourced from the 3 highest-scoring segments.
- Entering a number greater than the available qualifying segments (e.g. `10` when only `4` qualify) generates all 4, with a message explaining why fewer than requested were made.
- Entering `0`, a negative number, or non-numeric text re-prompts instead of crashing or silently defaulting.