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
- Speaker changes (see amendment below — no longer "free" from the ASR provider)

Face detection, emotion detection, and object detection are deferred to
Phase 3, and only built when a specific feature requires them (e.g., face-
tracked auto-reframe, emotion-based B-roll timing).

## Amendment (2026-07-20): speaker diarization is not included in Phase 1
This ADR originally assumed the ASR provider would hand back speaker labels
as part of transcription. [ADR-0001](0001-asr-provider.md) settled on
OpenAI's Whisper API as primary, which has no diarization endpoint — Deepgram
did, OpenAI doesn't. Rather than add a second ML dependency (e.g.
pyannote-audio, which needs its own model download and meaningfully more CPU
time) just to fill in a field nothing in Phase 1 consumes yet, speaker
diarization is deferred: the `metadata.speakers` column
(docs/03-database-schema.md) is populated with a single segment spanning the
full duration in Phase 1, not real per-speaker attribution.

This is a real, not cosmetic, limitation: style rules that want to react to
speaker changes (e.g. a cut on speaker swap in a podcast) can't yet in MVP.
None of the four Phase 1 style presets currently require it. Revisit when a
preset or feature needs true diarization — candidates are pyannote-audio
(self-hosted, CPU-feasible for short clips) or switching back to Deepgram for
its diarization endpoint specifically.

## Consequences
- Metadata extraction stays CPU-only and cheap, keeping the whole pipeline
  inside the $0.30/video target.
- Claude's edit-plan prompt in Phase 1 is simpler (fewer, more reliable
  signals) which reduces hallucinated/inconsistent edit decisions.
- Style presets that conceptually want "punch zoom on the speaker's face"
  approximate it via transcript emphasis + scene timing in MVP, not actual
  face coordinates. Documented as a known limitation, not a silent gap.
