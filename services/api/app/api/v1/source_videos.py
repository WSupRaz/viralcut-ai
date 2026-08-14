import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_owned_project
from app.schemas.job import JobRead
from app.schemas.source_video import (
    SourceVideoRead,
    SourceVideoUploadPartRead,
    SourceVideoUploadPartUrlResponse,
    SourceVideoUploadStartRequest,
    SourceVideoUploadStartResponse,
)
from app.services.source_video_service import (
    FileTooLargeError,
    NotAVideoError,
    ObjectMissingError,
    UnsupportedVideoTypeError,
    UploadIncompleteError,
    UploadNotFoundError,
    UploadSessionExpiredError,
    complete_source_video_upload,
    delete_source_video,
    generate_part_upload_url,
    get_source_video_for_project,
    get_upload_parts,
    list_source_videos,
    retry_source_video_processing,
    start_source_video_upload,
)
from db_models.models.project import Project

router = APIRouter(prefix="/projects/{project_id}/source-videos", tags=["source-videos"])


@router.post(
    "/uploads/start",
    response_model=SourceVideoUploadStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_upload(
    payload: SourceVideoUploadStartRequest,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> SourceVideoUploadStartResponse:
    """Begin a resumable multipart upload for a new source video. The browser
    then PUTs parts to /part-url?part_number=N URLs and finishes with
    /uploads/complete. Returns chunk geometry (part_size/part_count) so the
    client never needs to know storage internals."""
    try:
        return await start_source_video_upload(db, project_id=project.id, data=payload)
    except UnsupportedVideoTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type: {exc}. Allowed: mp4, mov, m4v.",
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc


@router.get(
    "/{source_video_id}/uploads/parts",
    response_model=list[SourceVideoUploadPartRead],
)
async def upload_parts(
    source_video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> list[SourceVideoUploadPartRead]:
    """Parts already uploaded for a pending upload session -- used by a
    resuming client to skip chunks that already made it (upload survives a
    page refresh or a temporary network drop)."""
    try:
        parts = await get_upload_parts(
            db, project_id=project.id, source_video_id=source_video_id
        )
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UploadSessionExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [SourceVideoUploadPartRead(part_number=p["part_number"], size=p["size"]) for p in parts]


@router.get(
    "/{source_video_id}/uploads/part-url",
    response_model=SourceVideoUploadPartUrlResponse,
)
async def part_url(
    source_video_id: uuid.UUID,
    part_number: int = Query(ge=1),
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> SourceVideoUploadPartUrlResponse:
    """Freshly-signed PUT URL for one part. Signed per request so a URL can
    never outlive its intended use; the client re-requests on retry/resume."""
    try:
        upload_url = await generate_part_upload_url(
            db, project_id=project.id, source_video_id=source_video_id, part_number=part_number
        )
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UploadSessionExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return SourceVideoUploadPartUrlResponse(part_number=part_number, upload_url=upload_url)


@router.post(
    "/{source_video_id}/uploads/complete",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def complete_upload(
    source_video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> JobRead:
    """Verify + assemble the uploaded parts server-side (no bytes through
    this process), then enqueue the proxy task with a storage reference."""
    try:
        return await complete_source_video_upload(
            db, project_id=project.id, source_video_id=source_video_id
        )
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UploadSessionExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (UploadIncompleteError, NotAVideoError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/{source_video_id}/retry",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_processing(
    source_video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> JobRead:
    """Re-run processing for a source video whose job failed. Verifies the
    object actually exists in storage first -- no blind re-enqueues."""
    try:
        return await retry_source_video_processing(
            db, project_id=project.id, source_video_id=source_video_id
        )
    except UploadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ObjectMissingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[SourceVideoRead])
async def list_all(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> list:
    return await list_source_videos(db, project_id=project.id)


@router.delete("/{source_video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    source_video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> None:
    source_video = await get_source_video_for_project(
        db, project_id=project.id, source_video_id=source_video_id
    )
    if source_video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source video not found")
    await delete_source_video(db, source_video=source_video)
