import uuid
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import send_task
from app.core.config import settings
from app.core.plan_limits import PlanLimits, limits_for
from app.schemas.source_video import (
    SourceVideoUploadStartRequest,
    SourceVideoUploadStartResponse,
)
from app.services.job_service import create_job
from app.services.storage import (
    ALLOWED_VIDEO_CONTENT_TYPES,
    MULTIPART_PART_SIZE_BYTES,
    abort_multipart_upload,
    build_raw_video_key,
    complete_multipart_upload,
    compute_multipart_part_count,
    create_multipart_upload,
    delete_object,
    generate_presigned_part_upload_url,
    head_is_video_container,
    list_parts,
    object_size,
)
from db_models.models.enums import JobType, PlanTier
from db_models.models.job import Job
from db_models.models.source_video import SourceVideo


class UnsupportedVideoTypeError(Exception):
    pass


class FileTooLargeError(Exception):
    def __init__(self, size_bytes: int, cap: int | None = None, plan: PlanTier | None = None) -> None:
        self.size_bytes = size_bytes
        cap = cap or settings.max_upload_bytes
        super().__init__(
            f"File is {size_bytes} bytes; your plan allows up to {cap} bytes per file"
        )


class ClipLimitError(Exception):
    def __init__(self, limit: int, plan: PlanTier) -> None:
        self.limit = limit
        self.plan = plan
        super().__init__(
            f"Your {plan.value} plan allows {limit} clip(s) per project. "
            "Remove one or upgrade to upload more."
        )


class UploadNotFoundError(Exception):
    pass


class UploadSessionExpiredError(Exception):
    pass


class UploadIncompleteError(Exception):
    pass


class NotAVideoError(Exception):
    pass


class ObjectMissingError(Exception):
    pass


def _upload_cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(
        hours=settings.abandoned_upload_ttl_hours
    )


async def _cleanup_abandoned_uploads(db: AsyncSession, *, project_id: uuid.UUID) -> None:
    """Abort + delete pending (never-completed) upload sessions older than
    the TTL, run when a new upload starts in the same project. Without this,
    a browser that died mid-upload (tab closed hard, laptop lost) would leak
    the multipart upload + partial object forever. Production should also set
    a bucket lifecycle rule; this is the in-app safety net."""
    result = await db.execute(
        select(SourceVideo).where(
            SourceVideo.project_id == project_id,
            SourceVideo.upload_id.is_not(None),
            SourceVideo.created_at < _upload_cutoff(),
        )
    )
    for stale in result.scalars().all():
        abort_multipart_upload(stale.r2_key_raw, stale.upload_id)
        delete_object(stale.r2_key_raw)
        await db.delete(stale)
    await db.commit()


async def start_source_video_upload(
    db: AsyncSession, *, project_id: uuid.UUID, data: SourceVideoUploadStartRequest, plan: PlanTier
) -> SourceVideoUploadStartResponse:
    """Begin a resumable multipart upload. Creates the SourceVideo row (in
    `uploaded` status) and the server-side multipart session; the browser
    then PUTs each part to a freshly-signed URL and calls complete when done.
    The upload can be resumed after a network drop or page refresh by asking
    for the already-uploaded parts (list_parts) and re-uploading the rest."""
    if data.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise UnsupportedVideoTypeError(data.content_type)

    # Effective cap = min(global hard cap, what the user's plan allows).
    plan_limits: PlanLimits = limits_for(plan)
    effective_cap = min(settings.max_upload_bytes, plan_limits.max_upload_bytes)
    if data.size_bytes > effective_cap:
        raise FileTooLargeError(data.size_bytes, cap=effective_cap, plan=plan)

    clip_count = await db.execute(
        select(func.count()).select_from(SourceVideo).where(SourceVideo.project_id == project_id)
    )
    if clip_count.scalar_one() >= plan_limits.max_clips_per_project:
        raise ClipLimitError(plan_limits.max_clips_per_project, plan)

    await _cleanup_abandoned_uploads(db, project_id=project_id)

    order_index_result = await db.execute(
        select(func.count()).select_from(SourceVideo).where(SourceVideo.project_id == project_id)
    )
    order_index = order_index_result.scalar_one()

    r2_key = build_raw_video_key(project_id, data.filename)
    part_count = compute_multipart_part_count(data.size_bytes)

    source_video = SourceVideo(
        project_id=project_id,
        r2_key_raw=r2_key,
        order_index=order_index,
        size_bytes=data.size_bytes,
        original_filename=data.filename,
        content_type=data.content_type,
    )
    db.add(source_video)
    await db.commit()
    await db.refresh(source_video)

    upload_id = create_multipart_upload(r2_key, data.content_type)
    source_video.upload_id = upload_id
    await db.commit()

    return SourceVideoUploadStartResponse(
        source_video_id=source_video.id,
        upload_id=upload_id,
        r2_key=r2_key,
        part_size=MULTIPART_PART_SIZE_BYTES,
        part_count=part_count,
    )


