"""add share_count to posts

Revision ID: 003_add_share_count
Revises: 002_add_diary_type
Create Date: 2026-08-24

Adds share_count column to posts table for share/forward counting
(社区分享页转发功能与热度排序).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_share_count'
down_revision: Union[str, None] = '002_add_diary_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add share_count column to posts table (additive only; existing rows get 0)
    with op.batch_alter_table('posts') as batch_op:
        batch_op.add_column(
            sa.Column('share_count', sa.Integer(), nullable=True, server_default='0')
        )


def downgrade() -> None:
    with op.batch_alter_table('posts') as batch_op:
        batch_op.drop_column('share_count')
