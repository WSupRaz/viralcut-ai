from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db_models.models.style import Style


async def list_styles(db: AsyncSession) -> list[Style]:
    result = await db.execute(select(Style).order_by(Style.name))
    return list(result.scalars().all())
