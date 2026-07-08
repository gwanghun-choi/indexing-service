"""
사용자 정의 카테고리 엔티티

사용자별 커스텀 카테고리를 관리하며, 계층 구조(무제한 깊이)를 지원합니다.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.config.database import Base


class UserCategory(Base):
    """
    사용자 정의 카테고리 엔티티

    사용자별로 독립적인 카테고리 체계를 제공합니다.
    계층 구조를 지원하며, 부모-자식 관계로 무제한 깊이의 트리 구조를 표현합니다.

    Attributes:
        id (int): 카테고리 고유 식별자
        user_id (int): 소유자 사용자 ID
        group_id (int): 소속 그룹 ID (참조용)
        name (str): 카테고리 이름 (최대 100자)
        description (str): 카테고리 설명
        default_retention_period (int): 만료기간 추천값 (년 단위, 기본 3년)
        parent_id (int): 부모 카테고리 ID (NULL이면 루트 카테고리)
        depth (int): 계층 깊이 (루트=1)
        path (str): 경로 문자열 (예: "1/5/12")
        created_at (datetime): 생성 시각
        updated_at (datetime): 수정 시각
    """

    __tablename__ = "indexing_user_categories"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "name", "parent_id", name="uq_user_name_parent"
        ),
        CheckConstraint("depth >= 1", name="ck_depth_positive"),
        Index("idx_user_categories_user_id", "user_id"),
        Index("idx_user_categories_parent_id", "parent_id"),
        Index("idx_user_categories_path", "path"),
        {"schema": "indexing"},
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="카테고리 고유 식별자",
    )
    user_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="소유자 사용자 ID",
    )
    group_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="소속 그룹 ID",
    )
    name = Column(
        String(100),
        nullable=False,
        comment="카테고리 이름",
    )
    description = Column(
        Text,
        nullable=True,
        comment="카테고리 설명",
    )
    default_retention_period = Column(
        Integer,
        default=3,
        nullable=False,
        comment="만료기간 추천값 (년 단위)",
    )
    parent_id = Column(
        Integer,
        ForeignKey("indexing.indexing_user_categories.id", ondelete="RESTRICT"),
        nullable=True,
        comment="부모 카테고리 ID",
    )
    depth = Column(
        Integer,
        default=1,
        nullable=False,
        comment="계층 깊이 (루트=1)",
    )
    path = Column(
        Text,
        nullable=True,
        index=True,
        comment="경로 문자열 (예: 1/5/12)",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="생성 시각",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="수정 시각",
    )

    # Self-referential relationship for parent-child
    # parent_id가 현재 레코드의 id를 참조하는 관계
    parent = relationship(
        "UserCategory",
        remote_side="UserCategory.id",
        foreign_keys=[parent_id],
        backref="children",
    )

    def __repr__(self) -> str:
        """엔티티의 문자열 표현을 반환합니다."""
        return (
            f"UserCategory(id={self.id}, "
            f"user_id={self.user_id}, "
            f"name='{self.name}', "
            f"depth={self.depth})"
        )

    def to_dict(self) -> dict:
        """엔티티를 딕셔너리로 변환합니다."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "group_id": self.group_id,
            "name": self.name,
            "description": self.description,
            "default_retention_period": self.default_retention_period,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "path": self.path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
