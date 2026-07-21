import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_owned_project
from app.schemas.job import JobRead
from app.services.job_service import get_job_for_project, list_jobs_for_project
from db_models.models.project import Project

router = APIRouter(prefix="/projects/{project_id}/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_all(
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> list:
    return await list_jobs_for_project(db, project_id=project.id)


@router.get("/{job_id}", response_model=JobRead)
async def get_one(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    project: Project = Depends(get_owned_project),
) -> JobRead:
    job = await get_job_for_project(db, project_id=project.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
