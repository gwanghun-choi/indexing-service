"""
agents 스키마의 페르소나 관련 엔티티
2단계 페르소나 조회를 위한 테이블 정의
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class AgtPersonasDataEntity(Base):
    """
    페르소나 데이터 엔티티 - 시스템 프롬프트 및 설정 저장
    """

    __tablename__ = "agt_personas_data"
    __table_args__ = {"schema": "agents"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, comment="사용자 ID")
    category = Column(String(50), nullable=True, comment="카테고리")
    name = Column(String(255), nullable=False, comment="페르소나 이름")
    description = Column(String(1000), nullable=False, comment="페르소나 설명")
    system_prompt = Column(Text, nullable=False, comment="시스템 프롬프트")
    user_persona_title = Column(String(255), nullable=True, comment="사용자 정의 제목")
    user_persona_description = Column(
        String(1000), nullable=True, comment="사용자 정의 설명"
    )
    is_system = Column(
        Boolean, nullable=False, default=False, comment="시스템 페르소나 여부"
    )
    is_public = Column(Boolean, nullable=False, default=False, comment="공개 여부")
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, comment="생성일시"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="수정일시",
    )

    # 관계 설정 - AgtPersonaMyPageEntity가 정의되지 않아 주석 처리
    # my_pages = relationship(
    #     "AgtPersonaMyPageEntity",
    #     back_populates="persona_data",
    #     cascade="all, delete-orphan",
    # )
