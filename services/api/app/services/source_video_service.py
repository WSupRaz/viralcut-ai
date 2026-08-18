import uuid
from datetime import datetime, timedelta, timezone

from botocore.exceptions import BotoCoreError, ClientError
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


class StorageUnavailableError(Exception):
    """The object store rejected or failed a call we cannot recover from
    here (transient 5xx, InvalidPart, EntityTooSmall...). Distinct from an
    expired session so the caller can tell 'retry this' from 'start over',
    and so it never surfaces as an opaque 500."""


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


async def _recover_pending_uploads(db: AsyncSession, *, project_id: uuid.UUID) -> None:
    """Heal rows left stuck by a lost complete response.

    A pending row whose object is already fully assembled in storage is a
    finished upload that never got acknowledged. Left alone it stays
    upload_pending forever, stays invisible in the clip list, and still counts
    against the per-project clip limit -- so a few of them lock the user out of
    uploading at all. Sweep them whenever a new upload starts."""
    result = await db.execute(
        select(SourceVideo).where(
            SourceVideo.project_id == project_id,
            SourceVideo.upload_id.is_not(None),
        )
    )
    for pending in result.scalars().all():
        try:
            if object_size(pending.r2_key_raw) == pending.size_bytes:
                await _finalize_assembled_upload(db, source_video=pending)
        except Exception as exc:  # noqa: BLE001
            # Recovery is opportunistic -- never block a new upload because an
            # old row could not be healed. It stays pending and is retried on
            # the next start, or aged out by the abandoned-upload sweep.
            print(f"[upload-recovery] {pending.id}: {exc}", flush=True)


async def _reusable_pending_upload(
    db: AsyncSession, *, project_id: uuid.UUID, filename: str, size_bytes: int
) -> SourceVideo | None:
    """An open session for the very same file, so a repeat upload resumes it
    instead of starting a parallel one. Without this, every retry created a
    fresh row and re-sent the whole file -- duplicates accumulate, each one
    consuming a clip slot."""
    result = await db.execute(
        select(SourceVideo)
        .where(
            SourceVideo.project_id == project_id,
            SourceVideo.upload_id.is_not(None),
            SourceVideo.original_filename == filename,
            SourceVideo.size_bytes == size_bytes,
        )
        .order_by(SourceVideo.created_at.desc())
    )
    candidates = list(result.scalars().all())
    if not candidates:
        return None

    # Keep the newest; older duplicates of the same file are dead weight.
    keep, *duplicates = candidates
    for dupe in duplicates:
        try:
            abort_multipart_upload(dupe.r2_key_raw, dupe.upload_id)
            delete_object(dupe.r2_key_raw)
        except Exception:  # noqa: BLE001 -- best effort; the row is what matters
            pass
        await db.delete(dupe)
    if duplicates:
        await db.commit()
    return keep


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

    # Housekeeping runs BEFORE the clip-limit check, not after: stuck and
    # abandoned rows count toward the limit, so a project holding a few of them
    # is locked out of uploading entirely -- and the fix for those rows lives
    # right here. Checking the limit first would make the lockout permanent.
    await _cleanup_abandoned_uploads(db, project_id=project_id)
    await _recover_pending_uploads(db, project_id=project_id)

    # Same file already mid-upload? Hand back that session so the client
    # resumes it rather than uploading a second copy alongside it. Also runs
    # before the limit check -- resuming adds no new clip.
    existing = await _reusable_pending_upload(
        db, project_id=project_id, filename=data.filename, size_bytes=data.size_bytes
    )
    if existing is not None:
        return SourceVideoUploadStartResponse(
            source_video_id=existing.id,
            upload_id=existing.upload_id,
            r2_key=existing.r2_key_raw,
            part_size=MULTIPART_PART_SIZE_BYTES,
            part_count=compute_multipart_part_count(existing.size_bytes),
        )

    # Count finished uploads only. A row with an open multipart session is an
    # attempt, not a clip: the UI hides those rows, so counting them let a few
    # failed attempts fill the quota with things the user could neither see nor
    # delete -- locked out of a project without ever completing one upload.
    clip_count = await db.execute(
        select(func.count())
        .select_from(SourceVideo)
        .where(
            SourceVideo.project_id == project_id,
            SourceVideo.upload_id.is_(None),
        )
    )
    if clip_count.scalar_one() >= plan_limits.max_clips_per_project:
        raise ClipLimitError(plan_limits.max_clips_per_project, plan)

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
    result = await db.execute(
        select(SourceVideo).where(
            SourceVideo.id == source_video_id,
            SourceVideo.project_id == project_id,
        )
    )
    source_video = result.scalar_one_or_none()
    if source_video is None:
        raise UploadNotFoundError(str(source_video_id))
    if source_video.upload_id is None:
        # Already completed. The client only calls this again because a
        # previous response never arrived, so answer with the job that call
        # created instead of a 404 it cannot act on.
        return await _proxy_job_for(db, source_video=source_video)

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


