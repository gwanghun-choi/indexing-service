"""
엔티티 관계 테이블

엔티티 간의 관계를 저장 (그래프 탐색 및 시각화용)
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, String, Integer, DateTime, Index

from app.config.database import Base


class EntityRelation(Base):
    """
    엔티티 관계 테이블

    Attributes:
        id (int): 고유 식별자
        group_id (int): 그룹 ID
        source_entity (str): 출발 엔티티 이름
        source_type (str): 출발 엔티티 타입
        relation_type (str): 관계 타입 (담당함, 소속됨, ...)
        target_entity (str): 도착 엔티티 이름
        target_type (str): 도착 엔티티 타입
        source_hash (str): 관계가 추출된 문서 해시
        created_at (datetime): 생성 시간
    """

    __tablename__ = "indexing_entity_relation"
    __table_args__ = (
        Index("ix_entity_relation_group_source", "group_id", "source_entity"),
        Index("ix_entity_relation_group_target", "group_id", "target_entity"),
        Index("ix_entity_relation_source_hash", "source_hash"),
        {"schema": "indexing"},
    )

    id = Column(Integer, primary_key=True, index=True, comment="고유 식별자")
    group_id = Column(Integer, nullable=False, comment="그룹 ID")
    source_entity = Column(String(255), nullable=False, comment="출발 엔티티 이름")
    source_type = Column(String(50), nullable=False, comment="출발 엔티티 타입")
    relation_type = Column(String(100), nullable=False, comment="관계 타입 (담당함, 소속됨, ...)")
    target_entity = Column(String(255), nullable=False, comment="도착 엔티티 이름")
    target_type = Column(String(50), nullable=False, comment="도착 엔티티 타입")
    source_hash = Column(String(64), nullable=False, comment="관계가 추출된 문서 해시")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("Asia/Seoul")),
        comment="생성 시간",
    )

    def __repr__(self) -> str:
        return (
            f"EntityRelation(id={self.id}, "
            f"source='{self.source_entity}', "
            f"relation='{self.relation_type}', "
            f"target='{self.target_entity}')"
        )
