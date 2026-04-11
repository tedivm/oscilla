"""extend userrecord with web auth columns

Revision ID: f2efd06c87d8
Revises: 4e3a2cc7ad61
Create Date: 2026-04-11 16:55:25.943712

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f2efd06c87d8"
down_revision = "4e3a2cc7ad61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode for alter_column and constraint changes — required by SQLite.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("user_key", nullable=True)
        batch_op.add_column(sa.Column("email", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("hashed_password", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("display_name", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"))
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch_op.create_unique_constraint("uq_users_email", ["email"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_email", type_="unique")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("is_active")
        batch_op.drop_column("is_email_verified")
        batch_op.drop_column("display_name")
        batch_op.drop_column("hashed_password")
        batch_op.drop_column("email")
        batch_op.alter_column("user_key", nullable=False)
