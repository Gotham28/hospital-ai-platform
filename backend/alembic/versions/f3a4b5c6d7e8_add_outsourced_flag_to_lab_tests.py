"""add is_outsourced and outsourced_note to lab_tests

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a4b5c6d7e8'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # is_outsourced: NOT NULL with server_default='false' so existing rows are safely
    # defaulted to False without a full-table UPDATE.
    op.add_column(
        'lab_tests',
        sa.Column('is_outsourced', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )
    # outsourced_note: nullable, no default — starts NULL for all existing rows.
    # Clinic wording is pending sign-off; admin fills this in via PATCH /lab-tests/{id}.
    op.add_column(
        'lab_tests',
        sa.Column('outsourced_note', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('lab_tests', 'outsourced_note')
    op.drop_column('lab_tests', 'is_outsourced')
