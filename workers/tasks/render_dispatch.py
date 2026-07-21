import subprocess
import tempfile
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select

from db_models.models.edit_plan import EditPlan as EditPlanRow
from db_models.models.enums import JobStatus
from db_models.models.export import Export
from db_models.models.job import Job
from db_models.models.source_video import SourceVideo
from db_models.models.timeline import Timeline

from workers.celery_app import celery_app
from workers.config import settings
from workers.db import get_session_factory
from workers.storage import download_to_path, upload_from_path

# Re-encode (not stream-copy) every trim: -ss before -i is a fast keyframe
# seek, but combined with a re-encoded output ffmpeg still decodes forward
# to the exact requested frame -- frame-accurate cuts at arbitrary
# (non-keyframe) timestamps, which is exactly what Claude's timeline gives us.
ENCODE_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-ar", "48000"]

RENDER_WORKER_TIMEOUT_SECONDS = 300.0


def _trim_clip(input_path: Path, output_path: Path, start: float, end: float) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start), "-to", str(end),
            "-i", str(input_path),
            *ENCODE_ARGS,
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def _concat_clips(clip_paths: list[Path], output_path: Path, concat_list_path: Path) -> None:
    # All clips just went through the same ENCODE_ARGS above, so their codec
    # params match and a stream-copy concat is safe (fast, no quality loss).
    concat_list_path.write_text("".join(f"file '{p}'\n" for p in clip_paths))
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list_path),
            "-c", "copy",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


def _resolve_raw_keys(session, timeline: list[dict]) -> dict[uuid.UUID, str]:
    source_video_ids = {uuid.UUID(clip["source_video_id"]) for clip in timeline}
    source_videos = (
        session.execute(select(SourceVideo).where(SourceVideo.id.in_(source_video_ids)))
        .scalars()
        .all()
    )
    raw_keys = {sv.id: sv.r2_key_raw for sv in source_videos}
    missing = source_video_ids - set(raw_keys)
    if missing:
        raise ValueError(f"timeline references unknown source_video_id(s): {missing}")
    return raw_keys


def _produce_cut_video(
    timeline: list[dict], raw_keys: dict[uuid.UUID, str], tmp_dir: Path
) -> Path:
    local_source_paths: dict[uuid.UUID, Path] = {}
    for sv_id, raw_key in raw_keys.items():
        local_path = tmp_dir / f"source_{sv_id}.mp4"
        download_to_path(raw_key, str(local_path))
        local_source_paths[sv_id] = local_path

    clip_paths = []
    for i, clip in enumerate(timeline):
        sv_id = uuid.UUID(clip["source_video_id"])
        clip_path = tmp_dir / f"clip_{i:04d}.mp4"
        _trim_clip(
            local_source_paths[sv_id], clip_path, clip["source_start"], clip["source_end"]
        )
        clip_paths.append(clip_path)

    cut_output_path = tmp_dir / "cut_output.mp4"
    concat_list_path = tmp_dir / "concat.txt"
    _concat_clips(clip_paths, cut_output_path, concat_list_path)
    return cut_output_path


