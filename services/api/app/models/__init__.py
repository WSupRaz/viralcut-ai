"""Importing every model module here registers its table on Base.metadata —
required for Alembic autogenerate to see the full schema."""

from app.models.asset import Asset
from app.models.billing import BillingAccount
from app.models.credit import Credit
from app.models.edit_plan import EditPlan
from app.models.export import Export
from app.models.job import Job
from app.models.project import Project
from app.models.source_video import SourceVideo
from app.models.style import Style
from app.models.template import Template
from app.models.timeline import Timeline
from app.models.user import User
from app.models.video_metadata import VideoMetadata

__all__ = [
    "Asset",
    "BillingAccount",
    "Credit",
    "EditPlan",
    "Export",
    "Job",
    "Project",
    "SourceVideo",
    "Style",
    "Template",
    "Timeline",
    "User",
    "VideoMetadata",
]
