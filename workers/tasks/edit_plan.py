import uuid

from sqlalchemy import select

from db_models.models.edit_plan import EditPlan as EditPlanRow
from db_models.models.enums import EditPlanStatus, JobStatus, SourceVideoStatus
from db_models.models.job import Job
from db_models.models.project import Project
from db_models.models.source_video import SourceVideo
from db_models.models.style import Style
from db_models.models.video_metadata import VideoMetadata
from edit_plan_schema import EditPlan, validate_and_clamp

from workers.celery_app import celery_app
from workers.config import settings
from workers.db import get_session_factory
from workers.providers.llm.claude_provider import ClaudeEditPlanProvider
from workers.providers.llm.openrouter_provider import OpenRouterEditPlanProvider
from workers.providers.llm.prompts import build_system_prompt, build_user_prompt


def _generate_with_fallback(system_prompt: str, user_prompt: str) -> tuple[dict, str]:
    try:
        provider = ClaudeEditPlanProvider()
        return provider.generate(system_prompt, user_prompt), provider.name
    except Exception:
        if not settings.openrouter_api_key:
            raise
        provider = OpenRouterEditPlanProvider()
        return provider.generate(system_prompt, user_prompt), provider.name


@celery_app.task(name="workers.tasks.edit_plan.generate_edit_plan", bind=True, max_retries=3)
def generate_edit_plan(self, project_id: str, job_id: str) -> dict:
    """Pipeline steps 5-6: Claude receives only structured metadata (never
    raw video) and returns a structured edit plan, which is then validated
    and clamped against the real source video durations before being
    trusted (docs/adr/0005-edit-plan-schema.md)."""
    session_factory = get_session_factory()

    with session_factory() as session:
        job = session.get(Job, uuid.UUID(job_id))
        project = session.get(Project, uuid.UUID(project_id))
        if job is None or project is None:
            raise ValueError(f"project {project_id} or job {job_id} not found")

        source_videos = (
            session.execute(
                select(SourceVideo)
                .where(SourceVideo.project_id == project.id)
                .order_by(SourceVideo.order_index)
            )
            .scalars()
            .all()
        )
        if not source_videos:
            raise ValueError(f"project {project_id} has no source videos")

        source_summaries = []
        source_durations: dict[uuid.UUID, float] = {}
        for sv in source_videos:
            if sv.status != SourceVideoStatus.METADATA_READY:
                raise ValueError(
                    f"source_video {sv.id} is not metadata-ready yet (status={sv.status})"
                )
            metadata = session.execute(
                select(VideoMetadata).where(VideoMetadata.source_video_id == sv.id)
            ).scalar_one()
            duration = float(sv.duration_seconds)
            source_durations[sv.id] = duration
            source_summaries.append(
                {
                    "source_video_id": str(sv.id),
                    "order_index": sv.order_index,
                    "duration_seconds": duration,
                    "transcript": metadata.transcript,
                    "scene_changes": metadata.scene_changes,
                    "silences": metadata.silences,
                    "speakers": metadata.speakers,
                }
            )

        style = session.get(Style, project.style_id) if project.style_id else None
        style_rules = style.rules_json if style is not None else {}
        instructions = project.instructions

        job.status = JobStatus.RUNNING
        session.commit()

    try:
        system_prompt = build_system_prompt(style_rules)
        user_prompt = build_user_prompt(source_summaries, instructions)

        raw_plan, provider_name = _generate_with_fallback(system_prompt, user_prompt)

        plan = EditPlan(**raw_plan)
        clamped = validate_and_clamp(plan, source_durations)
    except Exception as exc:
        with session_factory() as session:
            job = session.get(Job, uuid.UUID(job_id))
            job.status = JobStatus.FAILED
            job.error = str(exc)[:2000]
            job.retry_count = (job.retry_count or 0) + 1
            session.commit()
        raise

    with session_factory() as session:
        project = session.get(Project, uuid.UUID(project_id))
        job = session.get(Job, uuid.UUID(job_id))

        edit_plan_row = EditPlanRow(
            project_id=project.id,
            style_id=project.style_id,
            plan_json=clamped.model_dump(mode="json"),
            viral_score=clamped.viral_score.model_dump(mode="json"),
            model=provider_name,
            status=EditPlanStatus.GENERATED,
        )
        session.add(edit_plan_row)

        job.status = JobStatus.SUCCEEDED
        job.progress_pct = 100
        session.commit()

        edit_plan_id = edit_plan_row.id

    return {
        "project_id": project_id,
        "edit_plan_id": str(edit_plan_id),
        "provider": provider_name,
        "timeline_clip_count": len(clamped.timeline),
        "viral_score": clamped.viral_score.model_dump(),
    }
