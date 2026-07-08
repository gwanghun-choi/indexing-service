"""
API 권한 엔티티

엔드포인트 권한 관리를 위한 데이터베이스 엔티티를 정의합니다.
"""

from sqlalchemy import Column, String, Integer
from app.config.database import Base


class ApiPermission(Base):
    """API 권한 정보 엔티티"""

    __tablename__ = "indexing_endpoints_permission"
    __table_args__ = {"schema": "indexing"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String(255), nullable=False, comment="API 경로")
    resource_type = Column(String(50), nullable=False, comment="리소스 타입")
    required_role = Column(String(50), nullable=True, comment="필요 역할")
    http_method = Column(String(10), nullable=False, comment="HTTP 메소드")
    action_type = Column(String(20), nullable=False, comment="액션 타입")

    def __repr__(self):
        return f"<ApiPermission(path={self.path}, method={self.http_method}, action={self.action_type})>"
