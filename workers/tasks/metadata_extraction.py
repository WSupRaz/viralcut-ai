import math
import re
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

# PySceneDetect runs a Python frame-by-frame loop; on very long videos it can
# take as long as the transcode itself. Above this source duration we skip it
# -- transcripts + silences still flow to the edit-plan prompt, and the plan
# gets clamped to actual media duration regardless. Configurable via
# SCENE_DETECT_MAX_DURATION_SECONDS.
from workers.db import get_session_factory
from workers.ffmpeg import FFmpegError, probe_duration_seconds, run_ffmpeg
from workers.providers.asr.base import TranscriptionResult
from workers.providers.asr.groq_provider import GroqWhisperProvider
from workers.providers.asr.openai_provider import OpenAIWhisperProvider
from workers.providers.scene_detect.pyscenedetect import detect_scenes
from workers.storage import download_to_path

SILENCE_NOISE_THRESHOLD_DB = "-30dB"
SILENCE_MIN_DURATION_SECONDS = 0.5

# OpenAI and Groq both cap audio uploads at 25 MB per request. We extract
# audio losslessly (FLAC at 16 kHz mono, speech-compressible) and split into
# chunks below this budget for anything longer. ~2 MB of margin absorbs
# encoder overhead above the byte budget.
ASR_MAX_BYTES_PER_REQUEST = 23 * 1024 * 1024
# Chunks shorter than this would multiply API round-trips for little benefit.
ASR_MIN_CHUNK_SECONDS = 60.0

_SILENCE_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def _extract_audio(video_path: Path, audio_path: Path) -> None:
    """Mono 16 kHz FLAC -- lossless (Whisper is trained on 16 kHz audio) and
    small enough that a single hour of speech stays ~30-45 MB, i.e. a few
    API chunks at most instead of one giant file that gets rejected."""
    run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-threads", "1",
            "-i", str(video_path),
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "flac",
            str(audio_path),
        ],
        label="audio extraction",
    )


def _split_audio(audio_path: Path, tmp_dir: Path) -> list[tuple[Path, float]]:
    """Return [(chunk_path, start_offset_seconds)] covering the full audio.
    A single chunk when the file fits the API budget; otherwise split by
    duration so each chunk stays under ASR_MAX_BYTES_PER_REQUEST."""
    size = audio_path.stat().st_size
    if size <= ASR_MAX_BYTES_PER_REQUEST:
        return [(audio_path, 0.0)]

    duration = probe_duration_seconds(str(audio_path))
    bytes_per_second = size / duration if duration > 0 else 0.0
    if bytes_per_second <= 0:
        raise FFmpegError(f"could not determine audio length ({size} bytes)")

    chunk_seconds = max(
        ASR_MIN_CHUNK_SECONDS,
        math.floor((ASR_MAX_BYTES_PER_REQUEST / bytes_per_second) * 0.8),
    )
    chunks = []
    start = 0.0
    index = 0
    while start < duration:
        out_path = tmp_dir / f"audio_part_{index:04d}.flac"
        run_ffmpeg(
            [
                "ffmpeg", "-y",
                "-threads", "1",
                "-ss", f"{start:.3f}",
                "-t", f"{chunk_seconds:.3f}",
                "-i", str(audio_path),
                "-c:a", "flac",
                str(out_path),
            ],
            label="audio split",
        )
        chunks.append((out_path, start))
        start += chunk_seconds
        index += 1
    return chunks