@celery_app.task(name="workers.tasks.render_dispatch.cut_source_video", bind=True, max_retries=3)
def cut_source_video(self, edit_plan_id: str, job_id: str) -> dict:
    """Pipeline step 6, the ffmpeg half only: cut and concatenate the raw
    source video(s) per an edit plan's `timeline` -- the sole rendering
    authority (ADR-0005). Produces an intermediate "cut" video with no
    captions/zooms. Kept as a standalone task (e.g. for a future raw-cut
    preview); `render_export` below is the full export path used by the
    actual export flow.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        job = session.get(Job, uuid.UUID(job_id))
        edit_plan = session.get(EditPlanRow, uuid.UUID(edit_plan_id))
        if job is None or edit_plan is None:
            raise ValueError(f"edit_plan {edit_plan_id} or job {job_id} not found")

        timeline = edit_plan.plan_json["timeline"]
        if not timeline:
            raise ValueError(f"edit_plan {edit_plan_id} has an empty timeline")

        raw_keys = _resolve_raw_keys(session, timeline)
        project_id = edit_plan.project_id

        job.status = JobStatus.RUNNING
        session.commit()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cut_output_path = _produce_cut_video(timeline, raw_keys, tmp_dir)
            cut_key = f"renders/{project_id}/{edit_plan_id}/cut.mp4"
            upload_from_path(str(cut_output_path), cut_key)
    except Exception as exc:
        with session_factory() as session:
            job = session.get(Job, uuid.UUID(job_id))
            job.status = JobStatus.FAILED
            job.error = str(exc)[:2000]
            job.retry_count = (job.retry_count or 0) + 1
            session.commit()
        raise

    with session_factory() as session:
        job = session.get(Job, uuid.UUID(job_id))
        job.status = JobStatus.SUCCEEDED
        job.progress_pct = 100
        session.commit()

    return {"edit_plan_id": edit_plan_id, "cut_r2_key": cut_key, "clip_count": len(timeline)}


@celery_app.task(name="workers.tasks.render_dispatch.render_export", bind=True, max_retries=3)
def render_export(self, export_id: str, job_id: str) -> dict:
    """The full export path (pipeline steps 6-7): ffmpeg cut, then hand off
    to the Remotion HTTP service (apps/render-worker) for captions/zooms
    compositing, then persist the final R2 key on the Export row.

    render-worker runs as a separate container/process (Node, needs headless
    Chromium) -- reached over HTTP rather than via Docker socket mounting or
    subprocess, which would need the Python worker container to have Docker
    access to a sibling container (more privilege than this needs, and a
    real security surface for a solo-founder-scale deployment).
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        job = session.get(Job, uuid.UUID(job_id))
        export = session.get(Export, uuid.UUID(export_id))
        if job is None or export is None:
            raise ValueError(f"export {export_id} or job {job_id} not found")

        timeline_row = session.get(Timeline, export.timeline_id)
        if timeline_row is None:
            raise ValueError(
                f"export {export_id} references missing timeline {export.timeline_id}"
            )

        state = timeline_row.state_json
        timeline = state["timeline"]
        if not timeline:
            raise ValueError(f"export {export_id}'s timeline is empty")
        subtitles = state.get("subtitles", [])
        zooms = state.get("zooms", [])

        raw_keys = _resolve_raw_keys(session, timeline)
        project_id = export.project_id

        job.status = JobStatus.RUNNING
        session.commit()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cut_output_path = _produce_cut_video(timeline, raw_keys, tmp_dir)
            cut_key = f"renders/{project_id}/{export_id}/cut.mp4"
            upload_from_path(str(cut_output_path), cut_key)

        final_key = f"renders/{project_id}/{export_id}/final.mp4"
        response = httpx.post(
            f"{settings.render_worker_url}/render",
            json={
                "inputKey": cut_key,
                "outputKey": final_key,
                "subtitles": subtitles,
                "zooms": zooms,
            },
            timeout=RENDER_WORKER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("outputKey") != final_key:
            raise ValueError(f"render-worker returned unexpected response: {result}")
    except Exception as exc:
        with session_factory() as session:
            job = session.get(Job, uuid.UUID(job_id))
            job.status = JobStatus.FAILED
            job.error = str(exc)[:2000]
            job.retry_count = (job.retry_count or 0) + 1
            session.commit()
        raise

    with session_factory() as session:
        export = session.get(Export, uuid.UUID(export_id))
        job = session.get(Job, uuid.UUID(job_id))
        export.r2_key_output = final_key
        job.status = JobStatus.SUCCEEDED
        job.progress_pct = 100
        session.commit()

    return {"export_id": export_id, "r2_key_output": final_key}
