import enum


class PlanTier(str, enum.Enum):
    FREE = "free"
    CREATOR = "creator"
    PRO = "pro"
    BUSINESS = "business"


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class AspectRatio(str, enum.Enum):
    VERTICAL = "9:16"
    HORIZONTAL = "16:9"
    SQUARE = "1:1"


class SourceVideoStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROXY_READY = "proxy_ready"
    METADATA_READY = "metadata_ready"
    FAILED = "failed"


class EditPlanStatus(str, enum.Enum):
    GENERATED = "generated"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class JobType(str, enum.Enum):
    PROXY = "proxy"
    METADATA_EXTRACTION = "metadata_extraction"
    EDIT_PLAN = "edit_plan"
    RENDER = "render"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"


class ExportQuality(str, enum.Enum):
    P720 = "720p"
    P1080 = "1080p"
    K4 = "4k"


class AssetType(str, enum.Enum):
    TRANSITION = "transition"
    SOUND_EFFECT = "sound_effect"
    MUSIC = "music"
    MOTION_GRAPHIC = "motion_graphic"
    BROLL = "broll"


class AssetSource(str, enum.Enum):
    INTERNAL = "internal"
    PEXELS = "pexels"
    PIXABAY = "pixabay"


class CreditReason(str, enum.Enum):
    MONTHLY_GRANT = "monthly_grant"
    PURCHASE = "purchase"
    RENDER_SPEND = "render_spend"
    REFUND = "refund"
    PROMO = "promo"
