"""add character_iteration_active_buffs table

Revision ID: 4e3a2cc7ad61
Revises: 97bbf20a2043
Create Date: 2026-04-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4e3a2cc7ad61"
down_revision = "97bbf20a2043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "character_iteration_active_buffs",
        sa.Column("iteration_id", sa.Uuid(), nullable=False),
        sa.Column("buff_ref", sa.String(), nullable=False),
        sa.Column("remaining_turns", sa.Integer(), nullable=False),
        sa.Column("variables_json", sa.String(), nullable=False, server_default="{}"),
        sa.Column("tick_expiry", sa.BigInteger(), nullable=True),
        sa.Column("game_tick_expiry", sa.BigInteger(), nullable=True),
        sa.Column("real_ts_expiry", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["iteration_id"],
            ["character_iterations.id"],
        ),
        sa.PrimaryKeyConstraint("iteration_id", "buff_ref"),
    )


def downgrade() -> None:
    op.drop_table("character_iteration_active_buffs")
