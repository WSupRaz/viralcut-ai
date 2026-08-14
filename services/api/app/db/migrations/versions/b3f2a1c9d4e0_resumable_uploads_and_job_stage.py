"""resumable uploads + job stage

Revision ID: b3f2a1c9d4e0
Revises: 49822dc945f9
Create Date: 2026-08-15 12:00:00.000000

Adds the server-side session state that makes uploads chunked/resumable
(size_bytes, upload_id, original_filename, content_type on source_videos)
and a human-readable stage on jobs so the frontend can show live processing
status. upload_id non-null == upload in progress; cleared on complete.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3f2a1c9d4e0'
down_revision: Union[str, None] = '50f2fecdf71d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent (IF NOT EXISTS): the API runs `alembic upgrade head` on every
    # boot, so concurrent replica starts must never collide.
    op.execute("ALTER TABLE source_videos ADD COLUMN IF NOT EXISTS size_bytes BIGINT")
    op.execute("ALTER TABLE source_videos ADD COLUMN IF NOT EXISTS upload_id TEXT")
    op.execute("ALTER TABLE source_videos ADD COLUMN IF NOT EXISTS original_filename TEXT")
    op.execute("ALTER TABLE source_videos ADD COLUMN IF NOT EXISTS content_type TEXT")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS stage TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS stage")
    op.execute("ALTER TABLE source_videos DROP COLUMN IF EXISTS content_type")
    op.execute("ALTER TABLE source_videos DROP COLUMN IF EXISTS original_filename")
    op.execute("ALTER TABLE source_videos DROP COLUMN IF EXISTS upload_id")
    op.execute("ALTER TABLE source_videos DROP COLUMN IF EXISTS size_bytes")
