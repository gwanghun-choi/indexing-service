"""
애플리케이션 설정 모듈

MDC 규칙에 따라 구성된 설정 파일들:
- settings.py: 환경 변수 기반 설정 관리
- constants.py: 상수 정의
- database/: 데이터베이스 연결 및 세션 관리
- data/: 설정 데이터 파일
"""

from app.config.settings import settings
from app.config.constants import ALLOWED_EXTENSIONS
from app.config.database import (
    connect_to_milvus,
    get_db,
    Base,
    get_vector_schema,
    get_meta_schema,
)

__all__ = [
    "settings",
    "ALLOWED_EXTENSIONS",
    "connect_to_milvus",
    "get_db",
    "Base",
    "get_vector_schema",
    "get_meta_schema",
]
