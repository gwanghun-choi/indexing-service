"""
엔티티 타입 마스터 테이블

Admin이 관리하는 엔티티 타입 정의
"""

from sqlalchemy import Column, String, Integer, Text

from app.config.database import Base


class EntityTypeMaster(Base):
    """
    엔티티 타입 마스터 테이블

    Attributes:
        id (int): 고유 식별자
        type_key (str): 타입 키 (person, organization, ...)
        type_name (str): 타입 이름 (인물, 조직, ...)
        description (str): 타입 설명
    """

    __tablename__ = "indexing_entity_type_master"
    __table_args__ = {"schema": "indexing"}

    id = Column(Integer, primary_key=True, index=True, comment="고유 식별자")
    type_key = Column(
        String(50), nullable=False, unique=True, comment="타입 키 (person, organization, ...)"
    )
    type_name = Column(String(100), nullable=False, comment="타입 이름 (인물, 조직, ...)")
    description = Column(Text, nullable=True, comment="타입 설명")

    def __repr__(self) -> str:
        return (
            f"EntityTypeMaster(id={self.id}, "
            f"type_key='{self.type_key}', "
            f"type_name='{self.type_name}')"
        )
