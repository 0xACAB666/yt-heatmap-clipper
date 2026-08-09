# Spec 010: Half-Screen (Left/Right) Crop Mode

## Status
Draft → Implemented on `feature/half-screen-crop`

## Problem
The existing crop modes all frame the *same* content for a clip's full duration: a static center crop (`default`), a static center-plus-facecam-corner stack (`split_left`/`split_right`), or a dynamically detected active speaker (`speaker_follow`). None of them handle a common two-person layout: a single uncut 16:9 frame with one speaker positioned on the left half and another on the right half (e.g. a podcast recorded on one camera, host and guest sitting side by side), where the user already knows — for the whole video — which side they want and just wants that half cropped out to 9:16. `speaker_follow`'s automatic detection is overkill (and a heavier dependency) when the user can simply say "always keep the left side" up front.

## Goals
- Add two new crop modes, `half_left` and `half_right`, that crop a fixed-width vertical slice centered on the left or right half of the scaled frame respectively, for the entire clip.
- Keep the implementation as simple as `default`'s: a single `-vf scale,crop` pass, no `filter_complex`, no stacking, no per-frame analysis.
- Let the user pick left-vs-right once per run, same as every other crop mode (one crop-mode selection up front in `main()`, applied to all selected clips).

## Non-Goals
- No automatic detection of which side is currently speaking — that's `speaker_follow`'s job. `half_left`/`half_right` are static for the whole run, chosen manually by the user because they already know the layout (e.g. "the source speaker is always on the left in this video").
- No configurable crop width or offset — reuse the existing fixed 720px output width, anchored to the midpoint of the left or right half of the scaled frame (analogous to how `default` is hardcoded to a centered 720px crop, just centered on a half instead of the whole frame).
- No per-clip face detection to fine-tune the anchor — the heuristic assumes the two speakers are roughly symmetric around the frame's vertical centerline and each sits near the middle of their half. If that assumption doesn't hold for a given video, this is a candidate for a future spec (e.g. reusing `speaker_follow`'s mediapipe detection to locate the actual face instead of guessing the half's midpoint).
- No combination with `split_left`/`split_right` or `speaker_follow` — two more mutually exclusive choices in the crop-mode prompt, not modifiers.
- No change to `default`, `split_left`, `split_right`, or `speaker_follow` behavior.
- No change to subtitle burn-in — it already runs unchanged on top of `cropped_file` regardless of which mode produced it.

## Requirements
1. Add `half_left` and `half_right` as two new branches in `proses_satu_clip`'s crop-mode dispatch (`run.py`, alongside `default`/`split_left`/`split_right`/`speaker_follow`), each a single `-vf` pass (no `filter_complex`):
   - `half_left`: `scale=-2:1280,crop=720:1280:(iw/2-720)/2:(ih-1280)/2` — centered on the midpoint of the left half of the scaled frame.
   - `half_right`: `scale=-2:1280,crop=720:1280:iw/2+(iw/2-720)/2:(ih-1280)/2` — centered on the midpoint of the right half of the scaled frame.
   - Vertical centering matches `default` (`(ih-1280)/2`); only the horizontal anchor changes. Anchoring on the half's midpoint (rather than flush to the outer frame edge) keeps a centered speaker's face inside the crop instead of near/off the boundary.
2. Extend the crop-mode prompt in `main()` (currently a 1–4 menu) to 1–6:
   - `5. Half screen — left (keep the left half, e.g. left-side speaker)` → `crop_mode = "half_left"`
   - `6. Half screen — right (keep the right half, e.g. right-side speaker)` → `crop_mode = "half_right"`
   Invalid-choice handling and the "Selected: ..." confirmation echo follow the same pattern as the existing four options.
3. Update `proses_satu_clip`'s docstring (`crop_mode: "default", "split_left", "split_right", "speaker_follow", "half_left", or "half_right"`) and the `CLAUDE.md` architecture notes' crop-mode bullet list to mention the two new modes.
4. `cek_dependensi` is unaffected — `half_left`/`half_right` need no new dependency (unlike `speaker_follow`'s `mediapipe`), so no change to its install-check logic beyond leaving it untriggered for these modes.

## Acceptance Criteria
- The crop-mode prompt offers 6 options; selecting 5 or 6 sets `crop_mode` to `half_left`/`half_right` for the whole run, consistent with how the other modes are chosen once per run.
- Given a side-by-side two-person source clip, `half_left` output contains only the left-side speaker and `half_right` output contains only the right-side speaker, for the clip's full duration (verified by manual review, e.g. against https://www.youtube.com/watch?v=BG1juhuu3YE).
- `default`, `split_left`, `split_right`, and `speaker_follow` produce byte-identical behavior to before this feature.
- Subtitle burn-in, when enabled, works unchanged on `half_left`/`half_right` output.
