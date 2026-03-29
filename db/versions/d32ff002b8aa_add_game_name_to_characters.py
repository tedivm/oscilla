"""add game_name to characters

Revision ID: d32ff002b8aa
Revises: 54ce9666dd28
Create Date: 2026-03-29 12:19:06.557964

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d32ff002b8aa"
down_revision = "54ce9666dd28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table is required for SQLite compatibility (ALTER TABLE is limited in SQLite)
    # Note: existing saves.db files must be deleted before running this migration —
    # there is no server_default for game_name, so existing rows cannot be migrated.
    with op.batch_alter_table("characters") as batch_op:
        batch_op.add_column(sa.Column("game_name", sa.String(), nullable=False))
        batch_op.drop_constraint("uq_character_user_name", type_="unique")
        batch_op.create_unique_constraint("uq_character_user_game_name", ["user_id", "game_name", "name"])


def downgrade() -> None:
    with op.batch_alter_table("characters") as batch_op:
        batch_op.drop_constraint("uq_character_user_game_name", type_="unique")
        batch_op.create_unique_constraint("uq_character_user_name", ["user_id", "name"])
        batch_op.drop_column("game_name")
