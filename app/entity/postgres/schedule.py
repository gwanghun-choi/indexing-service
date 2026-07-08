"""
임베딩 스케줄 엔티티

임베딩 자동 실행 스케줄 관리를 위한 데이터베이스 엔티티를 정의합니다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.config.database import Base


class EmbeddingSchedule(Base):
    """
    임베딩 스케줄 테이블

    사용자가 선택한 문서들을 특정 시간에 자동으로 임베딩 처리하는 예약 정보를 관리합니다.
    Celery Beat가 이 테이블을 주기적으로 확인하여 스케줄을 실행합니다.
    """

    __tablename__ = "indexing_embedding_schedules"
    __table_args__ = {"schema": "indexing"}

    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True, comment="스케줄 ID")
    name = Column(
        String(255),
        nullable=True,
        comment="스케줄 이름 (시스템 자동 생성, 사용자 수정 가능)",
    )
    description = Column(Text, nullable=True, comment="스케줄 설명")

    # 소유자 정보
    user_id = Column(Integer, nullable=False, comment="생성자 사용자 ID")
    group_id = Column(Integer, nullable=False, comment="그룹 ID")
    role_ids = Column(
        JSONB,
        nullable=False,
        comment="역할 ID 배열 (스케줄 생성자의 total_role)",
    )

    # 문서 목록
    document_hashes = Column(
        JSONB,
        nullable=False,
        comment="임베딩할 문서의 hash_sha256 배열 (JSON)",
    )

    # 예약 시간 설정
    scheduled_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="예약된 실행 시간",
    )
    cron_expression = Column(
        String(100),
        nullable=True,
        comment="반복 스케줄용 Cron 표현식 (선택사항)",
    )
    timezone = Column(
        String(50), nullable=False, default="Asia/Seoul", comment="시간대"
    )
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")

    # 임베딩 설정 (JSON)
    embedding_config = Column(
        JSONB,
        nullable=False,
        default={
            "chunk_size": 500,
            "chunk_overlap": 50,
            "enable_pii_anonymization": False,
            "pii_strategy": None,
            "pii_types": None,
            "persona_id": 0,
            "filter_score": None,
        },
        comment="임베딩 생성 설정 (JSON)",
    )

    # 실행 통계
    last_executed_at = Column(
        DateTime(timezone=True), nullable=True, comment="마지막 실행 시간"
    )
    total_executions = Column(
        Integer, nullable=False, default=0, comment="총 실행 횟수"
    )
    successful_executions = Column(
        Integer, nullable=False, default=0, comment="성공한 실행 횟수"
    )
    failed_executions = Column(
        Integer, nullable=False, default=0, comment="실패한 실행 횟수"
    )

    # 메타데이터
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        comment="생성 시간",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        onupdate=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        comment="수정 시간",
    )
    deleted_at = Column(
        DateTime(timezone=True), nullable=True, comment="삭제 시간 (Soft Delete)"
    )

    def __repr__(self) -> str:
        return (
            f"<EmbeddingSchedule("
            f"id={self.id!r}, "
            f"name={self.name!r}, "
            f"scheduled_at={self.scheduled_at!r}, "
            f"is_active={self.is_active!r}, "
            f"documents={len(self.document_hashes) if self.document_hashes else 0}"
            f")>"
        )


class ScheduleExecutionHistory(Base):
    """
    스케줄 실행 이력 테이블

    각 스케줄의 실행 결과와 통계를 기록합니다.
    """

    __tablename__ = "indexing_schedule_execution_history"
    __table_args__ = {"schema": "indexing"}

    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True, comment="실행 이력 ID")
    schedule_id = Column(
        Integer,
        ForeignKey("indexing.indexing_embedding_schedules.id", ondelete="CASCADE"),
        nullable=False,
        comment="스케줄 ID",
    )

    # 실행 정보
    execution_time = Column(
        DateTime(timezone=True), nullable=False, comment="실행 시간"
    )
    status = Column(
        String(20),
        nullable=False,
        comment="실행 상태 (running, success, failed, cancelled)",
    )

    # 처리 결과
    documents_processed = Column(
        Integer, nullable=False, default=0, comment="처리된 문서 수"
    )
    documents_success = Column(
        Integer, nullable=False, default=0, comment="성공한 문서 수"
    )
    documents_failed = Column(
        Integer, nullable=False, default=0, comment="실패한 문서 수"
    )

    # 태스크 ID들 (JSON array)
    task_ids = Column(JSONB, nullable=True, comment="Celery 태스크 ID 목록 (JSON)")

    # 실행 시간 정보
    started_at = Column(DateTime(timezone=True), nullable=True, comment="시작 시간")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="완료 시간")
    duration_seconds = Column(Integer, nullable=True, comment="실행 소요 시간(초)")

    # 에러 정보
    error_message = Column(Text, nullable=True, comment="에러 메시지")
    error_details = Column(JSONB, nullable=True, comment="에러 상세 정보 (JSON)")

    # 메타데이터
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        comment="레코드 생성 시간",
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduleExecutionHistory("
            f"id={self.id!r}, "
            f"schedule_id={self.schedule_id!r}, "
            f"status={self.status!r}, "
            f"documents_processed={self.documents_processed!r}"
            f")>"
        )
