"""add_retrieved_chunks_column

Revision ID: d5a9e3f4c8b2
Revises: c4e8f1a2b7d3
Create Date: 2026-03-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd5a9e3f4c8b2'
down_revision: Union[str, None] = 'c4e8f1a2b7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """RagasEvaluationDetail 테이블에 retrieved_chunks JSONB 컬럼 추가"""
    op.add_column(
        'indexing_ragas_evaluation_details',
        sa.Column(
            'retrieved_chunks',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='검색된 청크 메타데이터 목록',
        ),
        schema='indexing',
    )


def downgrade() -> None:
    """retrieved_chunks 컬럼 제거"""
    op.drop_column(
        'indexing_ragas_evaluation_details',
        'retrieved_chunks',
        schema='indexing',
    )
