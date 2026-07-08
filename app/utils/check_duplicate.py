import logging
from typing import Dict, Any

from app.crud.milvus.document_crud import select_documents

logger = logging.getLogger(__name__)


async def is_duplicate_data(data: Dict[str, Any]) -> bool:
    """
    해시값을 통한 중복 데이터 확인

    Args:
        data: 확인할 데이터 딕셔너리 (반드시 group_id, user_id, role_id, hash_sha256 키를 포함해야 함)

    Returns:
        bool: 중복된 데이터가 존재하면 True, 그렇지 않으면 False

    Raises:
        ValueError: 필수 키가 없는 경우
        Exception: 데이터베이스 쿼리 실패 시
    """
    try:
        logger.info(f"중복 데이터 확인 시작: hash_sha256={data['hash_sha256']}")

        # 컬렉션 조회
        collection = await select_documents(
            group_id=data["group_id"],
            user_id=data["user_id"],
            role_ids=data["total_role"],
            db_type="meta",
            hash_sha256_option=data["hash_sha256"],
        )

        is_duplicate = bool(collection)

        if is_duplicate:
            logger.info(f"✅ 중복 데이터 발견: hash_sha256={data['hash_sha256']}")
        else:
            logger.info(f"✅ 중복 데이터 없음: hash_sha256={data['hash_sha256']}")

        return is_duplicate
    except ValueError as ve:
        logger.warning(f"⚠️ 중복 데이터 확인 중 값 오류: {ve}")
        raise ve
    except Exception as e:
        logger.error(
            f"❌ 컬렉션 'TB_{data.get('group_id', 'unknown')}_meta'에서 중복 데이터 확인 중 오류 발생: {e}"
        )
        raise
