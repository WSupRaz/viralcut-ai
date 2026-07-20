from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TranscriptWord:
    word: str
    start: float
    end: float


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float


@dataclass
class TranscriptionResult:
    text: str
    language: str | None
    words: list[TranscriptWord]
    segments: list[TranscriptSegment]

    def to_json(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "words": [{"word": w.word, "start": w.start, "end": w.end} for w in self.words],
            "segments": [
                {"text": s.text, "start": s.start, "end": s.end} for s in self.segments
            ],
        }


class TranscriptionProvider(ABC):
    name: str

    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult: ...
