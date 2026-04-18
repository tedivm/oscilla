"""drop character_class from character_iterations

Revision ID: 157647760123
Revises: 4e401e38a348
Create Date: 2026-04-16 21:21:06.682132

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "157647760123"
down_revision = "4e401e38a348"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("character_iterations") as batch_op:
        batch_op.drop_column("character_class")


def downgrade() -> None:
    with op.batch_alter_table("character_iterations") as batch_op:
        batch_op.add_column(sa.Column("character_class", sa.String(), nullable=True))
