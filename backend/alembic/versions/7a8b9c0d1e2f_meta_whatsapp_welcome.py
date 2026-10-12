"""Add provider-neutral welcome metadata; DRAFT, not applied.

Revision ID: 7a8b9c0d1e2f
Revises: 0c682ef81de1
"""
from alembic import op
import sqlalchemy as sa

revision = "7a8b9c0d1e2f"
down_revision = "0c682ef81de1"
branch_labels = None
depends_on = None


def upgrade():
    columns = [
        ("provider", sa.String(16)),
        ("provider_message_id", sa.String(255)),
        ("request_id", sa.String(36)),
        ("request_fingerprint", sa.String(64)),
        ("language", sa.String(8)),
        ("consent_confirmed_at", sa.DateTime(timezone=True)),
        ("consent_recorded_by", sa.String(64)),
        ("error_code", sa.String(64)),
        ("status_updated_at", sa.DateTime(timezone=True)),
        ("provider_event_at", sa.DateTime(timezone=True)),
    ]
    for name, kind in columns:
        op.add_column("whatsapp_logs", sa.Column(name, kind, nullable=True))
    op.create_unique_constraint("uq_whatsapp_hospital_request", "whatsapp_logs", ["hospital_id", "request_id"])
    op.create_unique_constraint("uq_whatsapp_provider_message", "whatsapp_logs", ["provider_message_id"])


def downgrade():
    op.drop_constraint("uq_whatsapp_provider_message", "whatsapp_logs", type_="unique")
    op.drop_constraint("uq_whatsapp_hospital_request", "whatsapp_logs", type_="unique")
    for name in reversed([
        "provider", "provider_message_id", "request_id", "request_fingerprint", "language",
        "consent_confirmed_at", "consent_recorded_by", "error_code", "status_updated_at", "provider_event_at",
    ]):
        op.drop_column("whatsapp_logs", name)
