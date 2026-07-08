"""
파서 설정 엔티티

외부 문서 파서 설정 관리를 위한 데이터베이스 엔티티를 정의합니다.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.config.database import Base


class ParserConfig(Base):
    """
    파서 설정 테이블

    외부 문서 파서(KT Cloud Document Parse API 등)의 설정 정보를 관리합니다.
    API 키, 엔드포인트, 타임아웃 등의 설정을 저장합니다.
    """

    __tablename__ = "indexing_parser_config"
    __table_args__ = {"schema": "indexing"}

    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True, comment="파서 설정 ID")
    parser_name = Column(
        String(50),
        nullable=False,
        unique=True,
        comment="파서 식별자 (예: ktc_parser)",
    )
    display_name = Column(
        String(100),
        nullable=False,
        comment="표시 이름 (예: KT Cloud Document Parser)",
    )

    # API 설정
    api_endpoint = Column(Text, nullable=False, comment="API 엔드포인트 URL")
    api_key = Column(Text, nullable=False, comment="API 인증 키")

    # 동작 설정
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="활성화 여부 (FALSE일 경우 사용 불가)",
    )
    timeout_seconds = Column(
        Integer,
        nullable=False,
        default=300,
        comment="API 호출 타임아웃 (초)",
    )
    max_retries = Column(
        Integer,
        nullable=False,
        default=3,
        comment="실패 시 최대 재시도 횟수",
    )

    # 추가 설정 (파서별 옵션)
    extra_config = Column(
        JSONB,
        nullable=False,
        default={},
        comment="파서별 추가 설정 (JSON)",
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

    def __repr__(self) -> str:
        return (
            f"<ParserConfig("
            f"id={self.id!r}, "
            f"parser_name={self.parser_name!r}, "
            f"display_name={self.display_name!r}, "
            f"is_active={self.is_active!r}"
            f")>"
        )
