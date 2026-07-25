"""baseline schema

Revision ID: 001_baseline
Revises: 
Create Date: 2026-07-25

This is the baseline migration representing the existing database schema.
The database was created before Alembic was introduced, so this migration
serves as the starting point for future migrations.

To start fresh with Alembic on an existing database:
    alembic stamp 001_baseline

For new databases:
    alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration - no changes needed for existing databases.
    
    For new databases, the schema will be created by the application's
    init_db.py script (Base.metadata.create_all).
    
    Future migrations should be added on top of this baseline.
    """
    pass


def downgrade() -> None:
    """
    Baseline migration cannot be downgraded.
    """
    pass
