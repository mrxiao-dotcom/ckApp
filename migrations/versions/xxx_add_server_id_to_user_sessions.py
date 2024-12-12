"""add server_id to user_sessions

Revision ID: xxx
Revises: previous_revision_id
Create Date: 2024-01-10 15:28:34.649415

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'xxx'
down_revision = 'previous_revision_id'  # 替换为你的上一个迁移版本ID
branch_labels = None
depends_on = None

def upgrade():
    # 添加 server_id 列
    op.add_column('user_sessions', sa.Column('server_id', sa.String(10), nullable=True))

def downgrade():
    # 删除 server_id 列
    op.drop_column('user_sessions', 'server_id') 