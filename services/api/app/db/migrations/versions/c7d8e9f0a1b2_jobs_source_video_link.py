"""jobs.source_video_id

Revision ID: c7d8e9f0a1b2
Revises: b3f2a1c9d4e0
Create Date: 2026-08-15 13:00:00.000000

Links per-source-video jobs (proxy, metadata) to their clip so the frontend
can show per-clip stage/error. Project-level jobs (edit_plan, render) keep
this null.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b3f2a1c9d4e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent (IF NOT EXISTS): the API runs `alembic upgrade head` on every
    # boot, so concurrent replica starts must never collide.
    op.execute(
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_video_id UUID "
        "REFERENCES source_videos (id) ON DELETE CASCADE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_source_video_id ON jobs (source_video_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_source_video_id")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS source_video_id")
