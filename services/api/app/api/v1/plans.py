from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.plan_limits import PLAN_LIMITS, PlanLimits, limits_for
from db_models.models.enums import PlanTier
from db_models.models.user import User

router = APIRouter(prefix="/plans", tags=["plans"])

# Order tiers cheapest-first for the pricing page.
PUBLIC_ORDER: list[PlanTier] = [
    PlanTier.FREE,
    PlanTier.CREATOR,
    PlanTier.PRO,
    PlanTier.BUSINESS,
]


@router.get("")
async def list_plans() -> dict:
    """Every tier and its limits -- drives the public pricing page. No auth:
    the limits themselves are not secrets; only *which* tier a user is on is
    private (see /plans/me)."""
    return {
        "plans": [limits_for(tier).to_dict() for tier in PUBLIC_ORDER],
    }


@router.get("/me")
async def my_plan(current_user: User = Depends(get_current_user)) -> dict:
    """The caller's current tier + limits, so the app UI can show what they
    get, gate uploads client-side, and show what upgrading unlocks."""
    limits: PlanLimits = limits_for(current_user.plan)
    return {
        "tier": current_user.plan.value,
        "limits": limits.to_dict(),
    }
