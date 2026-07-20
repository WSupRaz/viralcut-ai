"""Single shared instance per Postgres ENUM type.

Each Python Enum in enums.py maps to exactly one Postgres ENUM type. Building
the SQLAlchemy Enum() wrapper once here and importing the same instance
everywhere avoids duplicate CREATE TYPE statements when a type (e.g.
aspect_ratio) is used as a column on more than one table.
"""

from sqlalchemy import Enum as SqlEnum

from app.models.enums import (
    AspectRatio,
    AssetSource,
    AssetType,
    CreditReason,
    EditPlanStatus,
    ExportQuality,
    JobStatus,
    JobType,
    PlanTier,
    ProjectStatus,
    SourceVideoStatus,
)


def _values(enum_cls):
    return [member.value for member in enum_cls]


plan_tier_enum = SqlEnum(PlanTier, name="plan_tier", values_callable=_values)
project_status_enum = SqlEnum(ProjectStatus, name="project_status", values_callable=_values)
aspect_ratio_enum = SqlEnum(AspectRatio, name="aspect_ratio", values_callable=_values)
source_video_status_enum = SqlEnum(
    SourceVideoStatus, name="source_video_status", values_callable=_values
)
edit_plan_status_enum = SqlEnum(EditPlanStatus, name="edit_plan_status", values_callable=_values)
job_type_enum = SqlEnum(JobType, name="job_type", values_callable=_values)
job_status_enum = SqlEnum(JobStatus, name="job_status", values_callable=_values)
export_quality_enum = SqlEnum(ExportQuality, name="export_quality", values_callable=_values)
asset_type_enum = SqlEnum(AssetType, name="asset_type", values_callable=_values)
asset_source_enum = SqlEnum(AssetSource, name="asset_source", values_callable=_values)
credit_reason_enum = SqlEnum(CreditReason, name="credit_reason", values_callable=_values)
