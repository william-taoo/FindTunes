"""empty message

Revision ID: b8ceda250db5
Revises: 1bcc002aa681
Create Date: 2025-07-27 22:52:27.255675

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8ceda250db5'
down_revision: Union[str, Sequence[str], None] = '1bcc002aa681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('user_top_tracks', 'genius_id')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user_top_tracks', sa.Column('genius_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
