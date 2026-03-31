"""replace float stat column with biginteger

Revision ID: d3057a86660a
Revises: d4c9cbe28338
Create Date: 2026-03-30 18:55:58.417751

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d3057a86660a"
down_revision = "d4c9cbe28338"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.alter_column(
            "character_iteration_stat_values",
            "stat_value",
            type_=sa.BigInteger(),
            postgresql_using="ROUND(stat_value)::BIGINT",
            nullable=True,
        )
    else:
        # SQLite does not support ALTER COLUMN directly; use batch mode
        with op.batch_alter_table("character_iteration_stat_values") as batch_op:
            batch_op.alter_column(
                "stat_value",
                type_=sa.BigInteger(),
                nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.alter_column(
            "character_iteration_stat_values",
            "stat_value",
            type_=sa.Float(),
            postgresql_using="stat_value::DOUBLE PRECISION",
            nullable=True,
        )
    else:
        with op.batch_alter_table("character_iteration_stat_values") as batch_op:
            batch_op.alter_column(
                "stat_value",
                type_=sa.Float(),
                nullable=True,
            )
