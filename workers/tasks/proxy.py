import subprocess
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

from db_models.models.enums import JobStatus, JobType, SourceVideoStatus
from db_models.models.job import Job
from db_models.models.source_video import SourceVideo

from workers.celery_app import celery_app
from workers.db import get_session_factory
from workers.ffmpeg import probe_duration_seconds, run_ffmpeg
from workers.storage import download_to_path, upload_from_path

PROXY_HEIGHT = 480
PROXY_FPS = 15


def _transcode_proxy(input_path: Path, output_path: Path) -> None:
    # Unset thread count auto-scales to every CPU the container reports
    # (8 here) -- decoding a 4K source across that many threads holds that
    # many ~12MB raw frames in flight at once, easily enough to blow a
    # free-tier instance's 512MB RAM ceiling before encoding even starts.
    # Single-threaded is slower but bounds decode memory to ~one frame at a
    # time; -bf 0 avoids the encoder buffering frames for B-frame reordering.
    run_ffmpeg(
        [
            "ffmpeg", "-y",
            "-threads", "1",
            "-i", str(input_path),
            # Nothing downstream of the proxy needs full frame rate or a
            # high-quality scaler: it feeds preview, PySceneDetect (which
            # works off timestamps in seconds, unaffected by fps), and audio
            # extraction for ASR. The final render re-cuts the *raw* source,
            # never this file, so cheapening it costs no output quality.
            # Halving fps and using the cheap scaler cuts the scale+encode
            # work roughly in half on a 0.1-CPU free-tier instance.
            "-vf", f"scale=-2:{PROXY_HEIGHT}:flags=fast_bilinear",
            "-r", str(PROXY_FPS),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-bf", "0",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_path),
        ],
        label="proxy transcode",
    )


def _set_stage(session_factory, job_id: uuid.UUID, progress_pct: int, stage: str) -> None:
    with session_factory() as session:
        job = session.get(Job, uuid.UUID(str(job_id)))
        if job is not None:
            job.progress_pct = progress_pct
            job.stage = stage
            session.commit()


@celery_app.task(name="workers.tasks.proxy.generate_proxy", bind=True, max_retries=3)
def generate_proxy(self, source_video_id: str, job_id: str) -> dict:
    """Pipeline step 2: transcode a raw upload into a low-res proxy for fast
    preview/editing (docs/01-architecture.md). Runs entirely on CPU via
    ffmpeg (ADR-0003) -- no GPU, no MoviePy wrapper.

    Receives only a storage reference (source_video_id/job_id) -- the video
    binary never travels through Redis/Celery, and never into this process's
    memory: boto3 streams the download to a temp file, ffmpeg reads it
    frame-by-frame, and the proxy is streamed back up.

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
        job.celery_task_id = self.request.id
        job.stage = "Downloading source"
        job.progress_pct = 5
        raw_key = source_video.r2_key_raw
        project_id = source_video.project_id
        session.commit()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            raw_path = tmp_dir / "raw_input"
            proxy_path = tmp_dir / "proxy.mp4"

            download_to_path(raw_key, str(raw_path))
            _set_stage(session_factory, job_id, 30, "Probing media")
            duration = Decimal(str(probe_duration_seconds(str(raw_path)))).quantize(
                Decimal("0.001")
            )
            _set_stage(session_factory, job_id, 40, "Transcoding proxy")
            _transcode_proxy(raw_path, proxy_path)
            _set_stage(session_factory, job_id, 90, "Uploading proxy")

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
        job.stage = "Proxy ready"

        # Chain into metadata extraction automatically -- it needs no user
        # input, unlike edit-plan generation (explicit user action, since it
        # depends on style/instructions the user may still be setting).
        next_job = Job(
            project_id=source_video.project_id,
            type=JobType.METADATA_EXTRACTION,
            source_video_id=source_video.id,
        )
        session.add(next_job)
        session.commit()
        next_job_id = str(next_job.id)

    celery_app.send_task(
        "workers.tasks.metadata_extraction.extract_metadata",
        args=[source_video_id, next_job_id],
    )

    return {
        "source_video_id": source_video_id,
        "r2_key_proxy": proxy_key,
        "duration_seconds": str(duration),
        "metadata_job_id": next_job_id,
    }
