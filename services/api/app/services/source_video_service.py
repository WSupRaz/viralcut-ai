import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import send_task
from app.schemas.source_video import SourceVideoPresignRequest, SourceVideoPresignResponse
from app.services.job_service import create_job
from app.services.storage import (
    ALLOWED_VIDEO_CONTENT_TYPES,
    build_raw_video_key,
    generate_presigned_upload_url,
)
from db_models.models.enums import JobType
from db_models.models.job import Job
from db_models.models.source_video import SourceVideo


class UnsupportedVideoTypeError(Exception):
    pass


async def presign_source_video_upload(
    db: AsyncSession, *, project_id: uuid.UUID, data: SourceVideoPresignRequest
) -> SourceVideoPresignResponse:
    if data.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise UnsupportedVideoTypeError(data.content_type)

    order_index_result = await db.execute(
        select(func.count()).select_from(SourceVideo).where(SourceVideo.project_id == project_id)
    )
    order_index = order_index_result.scalar_one()

    r2_key = build_raw_video_key(project_id, data.filename)
    source_video = SourceVideo(
        project_id=project_id,
        r2_key_raw=r2_key,
        order_index=order_index,
    )
    db.add(source_video)
    await db.commit()
    await db.refresh(source_video)

    upload_url = generate_presigned_upload_url(r2_key, data.content_type)

    return SourceVideoPresignResponse(
        source_video_id=source_video.id, upload_url=upload_url, r2_key=r2_key
    )


async def confirm_source_video_upload(
    db: AsyncSession, *, source_video: SourceVideo
) -> Job:
    """Client calls this once its direct-to-R2 PUT succeeds. Enqueues the
    proxy task; proxy chains into metadata extraction on success, but edit-
    plan generation stays an explicit user action (POST .../edit-plan) since
    it depends on style/instructions the user may still be setting."""
    job = await create_job(db, project_id=source_video.project_id, job_type=JobType.PROXY)
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
