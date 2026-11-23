"""Queue approved WhatsApp welcome batches.

Revision ID: 3bc5e84d2190
Revises: 7a8b9c0d1e2f
"""
from alembic import op
import sqlalchemy as sa

revision = "3bc5e84d2190"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "whatsapp_batch_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospital.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("actor_hash", sa.String(64), nullable=False),
        sa.Column("approval_hash", sa.String(64), nullable=False),
        sa.Column("recipient_hash", sa.String(64), nullable=False),
        sa.Column("encrypted_phone", sa.LargeBinary()),
        sa.Column("masked_phone", sa.String(40), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("whatsapp_logs.id", ondelete="SET NULL")),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_id", sa.String(36)),
        sa.UniqueConstraint("hospital_id", "batch_id", "position", name="uq_whatsapp_batch_position"),
    )
    op.create_index("ix_whatsapp_batch_ready", "whatsapp_batch_items", ["status", "available_at"])
    op.create_index("ix_whatsapp_batch_recipient", "whatsapp_batch_items", ["hospital_id", "recipient_hash", "status"])


def downgrade():
    op.drop_table("whatsapp_batch_items")