def _detect_silences(audio_path: Path) -> list[dict]:
    """Dead-air windows via ffmpeg's silencedetect filter (ADR-0003). Reads
    from stderr -- with `-f null -` there's no output file, so that's where
    ffmpeg logs the filter's silence_start/silence_end markers."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-threads", "1", "-i", str(audio_path),
                "-af", f"silencedetect=noise={SILENCE_NOISE_THRESHOLD_DB}:d={SILENCE_MIN_DURATION_SECONDS}",
                "-f", "null", "-",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()[-1500:]
        raise FFmpegError(f"silence detection failed (exit {exc.returncode}): {detail}") from exc

    silences = []
    pending_start = None
    for line in result.stderr.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue
        end_match = _SILENCE_END_RE.search(line)
        if end_match and pending_start is not None:
            silences.append({"start": pending_start, "end": float(end_match.group(1))})
            pending_start = None
    return silences


def _transcribe_with_fallback(audio_path: Path, start_offset: float) -> tuple[TranscriptionResult, str]:
    try:
        provider = OpenAIWhisperProvider()
        return provider.transcribe(audio_path, start_offset=start_offset), provider.name
    except Exception:
        if not settings.groq_api_key:
            raise
        provider = GroqWhisperProvider()
        return provider.transcribe(audio_path, start_offset=start_offset), provider.name


def _transcribe_all(chunks: list[tuple[Path, float]]) -> tuple[TranscriptionResult, str]:
    """Transcribe every chunk (each with its own provider fallback) and merge
    into one global-timeline result. Chunks are already timestamp-offset by
    _split_audio/start_offset, so words and segments just concatenate."""
    all_words: list = []
    all_segments: list = []
    texts: list[str] = []
    language: str | None = None
    provider_names: set[str] = set()

    for index, (chunk_path, chunk_offset) in enumerate(chunks):
        result, provider_name = _transcribe_with_fallback(chunk_path, chunk_offset)
        if index == 0:
            language = result.language
        provider_names.add(provider_name)
        texts.append(result.text)
        all_words.extend(result.words)
        all_segments.extend(result.segments)

    merged = TranscriptionResult(
        text=" ".join(t for t in texts if t),
        language=language,
        words=all_words,
        segments=all_segments,
    )
    return merged, ",".join(sorted(provider_names))


def _set_stage(session_factory, job_id: uuid.UUID, progress_pct: int, stage: str) -> None:
    with session_factory() as session:
        job = session.get(Job, uuid.UUID(str(job_id)))
        if job is not None:
            job.progress_pct = progress_pct
            job.stage = stage
            session.commit()


@celery_app.task(name="workers.tasks.metadata_extraction.extract_metadata", bind=True, max_retries=3)
def extract_metadata(self, source_video_id: str, job_id: str) -> dict:
    """Pipeline steps 3-4: structured metadata extraction -- transcript
    (ASR), scene changes (PySceneDetect), and silence windows (ffmpeg
    silencedetect), all run against the proxy. speakers is a single
    full-duration segment per the ADR-0004 amendment (OpenAI's Whisper API
    doesn't diarize; PySceneDetect/silencedetect are unaffected by that).

    Long videos: audio is extracted losslessly and transcribed in <=25 MB
    chunks (the ASR providers' hard upload cap), with word/segment timestamps
    offset back into global time -- previously a video longer than ~50 min
    failed the whole job because its 64 kbps mp3 exceeded the API limit.
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
        job.celery_task_id = self.request.id
        job.stage = "Downloading proxy"
        job.progress_pct = 5
        proxy_key = source_video.r2_key_proxy
        duration = source_video.duration_seconds
        session.commit()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            # PySceneDetect's OpenCV backend wants a recognizable extension.
            proxy_path = tmp_dir / "proxy_input.mp4"
            audio_path = tmp_dir / "audio.flac"

            download_to_path(proxy_key, str(proxy_path))
            _set_stage(session_factory, uuid.UUID(job_id), 15, "Extracting audio")

            _extract_audio(proxy_path, audio_path)
            _set_stage(session_factory, uuid.UUID(job_id), 25, "Transcribing audio")

            chunks = _split_audio(audio_path, tmp_dir)
            transcript, provider_name = _transcribe_all(chunks)

            source_duration = float(duration) if duration else 0.0
            scene_cap = settings.scene_detect_max_duration_seconds
            if source_duration > scene_cap:
                _set_stage(
                    session_factory, uuid.UUID(job_id), 60,
                    f"Skipping scene detection ({int(source_duration)}s video)",
                )
                scenes = []
                scene_skipped = (
                    f"scene detection skipped: source is {int(source_duration)}s, "
                    f"limit is {int(scene_cap)}s"
                )
            else:
                _set_stage(session_factory, uuid.UUID(job_id), 60, "Detecting scenes")
                scenes = detect_scenes(proxy_path)
                scene_skipped = None
            _set_stage(session_factory, uuid.UUID(job_id), 85, "Detecting silences")
            silence_windows = _detect_silences(audio_path)
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
    scene_changes = {"scenes": scenes}
    if scene_skipped:
        scene_changes["skipped"] = scene_skipped
    silences = {"silences": silence_windows}

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
        job.stage = "Metadata ready"
        session.commit()

    return {
        "source_video_id": source_video_id,
        "provider": provider_name,
        "transcript_word_count": len(transcript.words),
        "audio_chunks": len(chunks),
        "scenes": len(scenes),
        "scene_skipped": scene_skipped is not None,
    }
