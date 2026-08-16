"""Per-plan tier limits.

The product sells on limits: every plan tier carries caps on the things that
cost real money (storage, transcodes, exports). The enforcement lives in the
service layer (project/source-video/export creation) and the same table is
surfaced to the frontend via GET /plans so the UI can show what a user gets
and what upgrading unlocks.

Tiers are ordered: `free < creator < pro < business`. The DB default for new
users is `free` (see db_models/models/user.py); nothing in this module
assigns tiers -- that's a billing decision (Phase 2: Stripe webhooks).
"""

from db_models.models.enums import PlanTier

# Ordered strongest-first for "what does upgrading unlock" comparisons.
TIER_ORDER: list[PlanTier] = [
    PlanTier.BUSINESS,
    PlanTier.PRO,
    PlanTier.CREATOR,
    PlanTier.FREE,
]

# 1 GiB
GIB = 1024 * 1024 * 1024


class PlanLimits:
    def __init__(
        self,
        tier: PlanTier,
        *,
        max_projects: int,
        max_clips_per_project: int,
        max_upload_bytes: int,
        export_qualities: tuple[str, ...],
        max_exports_per_project: int,
    ) -> None:
        self.tier = tier
        self.max_projects = max_projects
        self.max_clips_per_project = max_clips_per_project
        self.max_upload_bytes = max_upload_bytes
        self.export_qualities = export_qualities
        self.max_exports_per_project = max_exports_per_project

    def to_dict(self) -> dict:
        return {
            "tier": self.tier.value,
            "max_projects": self.max_projects,
            "max_clips_per_project": self.max_clips_per_project,
            "max_upload_bytes": self.max_upload_bytes,
            "export_qualities": list(self.export_qualities),
            "max_exports_per_project": self.max_exports_per_project,
        }


PLAN_LIMITS: dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        PlanTier.FREE,
        max_projects=2,
        max_clips_per_project=4,
        max_upload_bytes=1 * GIB,
        export_qualities=("720p",),
        max_exports_per_project=3,
    ),
    PlanTier.CREATOR: PlanLimits(
        PlanTier.CREATOR,
        max_projects=10,
        max_clips_per_project=10,
        max_upload_bytes=2 * GIB,
        export_qualities=("720p", "1080p"),
        max_exports_per_project=20,
    ),
    PlanTier.PRO: PlanLimits(
        PlanTier.PRO,
        max_projects=50,
        max_clips_per_project=30,
        max_upload_bytes=5 * GIB,
        export_qualities=("720p", "1080p", "4k"),
        max_exports_per_project=100,
    ),
    PlanTier.BUSINESS: PlanLimits(
        PlanTier.BUSINESS,
        max_projects=500,
        max_clips_per_project=200,
        max_upload_bytes=5 * GIB,
        export_qualities=("720p", "1080p", "4k"),
        max_exports_per_project=1000,
    ),
}


def limits_for(tier: PlanTier) -> PlanLimits:
    return PLAN_LIMITS[tier]


def tier_rank(tier: PlanTier) -> int:
    return TIER_ORDER.index(tier)
