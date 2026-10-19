"""Arquivo, erro e padronizacao de status

Revision ID: 8f2a1c7d9b40
Revises: 53eccc48df1d
Create Date: 2026-10-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f2a1c7d9b40'
down_revision = '53eccc48df1d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('videos_download', schema=None) as batch_op:
        batch_op.add_column(sa.Column('data_atualizacao', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('arquivo', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('erro', sa.Text(), nullable=True))
        batch_op.alter_column('url_video',
                              existing_type=sa.String(length=100),
                              type_=sa.String(length=255),
                              existing_nullable=True)

    op.execute("UPDATE videos_download SET status_download = 'ERRO' "
               "WHERE status_download = 'ERRO DOWNLOAD'")


def downgrade():
    op.execute("UPDATE videos_download SET status_download = 'ERRO DOWNLOAD' "
               "WHERE status_download = 'ERRO'")

    with op.batch_alter_table('videos_download', schema=None) as batch_op:
        batch_op.alter_column('url_video',
                              existing_type=sa.String(length=255),
                              type_=sa.String(length=100),
                              existing_nullable=True)
        batch_op.drop_column('erro')
        batch_op.drop_column('arquivo')
        batch_op.drop_column('data_atualizacao')
