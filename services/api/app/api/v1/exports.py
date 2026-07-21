import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_owned_project
from app.schemas.export import ExportCreate, ExportRead
from app.services.export_service import (
    EditPlanNotFoundError,
    UnsupportedAspectRatioError,
    create_export,
    get_export_for_project,
    list_exports_for_project,
)
from db_models.models.project import Project

router = APIRouter(prefix="/projects/{project_id}/exports", tags=["exports"])


@router.post("", response_model=ExportRead, status_code=status.HTTP_202_ACCEPTED)
async def create(
    payload: ExportCreate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> ExportRead:
    try:
        export = await create_export(
            db,
            project_id=project.id,
            edit_plan_id=payload.edit_plan_id,
            aspect_ratio=payload.aspect_ratio,
            quality=payload.quality,
        )
    except EditPlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Edit plan not found"
        ) from exc
    except UnsupportedAspectRatioError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Aspect ratio {exc.aspect_ratio} is not supported yet -- only 9:16 in Phase 1",
        ) from exc

    result = await get_export_for_project(db, project_id=project.id, export_id=export.id)
    assert result is not None
    return result


@router.get("", response_model=list[ExportRead])
async def list_all(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> list:
    return await list_exports_for_project(db, project_id=project.id)


@router.get("/{export_id}", response_model=ExportRead)
async def get_one(
    export_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> ExportRead:
    export = await get_export_for_project(db, project_id=project.id, export_id=export_id)
    if export is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return export
