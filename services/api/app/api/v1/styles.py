from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.style import StyleRead
from app.services.style_service import list_styles
from db_models.models.user import User

router = APIRouter(prefix="/styles", tags=["styles"])


@router.get("", response_model=list[StyleRead])
async def list_all(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list:
    return await list_styles(db)
