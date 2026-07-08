"""add_source_document_hash_column

Revision ID: f7c1d3e5a9b2
Revises: e6b0f2d5a3c7
Create Date: 2026-03-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f7c1d3e5a9b2'
down_revision: Union[str, None] = 'e6b0f2d5a3c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """기존 RAGAS 평가 데이터 삭제 + source_document_hash 컬럼 추가"""
    # 기존 데이터 삭제 (details → evaluations 순서: FK 제약)
    op.execute("DELETE FROM indexing.indexing_ragas_evaluation_details")
    op.execute("DELETE FROM indexing.indexing_ragas_evaluations")

    # source_document_hash 컬럼 추가
    op.add_column(
        'indexing_ragas_evaluation_details',
        sa.Column(
            'source_document_hash',
            sa.String(64),
            nullable=True,
            comment='출처 문서 hash_sha256',
        ),
        schema='indexing',
    )


def downgrade() -> None:
    """source_document_hash 컬럼 제거"""
    op.drop_column(
        'indexing_ragas_evaluation_details',
        'source_document_hash',
        schema='indexing',
    )
