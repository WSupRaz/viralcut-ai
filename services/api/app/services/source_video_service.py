import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.source_video import SourceVideoPresignRequest, SourceVideoPresignResponse
from app.services.storage import (
    ALLOWED_VIDEO_CONTENT_TYPES,
    build_raw_video_key,
    generate_presigned_upload_url,
)
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


async def list_source_videos(db: AsyncSession, *, project_id: uuid.UUID) -> list[SourceVideo]:
    result = await db.execute(
        select(SourceVideo)
        .where(SourceVideo.project_id == project_id)
        .order_by(SourceVideo.order_index)
    )
    return list(result.scalars().all())