async def _get_pending_upload(
    db: AsyncSession, *, project_id: uuid.UUID, source_video_id: uuid.UUID
) -> SourceVideo:
    source_video = await db.execute(
        select(SourceVideo).where(
            SourceVideo.id == source_video_id,
            SourceVideo.project_id == project_id,
        )
    )
    source_video = source_video.scalar_one_or_none()
    if source_video is None or source_video.upload_id is None:
        raise UploadNotFoundError(str(source_video_id))
    return source_video


async def get_upload_parts(
    db: AsyncSession, *, project_id: uuid.UUID, source_video_id: uuid.UUID
) -> list[dict]:
    """Parts already on the server for a pending upload, so a resuming client
    can skip re-uploading them. Raises UploadSessionExpiredError if the
    multipart session vanished server-side (aborted/expired) -- the client
    should restart the upload."""
    source_video = await _get_pending_upload(
        db, project_id=project_id, source_video_id=source_video_id
    )
    try:
        parts = list_parts(source_video.r2_key_raw, source_video.upload_id)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchUpload", "NoSuchKey", "404"):
            raise UploadSessionExpiredError(str(source_video_id)) from exc
        raise
    return sorted(parts, key=lambda p: p["part_number"])


async def generate_part_upload_url(
    db: AsyncSession, *, project_id: uuid.UUID, source_video_id: uuid.UUID, part_number: int
) -> str:
    source_video = await _get_pending_upload(
        db, project_id=project_id, source_video_id=source_video_id
    )
    part_count = compute_multipart_part_count(source_video.size_bytes)
    if part_number < 1 or part_number > part_count:
        raise UploadNotFoundError(f"part {part_number} out of range 1..{part_count}")
    try:
        return generate_presigned_part_upload_url(
            source_video.r2_key_raw, source_video.upload_id, part_number
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchUpload", "NoSuchKey", "404"):
            raise UploadSessionExpiredError(str(source_video_id)) from exc
        raise


async def complete_source_video_upload(
    db: AsyncSession, *, project_id: uuid.UUID, source_video_id: uuid.UUID
) -> Job:
    """Verify every part arrived (right count, right sizes), assemble the
    object server-side (S3 CompleteMultipartUpload -- no bytes through this
    process), sanity-check it looks like a video, then enqueue the proxy
    task. The Celery task receives only IDs -- the raw binary never touches
    Redis or Postgres, and never this process's memory."""
    source_video = await _get_pending_upload(
        db, project_id=project_id, source_video_id=source_video_id
    )
    part_count = compute_multipart_part_count(source_video.size_bytes)

    try:
        parts = list_parts(source_video.r2_key_raw, source_video.upload_id)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchUpload", "NoSuchKey", "404"):
            raise UploadSessionExpiredError(str(source_video_id)) from exc
        raise

    by_number = {p["part_number"]: p for p in parts}
    missing = [n for n in range(1, part_count + 1) if n not in by_number]
    if missing:
        raise UploadIncompleteError(
            f"Upload incomplete: {len(missing)} part(s) missing "
            f"(first missing: {missing[0]}). Resume the upload and try again."
        )

    # Every part except the last must be exactly the chunk size; the last is
    # the remainder (size_bytes - (part_count-1) * part_size).
    last_part_size = source_video.size_bytes - (part_count - 1) * MULTIPART_PART_SIZE_BYTES
    for n in range(1, part_count + 1):
        expected = last_part_size if n == part_count else MULTIPART_PART_SIZE_BYTES
        if by_number[n]["size"] != expected:
            raise UploadIncompleteError(
                f"Part {n} has size {by_number[n]['size']} bytes, expected {expected}. "
                "The file changed or was corrupted mid-upload; re-upload it."
            )

    ordered = [by_number[n] for n in range(1, part_count + 1)]
    complete_multipart_upload(source_video.r2_key_raw, source_video.upload_id, ordered)

    stored_size = object_size(source_video.r2_key_raw)
    if stored_size != source_video.size_bytes:
        raise UploadIncompleteError(
            f"Uploaded object is {stored_size} bytes but {source_video.size_bytes} "
            "were declared; re-upload the file."
        )
    if not head_is_video_container(source_video.r2_key_raw):
        raise NotAVideoError(
            "Uploaded file does not look like an MP4/MOV video. Check the file and re-upload."
        )

    source_video.upload_id = None
    await db.commit()

    return await _enqueue_proxy(db, source_video=source_video)


async def retry_source_video_processing(
    db: AsyncSession, *, project_id: uuid.UUID, source_video_id: uuid.UUID
) -> Job:
    """Manual retry for a source video whose processing failed: re-enqueues
    the proxy task (idempotent -- it re-downloads, re-transcodes, overwrites
    the same proxy key). Only valid once the upload actually landed in
    storage; unlike the old confirm-upload, this checks first."""
    source_video = await db.execute(
        select(SourceVideo).where(
            SourceVideo.id == source_video_id,
            SourceVideo.project_id == project_id,
        )
    )
    source_video = source_video.scalar_one_or_none()
    if source_video is None:
        raise UploadNotFoundError(str(source_video_id))

    if object_size(source_video.r2_key_raw) is None:
        raise ObjectMissingError(
            "Source video is not in storage. Re-upload it before retrying processing."
        )

    return await _enqueue_proxy(db, source_video=source_video)


async def _enqueue_proxy(db: AsyncSession, *, source_video: SourceVideo) -> Job:
    """Create the PROXY job (linked to its source video) and hand the worker
    a reference (IDs only)."""
    job = await create_job(
        db,
        project_id=source_video.project_id,
        job_type=JobType.PROXY,
        source_video_id=source_video.id,
    )
    send_task(
        "workers.tasks.proxy.generate_proxy", args=[str(source_video.id), str(job.id)]
    )
    return job


async def list_source_videos(db: AsyncSession, *, project_id: uuid.UUID) -> list[SourceVideo]:
    result = await db.execute(
        select(SourceVideo)
        .where(SourceVideo.project_id == project_id)
        .order_by(SourceVideo.order_index)
    )
    return list(result.scalars().all())


async def get_source_video_for_project(
    db: AsyncSession, *, project_id: uuid.UUID, source_video_id: uuid.UUID
) -> SourceVideo | None:
    result = await db.execute(
        select(SourceVideo).where(
            SourceVideo.id == source_video_id, SourceVideo.project_id == project_id
        )
    )
    return result.scalar_one_or_none()


async def delete_source_video(db: AsyncSession, *, source_video: SourceVideo) -> None:
    # Best-effort: a multipart-upload row can exist with no object behind it
    # at all (the browser may never have uploaded a single part). The DB row
    # is the part the user is actually asking to remove, so a storage-side
    # hiccup shouldn't block that. If a multipart session is still open,
    # abort it so the partial parts don't linger server-side.
    if source_video.upload_id:
        abort_multipart_upload(source_video.r2_key_raw, source_video.upload_id)
    for key in filter(None, [source_video.r2_key_raw, source_video.r2_key_proxy]):
        try:
            delete_object(key)
        except Exception:
            pass

    await db.delete(source_video)
    await db.commit()
