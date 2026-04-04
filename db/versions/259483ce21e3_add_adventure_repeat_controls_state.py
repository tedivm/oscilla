"""add adventure repeat controls state

Revision ID: 259483ce21e3
Revises: d734190494ea
Create Date: 2026-04-04 16:08:28.824301

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "259483ce21e3"
down_revision = "d734190494ea"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character_iteration_adventure_state",
        sa.Column("iteration_id", sa.UUID(), nullable=False),
        sa.Column("adventure_ref", sa.String(), nullable=False),
        sa.Column("last_completed_on", sa.String(), nullable=True),
        sa.Column("last_completed_at_total", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["iteration_id"], ["character_iterations.id"]),
        sa.PrimaryKeyConstraint("iteration_id", "adventure_ref"),
    )


def downgrade() -> None:
    op.drop_table("character_iteration_adventure_state")
