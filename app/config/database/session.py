"""
SQLAlchemy 비동기 세션 관리
컨텍스트 매니저 형태로 데이터베이스 세션을 제공합니다.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession as AS
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config.database import AsyncSessionLocal
from app.config.settings import settings

logger = logging.getLogger(__name__)


class WorkerEngineManager:
    """
    Celery 워커용 AsyncEngine 관리자

    워커 프로세스 레벨에서 AsyncEngine을 공유합니다.
    global 키워드를 사용하지 않고 클래스 속성으로 상태를 관리합니다.
    """

    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[sessionmaker] = None

    @classmethod
    def get_engine(cls) -> Tuple[AsyncEngine, sessionmaker]:
        """
        지연 초기화로 공유 엔진을 반환합니다.

        첫 호출 시 AsyncEngine을 생성하고, 이후 호출에서는 동일 인스턴스를 반환합니다.

        Returns:
            Tuple[AsyncEngine, sessionmaker]: (엔진, 세션 팩토리) 튜플
        """
        if cls._engine is None:
            cls._engine = create_async_engine(
                settings.ASYNC_POSTGRES_URI,
                echo=False,
                pool_pre_ping=True,
                poolclass=NullPool,  # Celery 워커용 연결 풀링 비활성화
            )

            cls._session_factory = sessionmaker(
                cls._engine,
                class_=AS,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )

            logger.info(f"[Worker] AsyncEngine 초기화 완료: PID={os.getpid()}")

        return cls._engine, cls._session_factory

    @classmethod
    async def dispose(cls) -> None:
        """
        워커 종료 시 AsyncEngine을 정리합니다.

        celery.py의 worker_process_shutdown에서 호출됩니다.
        """
        if cls._engine is not None:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            logger.info(f"[Worker] AsyncEngine 정리 완료: PID={os.getpid()}")


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 의존성 주입을 위한 비동기 데이터베이스 세션 제공자

    Yields:
        AsyncSession: SQLAlchemy 비동기 세션 객체
    """
    async_session = AsyncSessionLocal()
    try:
        yield async_session
        await async_session.commit()
    except Exception as e:
        await async_session.rollback()
        logger.error(f"데이터베이스 세션 오류: {e}")
        raise
    finally:
        await async_session.close()


@asynccontextmanager
async def get_async_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    비동기 컨텍스트 매니저 형태의, async with 문에서 사용 가능한 데이터베이스 세션 제공자

    Yields:
        AsyncSession: SQLAlchemy 비동기 세션 객체
    """
    async_session = AsyncSessionLocal()
    try:
        yield async_session
        await async_session.commit()
    except Exception as e:
        await async_session.rollback()
        logger.error(f"데이터베이스 세션 오류: {e}")
        raise
    finally:
        await async_session.close()


# Alias for compatibility with models repository
async_session_factory = get_async_db_context


@asynccontextmanager
async def get_async_db_context_for_worker() -> AsyncGenerator[AsyncSession, None]:
    """
    Celery 워커용 데이터베이스 세션 제공자

    WorkerEngineManager를 통해 공유 엔진을 사용합니다.
    세션만 열고 닫으며, 엔진 dispose는 워커 종료 시에만 수행됩니다.

    Yields:
        AsyncSession: SQLAlchemy 비동기 세션 객체
    """
    # 공유 엔진과 세션 팩토리 가져오기
    _, session_factory = WorkerEngineManager.get_engine()

    async_session = session_factory()
    try:
        yield async_session
        await async_session.commit()
    except Exception as e:
        await async_session.rollback()
        logger.error(f"Celery 워커 데이터베이스 세션 오류: {e}")
        raise
    finally:
        await async_session.close()
        # 주의: 엔진 dispose()는 여기서 하지 않음 (워커 종료 시에만)