async def _finalize_assembled_upload(db: AsyncSession, *, source_video: SourceVideo) -> Job:
    """Mark a row done when the object is already assembled in storage.

    Reached when the multipart session no longer exists. That has two very
    different causes: the session was aborted/expired, or a previous complete
    call already assembled the object and only its HTTP response was lost.
    CompleteMultipartUpload on a multi-hundred-megabyte file takes long enough
    that a dropped response is routine, so assuming the first meaning strands a
    fully-uploaded object behind a row that can never leave upload_pending --
    and every retry adds another one. Ask storage which case it is."""
    try:
        stored_size = object_size(source_video.r2_key_raw)
    except (ClientError, BotoCoreError) as exc:
        raise StorageUnavailableError(
            f"Could not reach storage to check the upload ({type(exc).__name__}). "
            "Try finishing again in a moment."
        ) from exc
    if stored_size is None:
        # Genuinely gone: nothing was ever assembled.
        raise UploadSessionExpiredError(str(source_video.id))
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
    return await _proxy_job_for(db, source_video=source_video)


async def complete_source_video_upload(
    db: AsyncSession, *, project_id: uuid.UUID, source_video_id: uuid.UUID
) -> Job:
    """Verify every part arrived (right count, right sizes), assemble the
    object server-side (S3 CompleteMultipartUpload -- no bytes through this
    process), sanity-check it looks like a video, then enqueue the proxy
    task. The Celery task receives only IDs -- the raw binary never touches
    Redis or Postgres, and never this process's memory."""
    result = await db.execute(
        select(SourceVideo).where(
            SourceVideo.id == source_video_id,
            SourceVideo.project_id == project_id,
        )
    )
    source_video = result.scalar_one_or_none()
    if source_video is None:
        raise UploadNotFoundError(str(source_video_id))
    if source_video.upload_id is None:
        # Already completed. The client only calls this again because a
        # previous response never arrived, so answer with the job that call
        # created instead of a 404 it cannot act on.
        return await _proxy_job_for(db, source_video=source_video)

    part_count = compute_multipart_part_count(source_video.size_bytes)

    try:
        parts = list_parts(source_video.r2_key_raw, source_video.upload_id)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchUpload", "NoSuchKey", "404"):
            # Completing is idempotent: if the object is already assembled,
            # this is a repeat of a call that succeeded but lost its response.
            return await _finalize_assembled_upload(db, source_video=source_video)
        raise StorageUnavailableError(
            f"Storage could not list the uploaded parts ({code or 'unknown error'}). "
            "Your file is still uploaded -- try finishing again in a moment."
        ) from exc
    except BotoCoreError as exc:
        raise StorageUnavailableError(
            f"Could not reach storage to verify the upload ({type(exc).__name__}). "
            "Your file is still uploaded -- try finishing again in a moment."
        ) from exc

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
    # Assembling and verifying the object are calls to the object store, and
    # any of them can fail for reasons that are not the client's fault: a
    # transient 5xx from the provider, InvalidPart, EntityTooSmall. Left
    # unhandled these became a bare 500, which a browser cannot even read
    # (ServerErrorMiddleware sits outside CORS), so the upload just "failed"
    # with no explanation after every byte had already arrived.
    try:
        complete_multipart_upload(source_video.r2_key_raw, source_video.upload_id, ordered)
        stored_size = object_size(source_video.r2_key_raw)
        is_video = head_is_video_container(source_video.r2_key_raw)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchUpload", "NoSuchKey", "404"):
            raise UploadSessionExpiredError(str(source_video_id)) from exc
        raise StorageUnavailableError(
            f"Storage rejected the upload ({code or 'unknown error'}). "
            "Your file is still uploaded -- try finishing again in a moment."
        ) from exc
    except BotoCoreError as exc:
        # ReadTimeoutError and friends. Assembling a large multipart object can
        # outlast any client-side budget while still succeeding at the
        # provider, so this is explicitly retryable: the next attempt finds the
        # finished object and finalises via _finalize_assembled_upload.
        raise StorageUnavailableError(
            f"Storage is still assembling the upload ({type(exc).__name__}). "
            "Your file is uploaded -- try finishing again in a moment."
        ) from exc

    if stored_size != source_video.size_bytes:
        raise UploadIncompleteError(
            f"Uploaded object is {stored_size} bytes but {source_video.size_bytes} "
            "were declared; re-upload the file."
        )
    if not is_video:
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


async def _proxy_job_for(db: AsyncSession, *, source_video: SourceVideo) -> Job:
    """The proxy job already queued for this video, if any.

    Completing is retried by the client whenever a response goes missing, so
    it has to be safe to call twice. Blindly enqueueing again would give one
    clip a second transcode -- the same pile-up that filled the queue with
    duplicate jobs for a single video."""
    result = await db.execute(
        select(Job)
        .where(Job.source_video_id == source_video.id, Job.type == JobType.PROXY)
        .order_by(Job.created_at.desc())
    )
    existing = result.scalars().first()
    if existing is not None:
        return existing
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
