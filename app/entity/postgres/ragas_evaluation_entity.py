"""
RAGAS 평가 결과 엔티티

RAGAS 평가 실행 결과와 개별 질문별 평가 상세를 저장합니다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, Float, ForeignKey, Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.config.database import Base


class RagasEvaluation(Base):
    """
    RAGAS 평가 실행 테이블

    평가 1회 실행의 설정, 상태, 집계 결과를 저장합니다.
    """

    __tablename__ = "indexing_ragas_evaluations"
    __table_args__ = {"schema": "indexing"}

    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True, comment="평가 ID")
    user_id = Column(Integer, nullable=False, comment="실행한 사용자 ID")
    group_id = Column(Integer, nullable=False, comment="그룹 ID")

    # 실행 상태
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="실행 상태 (pending, running, completed, failed)",
    )
    error_message = Column(Text, nullable=True, comment="실패 시 에러 메시지")

    # 평가 설정
    eval_mode = Column(
        String(20),
        nullable=False,
        comment="평가 모드 (retrieval, generation, all)",
    )
    llm_model = Column(String(100), nullable=False, comment="평가에 사용한 AI 모델")
    search_config = Column(JSONB, nullable=False, comment="검색 파라미터")
    dataset_filename = Column(String(255), nullable=True, comment="업로드한 Excel 파일명")

    # 평가 결과 (완료 후 채워짐)
    summary = Column(JSONB, nullable=True, comment="전체 평균 점수")
    by_document = Column(JSONB, nullable=True, comment="문서별 집계")
    by_category = Column(JSONB, nullable=True, comment="카테고리별 집계")
    total_items = Column(Integer, nullable=True, comment="평가 건수")
    duration_seconds = Column(Integer, nullable=True, comment="평가 소요 시간(초)")

    # 시간 정보
    started_at = Column(DateTime(timezone=True), nullable=True, comment="평가 시작 시각")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="평가 완료 시각")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        comment="레코드 생성 시각",
    )

    def __repr__(self) -> str:
        return (
            f"<RagasEvaluation("
            f"id={self.id!r}, "
            f"status={self.status!r}, "
            f"eval_mode={self.eval_mode!r}, "
            f"total_items={self.total_items!r}"
            f")>"
        )


class RagasEvaluationDetail(Base):
    """
    RAGAS 평가 개별 질문 결과 테이블

    골든 데이터셋의 각 질문에 대한 평가 점수와 검색 결과를 저장합니다.
    """

    __tablename__ = "indexing_ragas_evaluation_details"
    __table_args__ = {"schema": "indexing"}

    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True, comment="상세 ID")
    evaluation_id = Column(
        Integer,
        ForeignKey("indexing.indexing_ragas_evaluations.id", ondelete="CASCADE"),
        nullable=False,
        comment="평가 ID",
    )

    # 질문 정보
    item_id = Column(Integer, nullable=False, comment="골든 데이터셋 질문 ID")
    user_input = Column(Text, nullable=False, comment="검색 질의")
    category = Column(String(100), nullable=False, comment="카테고리")
    source_document = Column(String(255), nullable=False, comment="출처 문서명")
    source_document_hash = Column(String(64), nullable=True, comment="출처 문서 hash_sha256")

    # 평가 점수 (선택한 지표만 값이 채워짐)
    context_precision = Column(Float, nullable=True, comment="검색 정확도 점수")
    context_recall = Column(Float, nullable=True, comment="검색 누락률 점수")
    faithfulness = Column(Float, nullable=True, comment="답변 충실도 점수")
    answer_relevancy = Column(Float, nullable=True, comment="답변 적절성 점수")

    # 답변 및 검색 결과
    response = Column(Text, nullable=True, comment="AI 생성 답변")
    reference_contexts = Column(JSONB, nullable=True, comment="정답 컨텍스트 목록 [{text, page_number}]")
    retrieved_contexts = Column(JSONB, nullable=True, comment="검색된 컨텍스트 목록")
    retrieved_chunks = Column(JSONB, nullable=True, comment="검색된 청크 메타데이터 목록")
    num_results = Column(Integer, nullable=True, comment="검색 결과 수")

    def __repr__(self) -> str:
        return (
            f"<RagasEvaluationDetail("
            f"id={self.id!r}, "
            f"evaluation_id={self.evaluation_id!r}, "
            f"item_id={self.item_id!r}"
            f")>"
        )
