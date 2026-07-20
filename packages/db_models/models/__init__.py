"""Importing every model module here registers its table on Base.metadata —
required for Alembic autogenerate to see the full schema."""

from db_models.models.asset import Asset
from db_models.models.billing import BillingAccount
from db_models.models.credit import Credit
from db_models.models.edit_plan import EditPlan
from db_models.models.export import Export
from db_models.models.job import Job
from db_models.models.project import Project
from db_models.models.source_video import SourceVideo
from db_models.models.style import Style
from db_models.models.template import Template
from db_models.models.timeline import Timeline
from db_models.models.user import User
from db_models.models.video_metadata import VideoMetadata

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
