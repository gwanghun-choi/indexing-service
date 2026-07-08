"""add_ragas_evaluation_tables

Revision ID: b3f7a2c1d9e4
Revises: acff5bddba97
Create Date: 2026-03-19 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3f7a2c1d9e4'
down_revision: Union[str, None] = 'acff5bddba97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """RAGAS 평가 결과 테이블 생성"""
    op.create_table(
        'indexing_ragas_evaluations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='평가 ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='실행한 사용자 ID'),
        sa.Column('group_id', sa.Integer(), nullable=False, comment='그룹 ID'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', comment='실행 상태 (pending, running, completed, failed)'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='실패 시 에러 메시지'),
        sa.Column('eval_mode', sa.String(length=20), nullable=False, comment='평가 모드 (retrieval, generation, all)'),
        sa.Column('llm_model', sa.String(length=100), nullable=False, comment='평가에 사용한 AI 모델'),
        sa.Column('search_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='검색 파라미터'),
        sa.Column('dataset_filename', sa.String(length=255), nullable=True, comment='업로드한 Excel 파일명'),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='전체 평균 점수'),
        sa.Column('by_document', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='문서별 집계'),
        sa.Column('by_category', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='카테고리별 집계'),
        sa.Column('total_items', sa.Integer(), nullable=True, comment='평가 건수'),
        sa.Column('duration_seconds', sa.Integer(), nullable=True, comment='평가 소요 시간(초)'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='평가 시작 시각'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='평가 완료 시각'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()"), comment='레코드 생성 시각'),
        sa.PrimaryKeyConstraint('id'),
        schema='indexing',
    )
    op.create_index(
        'ix_ragas_evaluations_user_id',
        'indexing_ragas_evaluations',
        ['user_id'],
        schema='indexing',
    )
    op.create_index(
        'ix_ragas_evaluations_status',
        'indexing_ragas_evaluations',
        ['status'],
        schema='indexing',
    )
    op.create_index(
        'ix_ragas_evaluations_created_at',
        'indexing_ragas_evaluations',
        ['created_at'],
        schema='indexing',
    )

    op.create_table(
        'indexing_ragas_evaluation_details',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='상세 ID'),
        sa.Column('evaluation_id', sa.Integer(), nullable=False, comment='평가 ID'),
        sa.Column('item_id', sa.Integer(), nullable=False, comment='골든 데이터셋 질문 ID'),
        sa.Column('user_input', sa.Text(), nullable=False, comment='검색 질의'),
        sa.Column('category', sa.String(length=100), nullable=False, comment='카테고리'),
        sa.Column('source_document', sa.String(length=255), nullable=False, comment='출처 문서명'),
        sa.Column('context_precision', sa.Float(), nullable=True, comment='검색 정확도 점수'),
        sa.Column('context_recall', sa.Float(), nullable=True, comment='검색 누락률 점수'),
        sa.Column('faithfulness', sa.Float(), nullable=True, comment='답변 충실도 점수'),
        sa.Column('answer_relevancy', sa.Float(), nullable=True, comment='답변 적절성 점수'),
        sa.Column('response', sa.Text(), nullable=True, comment='AI 생성 답변'),
        sa.Column('retrieved_contexts', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='검색된 컨텍스트 목록'),
        sa.Column('num_results', sa.Integer(), nullable=True, comment='검색 결과 수'),
        sa.ForeignKeyConstraint(
            ['evaluation_id'],
            ['indexing.indexing_ragas_evaluations.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        schema='indexing',
    )
    op.create_index(
        'ix_ragas_evaluation_details_evaluation_id',
        'indexing_ragas_evaluation_details',
        ['evaluation_id'],
        schema='indexing',
    )


def downgrade() -> None:
    """RAGAS 평가 결과 테이블 삭제"""
    op.drop_table('indexing_ragas_evaluation_details', schema='indexing')
    op.drop_table('indexing_ragas_evaluations', schema='indexing')
