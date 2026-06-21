"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create slot table if not exists
    conn = op.get_bind()
    try:
        op.create_table(
            'slot',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('slot_date', sa.Date, nullable=False),
            sa.Column('slot_time', sa.Time, nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='available'),
            sa.Column('appointment_id', sa.Integer, nullable=True),
            sa.Column('created_at', sa.DateTime, nullable=False),
        )
    except Exception:
        # Table may already exist on older deployments
        pass

    # Add tracking_id column to appointment if missing
    try:
        op.add_column('appointment', sa.Column('tracking_id', sa.String(16), nullable=True))
    except Exception:
        try:
            # Some DBs may not allow add_column via op.add_column if exists; attempt raw SQL
            conn.execute('ALTER TABLE appointment ADD COLUMN tracking_id VARCHAR(16)')
        except Exception:
            pass


def downgrade():
    try:
        op.drop_table('slot')
    except Exception:
        pass
    try:
        op.drop_column('appointment', 'tracking_id')
    except Exception:
        pass
