import logging
from typing import AsyncGenerator

from pymilvus import CollectionSchema, connections
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.entity.milvus.embedding_info_entity import vector_fileds
from app.entity.milvus.meta_info_entity import meta_fields
from app.config.database.async_milvus import (
    # 동기 클라이언트 (Celery에서 직접 사용 가능)
    get_milvus_client,
    close_milvus_client,
    # 하위 호환성 (Deprecated)
    get_async_milvus_client,
    close_async_milvus_client,
    # 비동기 래퍼 (FastAPI에서 사용)
    async_query,
    async_search,
    async_insert,
    async_upsert,
    async_delete,
    async_list_collections,
    async_load_collection,
    async_create_collection,
    async_create_index,
)

__all__ = [
    "get_milvus_client",
    "close_milvus_client",
    "get_async_milvus_client",
    "close_async_milvus_client",
    "async_query",
    "async_search",
    "async_insert",
    "async_upsert",
    "async_delete",
    "async_list_collections",
    "async_load_collection",
    "async_create_collection",
    "async_create_index",
    "connect_to_milvus",
    "get_db",
    "Base",
    "get_vector_schema",
    "get_meta_schema",
    "AsyncSessionLocal",
    "async_engine",
]

logger = logging.getLogger(__name__)

# PostgreSQL 비동기 엔진 및 세션 설정
# Celery 워커 환경을 위한 개선된 설정
async_engine = create_async_engine(
    settings.ASYNC_POSTGRES_URI,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # 연결 상태 사전 확인
    pool_recycle=1800,  # 30분마다 연결 재생성
    pool_size=5,  # 워커당 풀 크기 제한
    max_overflow=10,  # 최대 오버플로우 연결 수
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


# Milvus 연결 설정
async def connect_to_milvus() -> bool:
    """
    Milvus 서버에 연결

    설정된 호스트와 포트로 Milvus 서버에 연결을 시도합니다.
    이미 연결되어 있으면 재연결하지 않습니다.

    Returns:
        bool: 연결 성공 여부

    Raises:
        Exception: Milvus 연결 중 예외 발생 시 로깅 후 False 반환
    """
    try:
        # 이미 연결되어 있으면 재연결하지 않음
        if connections.has_connection("default"):
            return True

        connections.connect(
            alias="default", host=settings.MILVUS_HOST, port=settings.MILVUS_PORT
        )
        logger.info("✅ Milvus에 연결되었습니다.")
        return True
    except Exception as e:
        logger.error(f"❌ Milvus 연결 오류: {e}")
        return False


# 비동기 데이터베이스 세션 의존성
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 의존성 주입을 위한 데이터베이스 세션 제공

    비동기 컨텍스트 매니저를 사용하여 세션을 안전하게 관리합니다.

    Yields:
        AsyncSession: SQLAlchemy 비동기 세션 객체

    Raises:
        Exception: 데이터베이스 연결 오류 시 로깅 후 예외 재발생
    """
    db = AsyncSessionLocal()
    try:
        yield db
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ 데이터베이스 세션 오류: {e}")
        raise
    finally:
        await db.close()


# Milvus 스키마를 가져오는 함수들
def get_vector_schema():
    """벡터 스키마를 반환합니다"""
    return CollectionSchema(fields=vector_fileds, description="문서 벡터 테이블")


def get_meta_schema():
    """메타 스키마를 반환합니다"""
    return CollectionSchema(fields=meta_fields, description="문서 메타 테이블")
