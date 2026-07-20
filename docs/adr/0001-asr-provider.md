# ADR 0001: Use hosted ASR (OpenAI Whisper API) instead of self-hosted Whisper Large V3

## Status
Accepted (superseded provider choice: originally Deepgram, switched to OpenAI — see Amendment below)

## Context
Spec called for Whisper Large V3 as primary transcription, self-hosted, while also
targeting CPU-only inference and <$0.30/video total cost. Large-v3 on CPU runs
slower than real-time (often 3-8x audio duration for a single-threaded run),
which either forces GPU instances (destroying the cost target) or creates queue
backpressure that kills user-perceived latency ("upload -> edit plan" needs to
feel fast, not take 20 minutes for a 10 minute video).

## Decision
Use a hosted ASR API for Phase 1 and Phase 2. No GPU, no self-hosted model.

Revisit self-hosting `faster-whisper` (CTranslate2, int8, CPU) only when hosted
ASR spend exceeds the cost of running a dedicated worker box at sustained volume
(rough breakeven: >50k transcription-minutes/month).

## Amendment (2026-07-20): Primary provider is OpenAI, not Deepgram
Originally scoped Deepgram Nova-3 as primary with Groq-hosted Whisper as
fallback. Switched to **OpenAI's `whisper-1` transcription API**
(`response_format=verbose_json`, `timestamp_granularities=["word","segment"]`)
as primary instead, because the founder already holds an OpenAI key and
Deepgram would have meant a new vendor signup for no material benefit at
MVP scale. Cost is comparable (~$0.006/min either way).

**Trade-off accepted**: OpenAI's Whisper API has no built-in speaker
diarization, unlike Deepgram Nova-3. This directly affects
[ADR-0004](0004-metadata-extraction-scope.md), which had assumed diarization
would come free from the ASR provider — amended there. Groq-hosted Whisper
remains an optional fallback (used if the OpenAI call errors); it doesn't
diarize either, so this doesn't reopen the diarization gap, just gives a
backup transcription path. Revisit Deepgram specifically if/when per-speaker
attribution becomes a hard requirement before Phase 3's dedicated diarization
work lands.

## Consequences
- No GPU dependency in Phase 1 infra at all.
- Transcription cost stays ~$0.02-0.06 per 10-min source video, well inside
  the $0.30/video budget.
- Adds a vendor dependency; mitigated by keeping the ASR call behind an
  internal interface (`TranscriptionProvider`) so swapping providers (Groq,
  Deepgram, or self-hosted later) is a config change, not a rewrite.
- Speaker diarization is no longer "comes free" — tracked as a known gap,
  see ADR-0004 amendment.
