# Standard library imports
import logging
from typing import Dict, List, Optional, Any

# Third-party imports
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Custom imports
from app.config.database.session import get_async_db_context, get_async_db_context_for_worker

logger = logging.getLogger(__name__)


async def select_user_group_info(user_id: int) -> Dict:
    """
    사용자 ID로 사용자 그룹 정보를 조회

    Args:
        user_id: 사용자 ID

    Returns:
        Dict: 사용자 그룹 정보 (group_id, role_id)
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(
                text(
                    "SELECT group_id, role_id FROM auth.auth_user_groups WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            )
            result = result.fetchone()

            if not result:
                logger.warning(
                    f"사용자 ID {user_id}에 대한 그룹 정보를 찾을 수 없습니다."
                )
                return None

            # Row 객체를 딕셔너리로 변환
            return {key: value for key, value in result._mapping.items()}
    except SQLAlchemyError as e:
        logger.error(f"사용자 그룹 정보 조회 실패: {e}")
        raise


async def select_all_user_groups(user_id: int) -> List[Dict]:
    """
    사용자 ID로 모든 그룹 정보 조회

    Args:
        user_id: 사용자 ID

    Returns:
        List[Dict]: 사용자가 속한 모든 그룹 정보 목록
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(
                text(
                    "SELECT group_id, role_id FROM auth_user_groups WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            )
            results = result.fetchall()

            if not results:
                logger.warning(
                    f"사용자 ID {user_id}에 대한 그룹 정보를 찾을 수 없습니다."
                )
                return []

            # Row 객체들을 딕셔너리 리스트로 변환
            return [
                {key: value for key, value in row._mapping.items()} for row in results
            ]
    except SQLAlchemyError as e:
        logger.error(f"사용자 그룹 정보 조회 실패: {e}")
        raise


async def execute_custom_query(query: str, params: dict = None) -> List[Dict]:
    """
    사용자 정의 쿼리 실행

    Args:
        query: SQL 쿼리
        params: 쿼리 파라미터 (딕셔너리)

    Returns:
        List[Dict]: 쿼리 결과
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(text(query), params or {})
            results = result.fetchall()
            return [
                {key: value for key, value in row._mapping.items()} for row in results
            ]
    except SQLAlchemyError as e:
        logger.error(f"쿼리 실행 실패: {e}")
        raise


async def select_embedding_models(use_worker_context: bool = False):
    """
    임베딩 모델 목록 조회

    Args:
        use_worker_context: Celery 워커에서 호출 시 True로 설정하여 워커 전용 세션 사용

    Returns:
        List[Dict]: 임베딩 모델 목록
    """
    try:
        # Celery 워커에서 호출 시 워커 전용 세션 사용
        context_manager = get_async_db_context_for_worker if use_worker_context else get_async_db_context

        async with context_manager() as db:
            result = await db.execute(
                text(
                    """
                SELECT *
                FROM public.gen_ai_models
                WHERE category = 'EMBEDDING'
                """
                )
            )
            results = result.fetchall()
            return [
                {key: value for key, value in row._mapping.items()} for row in results
            ]
    except SQLAlchemyError as e:
        logger.error(f"임베딩 모델 목록 조회 실패: {e}")
        raise


async def select_document_categories() -> List[Dict[str, Any]]:
    """
    카테고리 테이블의 모든 항목을 조회합니다.

    Returns:
        List[Dict[str, Any]]: 카테고리 항목 목록

    Raises:
        Exception: 데이터베이스 조회 중 오류 발생 시
    """
    try:
        query = """
            SELECT id, name, retention_period, description
            FROM indexing.indexing_document_categories
        """
        return await execute_custom_query(query)
    except Exception as e:
        logger.error(f"카테고리 목록 조회 중 오류 발생: {e}")
        raise


async def select_user_full_name(user_id: int) -> Optional[str]:
    """
    사용자 ID로 사용자의 full_name을 조회합니다.

    Args:
        user_id: 사용자 ID

    Returns:
        Optional[str]: 사용자의 full_name (없으면 None)

    Raises:
        Exception: 데이터베이스 조회 중 오류 발생 시
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(
                text(
                    "SELECT full_name FROM auth.auth_users WHERE id = :user_id"
                ),
                {"user_id": user_id},
            )
            row = result.fetchone()

            if not row:
                logger.warning(f"사용자 ID {user_id}에 대한 정보를 찾을 수 없습니다.")
                return None

            return row[0]  # full_name 반환
    except SQLAlchemyError as e:
        logger.error(f"사용자 full_name 조회 실패: {e}")
        raise


async def select_user_full_names_batch(user_ids: List[int]) -> Dict[int, str]:
    """
    여러 사용자 ID로 full_name을 배치 조회합니다.

    N+1 쿼리 문제를 해결하기 위해 한 번의 DB 호출로 여러 사용자 정보를 조회합니다.

    Args:
        user_ids: 사용자 ID 리스트

    Returns:
        Dict[int, str]: {user_id: full_name} 형태의 딕셔너리
            - 존재하지 않는 user_id는 결과에 포함되지 않음

    Raises:
        Exception: 데이터베이스 조회 중 오류 발생 시

    Example:
        >>> result = await select_user_full_names_batch([1, 2, 3])
        >>> print(result)
        {1: "홍길동", 2: "김철수"}
    """
    if not user_ids:
        return {}

    try:
        # 중복 제거
        unique_ids = list(set(user_ids))

        async with get_async_db_context() as db:
            # IN 절을 사용한 배치 조회
            result = await db.execute(
                text(
                    "SELECT id, full_name FROM auth.auth_users WHERE id = ANY(:user_ids)"
                ),
                {"user_ids": unique_ids},
            )
            rows = result.fetchall()

            # {user_id: full_name} 딕셔너리로 변환
            return {row[0]: row[1] for row in rows if row[1]}

    except SQLAlchemyError as e:
        logger.error(f"사용자 full_name 배치 조회 실패: {e}")
        raise
