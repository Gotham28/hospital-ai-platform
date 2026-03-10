"""Enable pgvector extension

Revision ID: 65cde85c52cb
Revises: 17c94b3cd7f7
Create Date: 2026-02-24 11:39:19.143662

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65cde85c52cb'
down_revision: Union[str, None] = '17c94b3cd7f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
