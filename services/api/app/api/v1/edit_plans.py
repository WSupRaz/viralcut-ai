from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_owned_project
from app.schemas.edit_plan import EditPlanRead
from app.schemas.job import JobRead
from app.services.edit_plan_service import (
    NoSourceVideosError,
    SourceVideosNotReadyError,
    list_edit_plans_for_project,
    trigger_edit_plan_generation,
)
from db_models.models.project import Project

router = APIRouter(prefix="/projects/{project_id}/edit-plans", tags=["edit-plans"])


@router.post("", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
async def generate(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> JobRead:
    try:
        return await trigger_edit_plan_generation(db, project_id=project.id)
    except NoSourceVideosError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no source videos"
        ) from exc
    except SourceVideosNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{exc.not_ready_count} source video(s) are not metadata-ready yet",
        ) from exc


@router.get("", response_model=list[EditPlanRead])
async def list_all(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> list:
    return await list_edit_plans_for_project(db, project_id=project.id)
