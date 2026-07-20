import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select

from db_models.models.enums import JobStatus, SourceVideoStatus
from db_models.models.job import Job
from db_models.models.source_video import SourceVideo
from db_models.models.video_metadata import VideoMetadata

from workers.celery_app import celery_app
from workers.config import settings
from workers.db import get_session_factory
from workers.providers.asr.base import TranscriptionResult
from workers.providers.asr.groq_provider import GroqWhisperProvider
from workers.providers.asr.openai_provider import OpenAIWhisperProvider
from workers.storage import download_to_path


def _extract_audio(video_path: Path, audio_path: Path) -> None:
    """Mono 16kHz mp3 -- small enough to stay well under the ASR API's 25MB
    upload limit for any reasonably-sized clip, and audio quality doesn't
    matter beyond what transcription needs."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "libmp3lame", "-b:a", "64k",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def _transcribe_with_fallback(audio_path: Path) -> tuple[TranscriptionResult, str]:
    try:
        provider = OpenAIWhisperProvider()
        return provider.transcribe(audio_path), provider.name
    except Exception:
        if not settings.groq_api_key:
            raise
        provider = GroqWhisperProvider()
        return provider.transcribe(audio_path), provider.name


@celery_app.task(name="workers.tasks.metadata_extraction.extract_metadata", bind=True, max_retries=3)
def extract_metadata(self, source_video_id: str, job_id: str) -> dict:
    """Pipeline steps 3-4: structured metadata extraction. Currently
    implements the ASR portion (transcript) for real; scene_changes and
    silences are populated with honest empty placeholders here and filled in
    by PySceneDetect/ffmpeg silencedetect in the next task -- not faked, just
    not built yet. speakers is a single full-duration segment per the
    ADR-0004 amendment (OpenAI's Whisper API doesn't diarize).
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        job = session.get(Job, uuid.UUID(job_id))
        source_video = session.get(SourceVideo, uuid.UUID(source_video_id))
        if job is None or source_video is None:
            raise ValueError(f"source_video {source_video_id} or job {job_id} not found")
        if source_video.r2_key_proxy is None:
            raise ValueError(f"source_video {source_video_id} has no proxy yet")

        job.status = JobStatus.RUNNING
        proxy_key = source_video.r2_key_proxy
        duration = source_video.duration_seconds
        session.commit()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            proxy_path = tmp_dir / "proxy_input"
            audio_path = tmp_dir / "audio.mp3"

            download_to_path(proxy_key, str(proxy_path))
            _extract_audio(proxy_path, audio_path)
            transcript, provider_name = _transcribe_with_fallback(audio_path)
    except Exception as exc:
        with session_factory() as session:
            job = session.get(Job, uuid.UUID(job_id))
            job.status = JobStatus.FAILED
            job.error = str(exc)[:2000]
            job.retry_count = (job.retry_count or 0) + 1
            session.commit()
        raise

    speakers = {
        "segments": [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": float(duration) if duration else None}
        ]
    }
    scene_changes = {"scenes": []}  # filled in by the next task (PySceneDetect)
    silences = {"silences": []}  # filled in by the next task (ffmpeg silencedetect)

    with session_factory() as session:
        source_video = session.get(SourceVideo, uuid.UUID(source_video_id))
        job = session.get(Job, uuid.UUID(job_id))

        existing = session.execute(
            select(VideoMetadata).where(VideoMetadata.source_video_id == source_video.id)
        ).scalar_one_or_none()
        if existing is None:
            existing = VideoMetadata(source_video_id=source_video.id)
            session.add(existing)

        existing.transcript = transcript.to_json()
        existing.scene_changes = scene_changes
        existing.silences = silences
        existing.speakers = speakers
        existing.provider = provider_name

        source_video.status = SourceVideoStatus.METADATA_READY
        job.status = JobStatus.SUCCEEDED
        job.progress_pct = 100
        session.commit()

    return {
        "source_video_id": source_video_id,
        "provider": provider_name,
        "transcript_word_count": len(transcript.words),
    }
