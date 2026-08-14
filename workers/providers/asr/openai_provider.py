from pathlib import Path

from openai import OpenAI

from workers.config import settings
from workers.providers.asr.base import (
    TranscriptionProvider,
    TranscriptionResult,
    TranscriptSegment,
    TranscriptWord,
)


class OpenAIWhisperProvider(TranscriptionProvider):
    name = "openai:whisper-1"

    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)

    def transcribe(self, audio_path: Path, start_offset: float = 0.0) -> TranscriptionResult:
        """start_offset (seconds) is added to every word/segment timestamp so
        chunks of a long audio file can be transcribed independently and
        merged back into global time (see metadata_extraction._split_audio)."""
        with audio_path.open("rb") as f:
            response = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"],
            )

        data = response.model_dump()
        words = [
            TranscriptWord(word=w["word"], start=w["start"] + start_offset, end=w["end"] + start_offset)
            for w in (data.get("words") or [])
        ]
        segments = [
            TranscriptSegment(text=s["text"].strip(), start=s["start"] + start_offset, end=s["end"] + start_offset)
            for s in (data.get("segments") or [])
        ]
        return TranscriptionResult(
            text=data["text"], language=data.get("language"), words=words, segments=segments
        )
