# ADR 0003: Trim video stack to FFmpeg + PySceneDetect + Remotion for MVP

## Status
Accepted

## Context
Spec listed FFmpeg, Remotion, OpenCV, MoviePy, and PySceneDetect as the video
stack. Several overlap in responsibility, which multiplies dependency surface,
Docker image size, and CPU worker cold-start time for no MVP-stage benefit.

## Decision
- **FFmpeg**: cuts, silence/filler removal, proxy generation, audio extraction,
  concat, final container muxing. Invoked via subprocess, never a Python
  wrapper library.
- **PySceneDetect**: scene-change detection only, feeding Claude's metadata
  input. CPU-only, cheap.
- **Remotion**: captions, punch zooms, motion graphics, transitions, B-roll
  compositing, final visual render. Runs server-side via `@remotion/renderer`
  in a Node worker.
- **Dropped for MVP**: MoviePy (redundant with direct FFmpeg calls, slower),
  OpenCV (only needed for face-tracked auto-reframe / subject-aware crop,
  which is a Phase 2+ feature, not MVP).

## Consequences
- Fewer dependencies to containerize, patch, and version-pin.
- Auto-reframe for 9:16 in MVP uses a **static center-crop or rule-of-thirds
  crop** (no face tracking) — acceptable for v1, explicitly called out as a
  known quality gap to close in Phase 2 when OpenCV/face-tracking is added.
- Render worker is a mixed Python (FFmpeg orchestration) + Node (Remotion)
  process; documented in architecture.md so it isn't a surprise at
  implementation time.
