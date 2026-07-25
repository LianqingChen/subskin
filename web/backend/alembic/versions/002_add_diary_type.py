"""add diary_type to posts

Revision ID: 002_add_diary_type
Revises: 001_baseline
Create Date: 2026-07-25

Adds diary_type column to posts table for treatment diary categorization.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_diary_type'
down_revision: Union[str, None] = '001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add diary_type column to posts table
    # SQLite doesn't support IF NOT EXISTS for columns, so we use batch mode
    with op.batch_alter_table('posts') as batch_op:
        batch_op.add_column(sa.Column('diary_type', sa.String(20), nullable=True))
        batch_op.create_index('ix_posts_diary_type', ['diary_type'])


def downgrade() -> None:
    with op.batch_alter_table('posts') as batch_op:
        batch_op.drop_index('ix_posts_diary_type')
        batch_op.drop_column('diary_type')
