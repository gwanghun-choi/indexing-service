"""
RAGAS LLM 모델 마스터 엔티티

평가에 사용할 수 있는 AI 모델 목록을 관리합니다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.config.database import Base


class RagasLlmModel(Base):
    """
    RAGAS LLM 모델 마스터 테이블

    평가에 사용 가능한 AI 모델을 등록/관리합니다.
    새 모델 출시 시 코드 배포 없이 DB INSERT만으로 추가 가능합니다.
    """

    __tablename__ = "indexing_ragas_llm_models"
    __table_args__ = {"schema": "indexing"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="모델 ID")
    model_name = Column(
        String(100), nullable=False, unique=True, comment="모델명 (gpt-4o, gpt-5.4-mini 등)"
    )
    description = Column(String(255), nullable=True, comment="설명 (기본값, 저비용 등)")
    is_active = Column(Boolean, nullable=False, default=True, comment="활성 여부")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        comment="생성 시각",
    )

    def __repr__(self) -> str:
        return (
            f"<RagasLlmModel("
            f"id={self.id!r}, "
            f"model_name={self.model_name!r}, "
            f"is_active={self.is_active!r}"
            f")>"
        )
