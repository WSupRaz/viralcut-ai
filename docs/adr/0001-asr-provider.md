# ADR 0001: Use hosted ASR (Deepgram/Groq) instead of self-hosted Whisper Large V3

## Status
Accepted

## Context
Spec called for Whisper Large V3 as primary transcription, self-hosted, while also
targeting CPU-only inference and <$0.30/video total cost. Large-v3 on CPU runs
slower than real-time (often 3-8x audio duration for a single-threaded run),
which either forces GPU instances (destroying the cost target) or creates queue
backpressure that kills user-perceived latency ("upload -> edit plan" needs to
feel fast, not take 20 minutes for a 10 minute video).

## Decision
Use a hosted ASR API for Phase 1 and Phase 2:
- **Primary: Deepgram Nova-3** (~$0.0043-0.0065/min, word-level timestamps,
  built-in diarization, fast — usually <30s for a 10 min file)
- **Fallback: Groq-hosted Whisper Large V3** (near-zero marginal cost, very fast,
  used if Deepgram errors or for A/B quality checks)

Revisit self-hosting `faster-whisper` (CTranslate2, int8, CPU) only when hosted
ASR spend exceeds the cost of running a dedicated worker box at sustained volume
(rough breakeven: >50k transcription-minutes/month).

## Consequences
- No GPU dependency in Phase 1 infra at all.
- Transcription cost becomes ~$0.02-0.06 per 10-min source video, well inside
  the $0.30/video budget.
- Adds a vendor dependency; mitigated by the Groq fallback and by keeping the
  ASR call behind an internal interface (`TranscriptionProvider`) so swapping
  to self-hosted later is a config change, not a rewrite.
