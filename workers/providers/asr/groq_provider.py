from pathlib import Path

from openai import OpenAI

from workers.config import settings
from workers.providers.asr.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptSegment,
    TranscriptWord,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqWhisperProvider(TranscriptionProvider):
    """Fallback ASR provider, used only if the primary (OpenAI) call fails
    and GROQ_API_KEY is configured. Groq exposes an OpenAI-compatible API for
    Whisper, so this reuses the same client library with a different
    base_url/model rather than a separate SDK."""

    name = "groq:whisper-large-v3"

    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.groq_api_key, base_url=GROQ_BASE_URL)

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        with audio_path.open("rb") as f:
            response = self._client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"],
            )

        data = response.model_dump()
        words = [
            TranscriptWord(word=w["word"], start=w["start"], end=w["end"])
            for w in (data.get("words") or [])
        ]
        segments = [
            TranscriptSegment(text=s["text"].strip(), start=s["start"], end=s["end"])
            for s in (data.get("segments") or [])
        ]
        return TranscriptionResult(
            text=data["text"], language=data.get("language"), words=words, segments=segments
        )
