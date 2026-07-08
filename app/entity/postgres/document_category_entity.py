from sqlalchemy import Column, String, Integer, Text

from app.config.database import Base


class DocumentCategory(Base):
    """
    문서 카테고리 정보를 저장하는 엔티티

    Attributes:
        id (int): 카테고리 고유 식별자
        name (str): 카테고리 이름
        retention_period (int): 권장 보관 기간(단위: 년)
        description (str): 비고 및 상세 설명
    """

    __tablename__ = "indexing_document_categories"
    __table_args__ = {"schema": "indexing"}

    id = Column(Integer, primary_key=True, index=True, comment="카테고리 고유 식별자")
    name = Column(String(100), nullable=False, unique=True, comment="카테고리 이름")
    retention_period = Column(
        Integer, nullable=False, comment="권장 보관 기간(단위: 년)"
    )
    description = Column(Text, nullable=True, comment="비고 및 상세 설명")

    def __repr__(self) -> str:
        """엔티티의 문자열 표현을 반환합니다."""
        return (
            f"DocumentCategory(id={self.id}, "
            f"name='{self.name}', "
            f"retention_period='{self.retention_period}')"
        )
