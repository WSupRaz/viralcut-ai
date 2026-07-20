import subprocess
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

from db_models.models.enums import JobStatus, SourceVideoStatus
from db_models.models.job import Job
from db_models.models.source_video import SourceVideo

from workers.celery_app import celery_app
from workers.db import get_session_factory
from workers.storage import download_to_path, upload_from_path

PROXY_HEIGHT = 480


def _probe_duration_seconds(path: Path) -> Decimal:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return Decimal(result.stdout.strip()).quantize(Decimal("0.001"))


def _transcode_proxy(input_path: Path, output_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"scale=-2:{PROXY_HEIGHT}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


@celery_app.task(name="workers.tasks.proxy.generate_proxy", bind=True, max_retries=3)
def generate_proxy(self, source_video_id: str, job_id: str) -> dict:
    """Pipeline step 2: transcode a raw upload into a low-res proxy for fast
    preview/editing (docs/01-architecture.md). Runs entirely on CPU via
    ffmpeg (ADR-0003) -- no GPU, no MoviePy wrapper.

    Each DB touch uses its own short-lived session so the connection isn't
    held open for the duration of the ffmpeg transcode, and so a crash
    mid-transcode leaves the job/source_video rows in a consistent state
    (RUNNING, not half-updated). Safe to retry: re-downloads, re-transcodes,
    and overwrites the same proxy key and row values.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        job = session.get(Job, uuid.UUID(job_id))
        source_video = session.get(SourceVideo, uuid.UUID(source_video_id))
        if job is None or source_video is None:
            raise ValueError(f"source_video {source_video_id} or job {job_id} not found")

        job.status = JobStatus.RUNNING
        raw_key = source_video.r2_key_raw
        project_id = source_video.project_id
        session.commit()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            raw_path = tmp_dir / "raw_input"
            proxy_path = tmp_dir / "proxy.mp4"

            download_to_path(raw_key, str(raw_path))
            duration = _probe_duration_seconds(raw_path)
            _transcode_proxy(raw_path, proxy_path)

            proxy_key = f"proxy/{project_id}/{source_video_id}.mp4"
            upload_from_path(str(proxy_path), proxy_key)
    except Exception as exc:
        with session_factory() as session:
            job = session.get(Job, uuid.UUID(job_id))
            job.status = JobStatus.FAILED
            job.error = str(exc)[:2000]
            job.retry_count = (job.retry_count or 0) + 1
            session.commit()
        raise

    with session_factory() as session:
        source_video = session.get(SourceVideo, uuid.UUID(source_video_id))
        job = session.get(Job, uuid.UUID(job_id))

        source_video.r2_key_proxy = proxy_key
        source_video.duration_seconds = duration
        source_video.status = SourceVideoStatus.PROXY_READY
        job.status = JobStatus.SUCCEEDED
        job.progress_pct = 100
        session.commit()

    return {
        "source_video_id": source_video_id,
        "r2_key_proxy": proxy_key,
        "duration_seconds": str(duration),
    }
