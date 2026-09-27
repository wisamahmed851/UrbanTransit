"""stop-period smart-card demand history

Revision ID: 927e64bd1e92
Revises: 6e3739ffae4a
"""

from alembic import op
import sqlalchemy as sa


revision = "927e64bd1e92"
down_revision = "6e3739ffae4a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("trip_context", schema=None) as batch_op:
        batch_op.add_column(sa.Column("prior_route_occupancy_mean", sa.Double(), nullable=True))
        batch_op.add_column(sa.Column("prior_route_hour_occupancy_mean", sa.Double(), nullable=True))
    op.create_table(
        "stop_period_boardings",
        sa.Column("entry_stop_id", sa.String(length=16), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("time_period", sa.String(length=16), nullable=False),
        sa.Column("tap_ins", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("entry_stop_id", "service_date", "time_period"),
    )


def downgrade():
    op.drop_table("stop_period_boardings")
    with op.batch_alter_table("trip_context", schema=None) as batch_op:
        batch_op.drop_column("prior_route_hour_occupancy_mean")
        batch_op.drop_column("prior_route_occupancy_mean")
