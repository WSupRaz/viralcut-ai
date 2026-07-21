import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db_models.models.enums import JobStatus, JobType
from db_models.models.job import Job


async def create_job(
    db: AsyncSession, *, project_id: uuid.UUID, job_type: JobType
) -> Job:
    job = Job(project_id=project_id, type=job_type, status=JobStatus.QUEUED)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_job_for_project(
    db: AsyncSession, *, project_id: uuid.UUID, job_id: uuid.UUID
) -> Job | None:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.project_id == project_id)
    )
    return result.scalar_one_or_none()


async def list_jobs_for_project(db: AsyncSession, *, project_id: uuid.UUID) -> list[Job]:
    result = await db.execute(
        select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
    )
    return list(result.scalars().all())
