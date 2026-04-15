"""remove_current_location_from_character_iterations

Revision ID: 4e401e38a348
Revises: 8cb42c2142c2
Create Date: 2026-04-14 16:45:27.331057

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4e401e38a348"
down_revision = "8cb42c2142c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("character_iterations", "current_location")


def downgrade() -> None:
    op.add_column("character_iterations", sa.Column("current_location", sa.String(), nullable=True))
