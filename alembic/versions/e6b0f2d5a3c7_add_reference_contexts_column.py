"""add_reference_contexts_column

Revision ID: e6b0f2d5a3c7
Revises: d5a9e3f4c8b2
Create Date: 2026-03-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e6b0f2d5a3c7'
down_revision: Union[str, None] = 'd5a9e3f4c8b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """기존 RAGAS 평가 데이터 삭제 + reference_contexts JSONB 컬럼 추가"""
    # 기존 데이터 삭제 (details → evaluations 순서: FK 제약)
    op.execute("DELETE FROM indexing.indexing_ragas_evaluation_details")
    op.execute("DELETE FROM indexing.indexing_ragas_evaluations")

    # reference_contexts JSONB 컬럼 추가
    op.add_column(
        'indexing_ragas_evaluation_details',
        sa.Column(
            'reference_contexts',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='정답 컨텍스트 목록 [{"text": str, "page_number": int}]',
        ),
        schema='indexing',
    )


def downgrade() -> None:
    """reference_contexts 컬럼 제거"""
    op.drop_column(
        'indexing_ragas_evaluation_details',
        'reference_contexts',
        schema='indexing',
    )
