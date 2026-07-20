# ADR 0004: Defer face/emotion/object detection out of MVP metadata extraction

## Status
Accepted

## Context
Spec's metadata extraction step lists transcript, scene changes, silences,
faces, speaker changes, emotions, and object detection. Face/emotion/object
detection require vision models that are either GPU-leaning or add material
CPU latency and cost per video, and no MVP feature (silence removal, captions,
zooms, style presets, export) actually consumes them.

## Decision
Phase 1 metadata extraction produces only:
- Transcript with word-level timestamps (from ADR-0001's ASR provider)
- Scene changes (PySceneDetect)
- Silence/dead-air windows (ffmpeg `silencedetect`)
- Speaker changes (diarization from the ASR provider's built-in diarization,
  not a separate model)

Face detection, emotion detection, and object detection are deferred to
Phase 3, and only built when a specific feature requires them (e.g., face-
tracked auto-reframe, emotion-based B-roll timing).

## Consequences
- Metadata extraction stays CPU-only and cheap, keeping the whole pipeline
  inside the $0.30/video target.
- Claude's edit-plan prompt in Phase 1 is simpler (fewer, more reliable
  signals) which reduces hallucinated/inconsistent edit decisions.
- Style presets that conceptually want "punch zoom on the speaker's face"
  approximate it via transcript emphasis + scene timing in MVP, not actual
  face coordinates. Documented as a known limitation, not a silent gap.
