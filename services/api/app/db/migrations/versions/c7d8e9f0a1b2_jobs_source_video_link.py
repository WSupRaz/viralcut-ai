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
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b3f2a1c9d4e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'jobs',
        sa.Column('source_video_id', sa.UUID(), sa.ForeignKey('source_videos.id', ondelete='CASCADE'), nullable=True),
    )
    op.create_index('ix_jobs_source_video_id', 'jobs', ['source_video_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_jobs_source_video_id', table_name='jobs')
    op.drop_column('jobs', 'source_video_id')
