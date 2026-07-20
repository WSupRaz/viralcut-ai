"""seed hormozi style preset

Revision ID: 50f2fecdf71d
Revises: 49822dc945f9
Create Date: 2026-07-21 00:07:35.548675

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50f2fecdf71d'
down_revision: Union[str, None] = '49822dc945f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Source of truth for authoring is packages/style-presets/hormozi.json --
# inlined here so the migration is self-contained and doesn't depend on an
# external file path that could move. Keep both in sync by hand if the rules
# change (downstream Claude prompt reads this row from the DB at runtime,
# never the JSON file directly -- see docs/03-database-schema.md).
HORMOZI_RULES = {
    "name": "Alex Hormozi",
    "slug": "hormozi",
    "description": "High-energy, fast-cut talking-head style popularized by Alex Hormozi.",
    "rules": {
        "cut_pacing": "Cut every 1.5-3 seconds. Remove dead air, filler words (um, uh, like, you know), and repeated phrases aggressively -- silence is the enemy.",
        "captions": "Bold, animated captions on every spoken word. Highlight 1-3 key words per sentence in a contrasting color to emphasize the core claim.",
        "zooms": "Punch zoom (scale 1.15-1.4) on emphasized words or key statements. Hold the zoom through the phrase, then release back to normal scale.",
        "transitions": "Hard cuts only. No crossfades or slow transitions -- speed is the point.",
        "tone": "High energy, direct, confident. No slow build-ups -- get to the point immediately and keep momentum throughout.",
    },
}


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO styles (id, name, slug, rules_json, is_system, created_at, updated_at)
            VALUES (gen_random_uuid(), :name, :slug, CAST(:rules_json AS JSONB), true, now(), now())
            ON CONFLICT (slug) DO UPDATE SET rules_json = EXCLUDED.rules_json
            """
        ),
        {"name": "Alex Hormozi", "slug": "hormozi", "rules_json": json.dumps(HORMOZI_RULES)},
    )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM styles WHERE slug = 'hormozi'"))
