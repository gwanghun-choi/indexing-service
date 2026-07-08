"""
파서 설정 CRUD

외부 문서 파서 설정의 데이터베이스 접근 로직을 제공합니다.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.config.database.session import (
    get_async_db_context,
    get_async_db_context_for_worker,
)
from app.entity.postgres.parser_config_entity import ParserConfig

logger = logging.getLogger(__name__)


async def select_parser_config(
    parser_name: str,
    use_worker_context: bool = False,
) -> Optional[ParserConfig]:
    """
    파서명으로 활성화된 파서 설정 조회

    Args:
        parser_name: 파서 식별자 (예: 'ktc_parser')
        use_worker_context: Celery 워커에서 호출 시 True

    Returns:
        Optional[ParserConfig]: 파서 설정 (없거나 비활성화된 경우 None)
    """
    context = get_async_db_context_for_worker if use_worker_context else get_async_db_context
    try:
        async with context() as db:
            stmt = select(ParserConfig).where(
                and_(
                    ParserConfig.parser_name == parser_name,
                    ParserConfig.is_active.is_(True),
                )
            )

            result = await db.execute(stmt)
            config = result.scalar_one_or_none()

            if config:
                logger.debug(f"✅ 파서 설정 조회 완료: {parser_name}")
            else:
                logger.warning(f"⚠️ 파서 설정을 찾을 수 없음: {parser_name}")

            return config

    except SQLAlchemyError as e:
        logger.error(f"❌ 파서 설정 조회 실패: {e}")
        raise


async def select_active_parser_configs() -> List[ParserConfig]:
    """
    활성화된 파서 설정 목록 조회

    Returns:
        List[ParserConfig]: 활성화된 파서 설정 목록
    """
    try:
        async with get_async_db_context() as db:
            stmt = select(ParserConfig).where(
                ParserConfig.is_active.is_(True)
            ).order_by(ParserConfig.parser_name)

            result = await db.execute(stmt)
            configs = result.scalars().all()

            logger.info(f"✅ 활성 파서 목록 조회 완료: {len(configs)}개")
            return list(configs)

    except SQLAlchemyError as e:
        logger.error(f"❌ 활성 파서 목록 조회 실패: {e}")
        raise


async def create_parser_config(config_data: Dict[str, Any]) -> ParserConfig:
    """
    파서 설정 생성

    Args:
        config_data: 파서 설정 데이터

    Returns:
        ParserConfig: 생성된 파서 설정

    Raises:
        SQLAlchemyError: 데이터베이스 오류
    """
    try:
        async with get_async_db_context() as db:
            config = ParserConfig(**config_data)
            db.add(config)
            await db.flush()
            await db.refresh(config)
            await db.commit()

            logger.info(f"✅ 파서 설정 생성 완료: {config.parser_name}")
            return config

    except SQLAlchemyError as e:
        logger.error(f"❌ 파서 설정 생성 실패: {e}")
        raise


async def update_parser_config(
    parser_name: str, update_data: Dict[str, Any]
) -> Optional[ParserConfig]:
    """
    파서 설정 수정

    Args:
        parser_name: 파서 식별자
        update_data: 수정할 데이터

    Returns:
        Optional[ParserConfig]: 수정된 파서 설정 (없으면 None)
    """
    try:
        async with get_async_db_context() as db:
            stmt = (
                update(ParserConfig)
                .where(ParserConfig.parser_name == parser_name)
                .values(**update_data)
                .returning(ParserConfig)
            )

            result = await db.execute(stmt)
            await db.commit()
            config = result.scalar_one_or_none()

            if config:
                logger.info(f"✅ 파서 설정 수정 완료: {parser_name}")
            else:
                logger.warning(f"⚠️ 수정할 파서 설정을 찾을 수 없음: {parser_name}")

            return config

    except SQLAlchemyError as e:
        logger.error(f"❌ 파서 설정 수정 실패: {e}")
        raise


async def delete_parser_config(parser_name: str) -> bool:
    """
    파서 설정 삭제

    Args:
        parser_name: 파서 식별자

    Returns:
        bool: 삭제 성공 여부
    """
    try:
        async with get_async_db_context() as db:
            stmt = delete(ParserConfig).where(
                ParserConfig.parser_name == parser_name
            )

            result = await db.execute(stmt)
            await db.commit()

            if result.rowcount > 0:
                logger.info(f"✅ 파서 설정 삭제 완료: {parser_name}")
                return True
            else:
                logger.warning(f"⚠️ 삭제할 파서 설정을 찾을 수 없음: {parser_name}")
                return False

    except SQLAlchemyError as e:
        logger.error(f"❌ 파서 설정 삭제 실패: {e}")
        raise
