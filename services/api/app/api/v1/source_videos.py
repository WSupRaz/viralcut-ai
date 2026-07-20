from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_owned_project
from app.schemas.source_video import (
    SourceVideoPresignRequest,
    SourceVideoPresignResponse,
    SourceVideoRead,
)
from app.services.source_video_service import (
    UnsupportedVideoTypeError,
    list_source_videos,
    presign_source_video_upload,
)
from db_models.models.project import Project

router = APIRouter(prefix="/projects/{project_id}/source-videos", tags=["source-videos"])


@router.post(
    "/presign-upload",
    response_model=SourceVideoPresignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def presign_upload(
    payload: SourceVideoPresignRequest,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> SourceVideoPresignResponse:
    try:
        return await presign_source_video_upload(db, project_id=project.id, data=payload)
    except UnsupportedVideoTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type: {exc}. Allowed: mp4, mov, m4v.",
        ) from exc


@router.get("", response_model=list[SourceVideoRead])
async def list_all(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> list:
    return await list_source_videos(db, project_id=project.id)
