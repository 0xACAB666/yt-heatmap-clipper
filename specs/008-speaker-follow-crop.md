# Spec 008: Speaker-Follow Crop Mode

## Status
Draft → Implemented on `feature/speaker-follow-crop`

## Problem
All three existing crop modes (`default`, `split_left`, `split_right`) frame the clip at a fixed spatial position for the entire duration: a static center crop, or a static split between a fixed-position "top" region and a fixed-position facecam corner. For source video with multiple people in a single, uncut frame (podcast/interview-style content), a fixed crop means the active speaker is often out of frame or off-center for stretches of the clip, since there's no camera operator choosing who to frame. The crop needs to move to whoever is actually talking.

## Goals
- Add a fourth crop mode, `speaker_follow`, that detects which on-screen face is speaking and crops horizontally to follow that face, switching framing at speaker-turn boundaries.
- Detection is CPU-only and audio-visual: track faces across sampled frames, compute a mouth-openness signal per face, and correlate it against the clip's audio energy over the same windows — the face whose mouth movement best matches the audio is the active speaker for that window.
- Crop motion is discrete holds: the crop stays fixed on the current speaker's position, then jumps to the next speaker's position at a detected turn-change. Implemented as a single ffmpeg pass using a piecewise, time-keyed `crop` filter expression (like the existing modes, no intermediate re-encode per turn).
- Graceful, per-clip fallback to the existing `default` center crop — with a printed notice, never a hard failure — whenever detection can't produce a confident result (0 or 1 face found, detection library unavailable, etc.).

## Non-Goals
- No continuous/smooth panning between speakers — that's future work if discrete holds prove too jumpy in practice.
- No speaker identity/diarization labeling (no "Speaker 1/2" naming, no linking to subtitle text or captions). This mode only decides *where to crop*, not who anyone is.
- No dedicated pretrained active-speaker-detection model (e.g. Light-ASD/TalkNet). The heuristic (mouth movement vs. audio energy) is the whole detection mechanism for this spec.
- No combination with `split_left`/`split_right` — `speaker_follow` is a fourth, mutually exclusive option in the crop-mode prompt, not a modifier on the split modes.
- No support for more than a small, fixed cap of simultaneously tracked faces (see Requirements) — videos with many people on screen are not a target use case yet.
- No GPU requirement or usage.
- No change to `default`, `split_left`, or `split_right` behavior.

## Requirements
1. Add `speaker_follow` as a fourth choice in the crop-mode prompt in `main()` (currently a 1–3 menu at run.py:642–662): `4. Speaker follow (auto-crop to whoever is talking)`, mapping to `crop_mode = "speaker_follow"`.
2. New dependency: `mediapipe` (face + facial-landmark detection, CPU-only, no separate checkpoint download beyond what the package bundles). Add to `requirements.txt` as an optional extra, and extend `cek_dependensi` to check/install it the same way it already does for `faster-whisper` — only required when `crop_mode == "speaker_follow"` is selected for the run; other modes are unaffected if it's missing.
3. Add `detect_speaker_turns(video_path, start, end)`, called from `proses_satu_clip` before the crop pass when `crop_mode == "speaker_follow"`:
   - Sample frames from the segment at a fixed interval (new constant `FACE_SAMPLE_INTERVAL_SEC`, suggested default `0.2`).
   - Run mediapipe face + landmark detection per sampled frame; track detected faces across frames into stable per-face tracks using simple nearest-bounding-box-center matching (new constant `MAX_TRACKED_FACES`, suggested default `4`) — no re-identification model, just frame-to-frame proximity.
   - For each face track, compute a mouth-aspect-ratio (MAR) time series from mouth landmarks.
   - Extract audio energy (short-time RMS) from the same segment at matching sample timestamps.
   - Over a sliding window, score each active face track by how well its MAR signal correlates with the audio energy in that window; the highest-scoring face is that window's active speaker.
   - Merge consecutive same-speaker windows into turns; drop/absorb any turn shorter than a minimum duration (new constant `MIN_SPEAKER_TURN_SEC`, suggested default `1.5`) into its neighboring turn, so the crop doesn't flicker between speakers faster than that.
   - Return an ordered list of `(turn_start, turn_end, face_center_x)` relative to the segment, or `None`/empty if fewer than 2 distinct faces were tracked with enough confidence to produce turns.
4. Crop-position mapping: each turn's `face_center_x` maps to a horizontal crop offset the same way the existing modes compute theirs (`scale=-2:1280` then `crop=720:1280:<x>:(ih-1280)/2`), except `<x>` is chosen to center the crop window on that face instead of the frame, clamped so the 720px-wide window never runs outside the scaled frame's bounds.
5. When turns are available, build a single ffmpeg pass for the segment using a piecewise `x` expression in the `crop` filter keyed on turn boundaries (e.g. `x='if(lt(t,T1),X0,if(lt(t,T2),X1,...))'`), analogous to how `default`/`split_left`/`split_right` build their filter strings today — no per-turn re-encode or concat.
6. Fallback path (any of: mediapipe unavailable/failed to install, detection raised an error, fewer than 2 usable face tracks found): print a one-line notice (e.g. `[Clip N] Speaker-follow detection unavailable/inconclusive — using default center crop.`) and process that clip with the existing `default` center-crop filter. This is a per-clip fallback, not a whole-run abort — matches the existing style of `list_available_heights`/resolution-discovery failing gracefully.
7. Subtitle burn-in (`use_subtitle`) works unchanged on top of the `speaker_follow` output — it already operates on `cropped_file` regardless of which mode produced it.

## Acceptance Criteria
- The crop-mode prompt offers a 4th option; selecting it sets `crop_mode = "speaker_follow"` for the whole run, consistent with how the other three are chosen once per run.
- Given a clip with two people who take turns speaking on camera, the output clip's horizontal crop position visibly changes at speaker turn boundaries, holding steady on one speaker between changes (verified by manual review).
- A clip with only one face on screen (or where detection can't confidently separate speakers) automatically falls back to the standard center crop, with a printed notice, and does not abort the run.
- If `mediapipe` is missing and the user selected `speaker_follow`, `cek_dependensi` attempts to install it the same way it does for `faster-whisper`; if that install fails, the run proceeds with the per-clip fallback in Requirement 6 rather than crashing.
- `default`, `split_left`, and `split_right` produce byte-identical behavior to before this feature.
- No crop switch happens more often than `MIN_SPEAKER_TURN_SEC` apart within a single clip.