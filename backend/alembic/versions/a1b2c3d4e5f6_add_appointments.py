    """add appointments table and booking_config

Revision ID: a1b2c3d4e5f6
Revises: 8e2627e5f8b9
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '8e2627e5f8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add booking_config JSON column to hospital table
    op.add_column(
        'hospital',
        sa.Column('booking_config', sa.Text(), nullable=True)
    )

    # 2. Create appointments table
    op.create_table(
        'appointments',
        sa.Column('id',               sa.Integer(),  primary_key=True, index=True),
        sa.Column('reference_number', sa.String(),   nullable=False, unique=True),
        sa.Column('hospital_id',      sa.Integer(),  sa.ForeignKey('hospital.id'), nullable=False),
        sa.Column('doctor_id',        sa.Integer(),  sa.ForeignKey('doctors.id'),  nullable=False),
        sa.Column('patient_name',     sa.String(),   nullable=False),
        sa.Column('patient_age',      sa.String(),   nullable=False),
        sa.Column('patient_phone',    sa.String(),   nullable=False),
        sa.Column('preferred_date',   sa.String(),   nullable=False),
        sa.Column('time_of_day',      sa.String(),   nullable=False),
        sa.Column('confirmed_time',   sa.String(),   nullable=True),
        sa.Column('status',           sa.String(),   nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.String(),   nullable=True),
        sa.Column('created_at',       sa.DateTime(), nullable=True),
        sa.Column('updated_at',       sa.DateTime(), nullable=True),
    )

    # 3. Index for fast lookups
    op.create_index('ix_appointments_hospital_id', 'appointments', ['hospital_id'])
    op.create_index('ix_appointments_status',      'appointments', ['status'])
    op.create_index('ix_appointments_doctor_date', 'appointments', ['doctor_id', 'preferred_date'])


def downgrade() -> None:
    op.drop_index('ix_appointments_doctor_date', table_name='appointments')
    op.drop_index('ix_appointments_status',      table_name='appointments')
    op.drop_index('ix_appointments_hospital_id', table_name='appointments')
    op.drop_table('appointments')
    op.drop_column('hospital', 'booking_config')