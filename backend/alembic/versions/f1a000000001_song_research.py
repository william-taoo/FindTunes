"""Evidence-backed song profile cache."""
from alembic import op
import sqlalchemy as sa
revision = 'f1a000000001'
down_revision = 'b8ceda250db5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('song_research_cache', sa.Column('key', sa.String(64), primary_key=True),
        sa.Column('expires_at', sa.Float(), nullable=False), sa.Column('payload', sa.JSON(), nullable=False))


def downgrade():
    op.drop_table('song_research_cache')
