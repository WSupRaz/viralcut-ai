import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plan_limits import PlanLimits, limits_for
from app.schemas.project import ProjectCreate, ProjectUpdate
from db_models.models.enums import PlanTier
from db_models.models.project import Project


class ProjectLimitError(Exception):
    def __init__(self, limit: int, tier: PlanTier) -> None:
        self.limit = limit
        self.tier = tier
        super().__init__(
            f"Your {tier.value} plan allows {limit} project(s). "
            "Delete one or upgrade to create more."
        )


async def count_projects(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).select_from(Project).where(Project.user_id == user_id)
    )
    return result.scalar_one()


async def create_project(db: AsyncSession, *, user_id: uuid.UUID, data: ProjectCreate, plan: PlanTier) -> Project:
    limits: PlanLimits = limits_for(plan)
    if await count_projects(db, user_id=user_id) >= limits.max_projects:
        raise ProjectLimitError(limits.max_projects, plan)

    project = Project(
        user_id=user_id,
        title=data.title,
        target_aspect_ratio=data.target_aspect_ratio,
        style_id=data.style_id,
        instructions=data.instructions,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession, *, user_id: uuid.UUID) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def get_project_for_user(
    db: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_project(db: AsyncSession, *, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, *, project: Project) -> None:
    await db.delete(project)
    await db.commit()
