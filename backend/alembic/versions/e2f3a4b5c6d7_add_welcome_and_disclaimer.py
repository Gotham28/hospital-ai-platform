"""add welcome_message and post_booking_disclaimer to hospital

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('hospital', sa.Column('welcome_message', sa.Text(), nullable=True))
    op.add_column('hospital', sa.Column('post_booking_disclaimer', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('hospital', 'post_booking_disclaimer')
    op.drop_column('hospital', 'welcome_message')