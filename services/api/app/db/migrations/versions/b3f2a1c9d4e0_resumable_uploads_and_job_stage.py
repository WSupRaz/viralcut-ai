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
    op.add_column('source_videos', sa.Column('size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('source_videos', sa.Column('upload_id', sa.Text(), nullable=True))
    op.add_column('source_videos', sa.Column('original_filename', sa.Text(), nullable=True))
    op.add_column('source_videos', sa.Column('content_type', sa.Text(), nullable=True))
    op.add_column('jobs', sa.Column('stage', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'stage')
    op.drop_column('source_videos', 'content_type')
    op.drop_column('source_videos', 'original_filename')
    op.drop_column('source_videos', 'upload_id')
    op.drop_column('source_videos', 'size_bytes')
