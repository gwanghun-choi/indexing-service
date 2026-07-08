import logging
from typing import List

from app.embedding.factory import create_embedding

logger = logging.getLogger(__name__)


async def embed_query(query: str, model: str = "openai") -> List[float]:
    """
    쿼리를 임베딩 벡터로 변환하는 비동기 함수

    Args:
        query: 임베딩할 텍스트 쿼리
        model: 사용할 임베딩 모델 이름 (기본값: 'openai')

    Returns:
        List[float]: 임베딩 벡터(부동소수점 리스트)

    Raises:
        Exception: 임베딩 생성 실패 시
    """
    try:
        logger.debug(f"임베딩 시작: 모델={model}, 쿼리 길이={len(query)}")

        # 임베딩 생성 (함수형 호출)
        query_embeddings = await create_embedding(model, [query])
        query_embedding = query_embeddings[0]

        logger.info(f"✅ 임베딩 완료: 모델={model}, 벡터 크기={len(query_embedding)}")
        return query_embedding
    except Exception as e:
        logger.error(f"❌ 임베딩 실패: 모델={model}, 오류={e}")
        raise
