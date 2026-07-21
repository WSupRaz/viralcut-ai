import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import celery_client
from app.services.job_service import create_job
from db_models.models.edit_plan import EditPlan
from db_models.models.enums import JobType, SourceVideoStatus
from db_models.models.job import Job
from db_models.models.source_video import SourceVideo


class NoSourceVideosError(Exception):
    pass


class SourceVideosNotReadyError(Exception):
    def __init__(self, not_ready_count: int) -> None:
        self.not_ready_count = not_ready_count
        super().__init__(f"{not_ready_count} source video(s) not metadata-ready yet")


async def trigger_edit_plan_generation(db: AsyncSession, *, project_id: uuid.UUID) -> Job:
    source_videos = (
        (await db.execute(select(SourceVideo).where(SourceVideo.project_id == project_id)))
        .scalars()
        .all()
    )
    if not source_videos:
        raise NoSourceVideosError(str(project_id))

    not_ready = [sv for sv in source_videos if sv.status != SourceVideoStatus.METADATA_READY]
    if not_ready:
        raise SourceVideosNotReadyError(len(not_ready))

    job = await create_job(db, project_id=project_id, job_type=JobType.EDIT_PLAN)
    celery_client.send_task(
        "workers.tasks.edit_plan.generate_edit_plan", args=[str(project_id), str(job.id)]
    )
    return job


async def list_edit_plans_for_project(db: AsyncSession, *, project_id: uuid.UUID) -> list[EditPlan]:
    result = await db.execute(
        select(EditPlan).where(EditPlan.project_id == project_id).order_by(EditPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def get_edit_plan_for_project(
    db: AsyncSession, *, project_id: uuid.UUID, edit_plan_id: uuid.UUID
) -> EditPlan | None:
    result = await db.execute(
        select(EditPlan).where(EditPlan.id == edit_plan_id, EditPlan.project_id == project_id)
    )
    return result.scalar_one_or_none()
