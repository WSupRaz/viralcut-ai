import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_client import send_task
from app.schemas.export import ExportRead
from app.services.job_service import create_job
from app.services.storage import generate_presigned_get_url
from db_models.models.edit_plan import EditPlan
from db_models.models.enums import AspectRatio, ExportQuality, JobType
from db_models.models.export import Export
from db_models.models.job import Job
from db_models.models.timeline import Timeline


class EditPlanNotFoundError(Exception):
    pass


class UnsupportedAspectRatioError(Exception):
    def __init__(self, aspect_ratio: str) -> None:
        self.aspect_ratio = aspect_ratio
        super().__init__(f"aspect ratio {aspect_ratio} is not supported in Phase 1")


async def create_export(
    db: AsyncSession,
    *,
    project_id: uuid.UUID,
    edit_plan_id: uuid.UUID,
    aspect_ratio: AspectRatio,
    quality: ExportQuality,
) -> Export:
    """Materializes a Timeline row from the chosen edit plan (Phase 1's
    timeline is view-only -- no drag-and-drop editing yet, so this is a 1:1
    copy of plan_json, not a merge with prior edits) and dispatches the full
    export render (workers.tasks.render_dispatch.render_export).

    Only 9:16 is supported in Phase 1 (docs/04-roadmap.md); `quality` is
    accepted but not yet enforced against a specific resolution/bitrate --
    the render uses the cut video's native resolution. Full export matrix is
    Phase 2.
    """
    if aspect_ratio != AspectRatio.VERTICAL:
        raise UnsupportedAspectRatioError(aspect_ratio.value)

    result = await db.execute(
        select(EditPlan).where(EditPlan.id == edit_plan_id, EditPlan.project_id == project_id)
    )
    edit_plan = result.scalar_one_or_none()
    if edit_plan is None:
        raise EditPlanNotFoundError(str(edit_plan_id))

    timeline = Timeline(
        project_id=project_id,
        source_edit_plan_id=edit_plan.id,
        state_json=edit_plan.plan_json,
    )
    db.add(timeline)
    await db.flush()

    job = await create_job(db, project_id=project_id, job_type=JobType.RENDER)

    export = Export(
        project_id=project_id,
        timeline_id=timeline.id,
        aspect_ratio=aspect_ratio,
        quality=quality,
        job_id=job.id,
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)

    send_task(
        "workers.tasks.render_dispatch.render_export", args=[str(export.id), str(job.id)]
    )
    return export


async def get_export_for_project(
    db: AsyncSession, *, project_id: uuid.UUID, export_id: uuid.UUID
) -> ExportRead | None:
    result = await db.execute(
        select(Export).where(Export.id == export_id, Export.project_id == project_id)
    )
    export = result.scalar_one_or_none()
    if export is None:
        return None

    job = await db.get(Job, export.job_id)
    download_url = (
        generate_presigned_get_url(export.r2_key_output) if export.r2_key_output else None
    )

    return ExportRead(
        id=export.id,
        project_id=export.project_id,
        timeline_id=export.timeline_id,
        aspect_ratio=export.aspect_ratio,
        quality=export.quality,
        job_id=export.job_id,
        job_status=job.status,
        r2_key_output=export.r2_key_output,
        download_url=download_url,
        created_at=export.created_at,
    )


async def list_exports_for_project(db: AsyncSession, *, project_id: uuid.UUID) -> list[ExportRead]:
    result = await db.execute(
        select(Export).where(Export.project_id == project_id).order_by(Export.created_at.desc())
    )
    exports = result.scalars().all()
    return [
        await get_export_for_project(db, project_id=project_id, export_id=export.id)
        for export in exports
    ]
