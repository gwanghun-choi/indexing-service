"""add_ragas_llm_models_table

Revision ID: c4e8f1a2b7d3
Revises: b3f7a2c1d9e4
Create Date: 2026-03-19 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e8f1a2b7d3'
down_revision: Union[str, None] = 'b3f7a2c1d9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """RAGAS LLM 모델 마스터 테이블 생성 + 초기 데이터"""
    op.create_table(
        'indexing_ragas_llm_models',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='모델 ID'),
        sa.Column('model_name', sa.String(length=100), nullable=False, comment='모델명'),
        sa.Column('description', sa.String(length=255), nullable=True, comment='설명'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='활성 여부'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), comment='생성 시각'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_name'),
        schema='indexing',
    )

    # 초기 데이터 삽입
    op.execute(
        sa.text(
            "INSERT INTO indexing.indexing_ragas_llm_models (model_name, description) VALUES "
            "('gpt-4o', '기본값'), "
            "('gpt-4o-mini', '저비용'), "
            "('gpt-5.4', '최신 고성능'), "
            "('gpt-5.4-mini', '최신 경량'), "
            "('gpt-5.4-nano', '최신 초경량')"
        )
    )


def downgrade() -> None:
    """RAGAS LLM 모델 마스터 테이블 삭제"""
    op.drop_table('indexing_ragas_llm_models', schema='indexing')
