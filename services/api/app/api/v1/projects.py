import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_owned_project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import (
    create_project,
    delete_project,
    list_projects,
    update_project,
)
from db_models.models.project import Project
from db_models.models.user import User

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Project:
    return await create_project(db, user_id=current_user.id, data=payload)


@router.get("", response_model=list[ProjectRead])
async def list_all(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Project]:
    return await list_projects(db, user_id=current_user.id)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_one(project: Project = Depends(get_owned_project)) -> Project:
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update(
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> Project:
    return await update_project(db, project=project, data=payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> None:
    await delete_project(db, project=project)
