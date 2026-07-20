import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.project import ProjectCreate, ProjectUpdate
from db_models.models.project import Project


async def create_project(db: AsyncSession, *, user_id: uuid.UUID, data: ProjectCreate) -> Project:
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
