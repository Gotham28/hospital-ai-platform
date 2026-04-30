"""add entry_type to knowledge_base

Revision ID: d1e2f3a4b5c6
Revises: cea080e631b8
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'cadd3b177e0d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'knowledge_base',
        sa.Column(
            'entry_type',
            sa.String(length=20),
            nullable=False,
            server_default='fact',
        )
    )


def downgrade() -> None:
    op.drop_column('knowledge_base', 'entry_type')