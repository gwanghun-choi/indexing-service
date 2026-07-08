"""
Reranker 원격 서비스 클라이언트
didimAIStudio_Reranker 서비스와 통신합니다.
"""

# Standard Library
import logging
from typing import Any, Dict, List, Optional

# Third-Party
import httpx

# Custom (Local)
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


async def call_reranker_service(
    query: str,
    documents: List[Dict[str, Any]],
    reranker_type: str,
    top_n: int,
    user_passport: str,
    flashrank_model: Optional[str] = None,
    cohere_api_key: Optional[str] = None,
    cohere_model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Reranker 원격 서비스 호출

    Args:
        query: 검색 쿼리
        documents: 재정렬할 문서 리스트
        reranker_type: 'flashrank' 또는 'cohere'
        top_n: 반환할 최대 문서 수
        user_passport: x-user-passport 헤더 값 (필수, 인증용)
        flashrank_model: FlashRank 모델명 (선택)
        cohere_api_key: Cohere API 키 (cohere 사용 시 필수)
        cohere_model: Cohere 모델명 (선택)

    Returns:
        Reranker 응답 (results, provider, model_name, processing_time)

    Raises:
        httpx.HTTPStatusError: API 호출 실패 시
    """
    settings = get_settings()
    url = f"{settings.RERANKER_SERVICE_URL}/api/v1/reranker/rerank"

    # 인증 헤더 설정
    headers = {"x-user-passport": user_passport}

    payload: Dict[str, Any] = {
        "query": query,
        "documents": documents,
        "reranker_type": reranker_type,
        "top_n": top_n,
    }

    if reranker_type == "flashrank" and flashrank_model:
        payload["flashrank_model"] = flashrank_model
    elif reranker_type == "cohere":
        if cohere_api_key:
            payload["cohere_api_key"] = cohere_api_key
        if cohere_model:
            payload["cohere_model"] = cohere_model

    logger.info(f"🔄 Reranker 서비스 호출: {reranker_type}, 문서 수={len(documents)}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        result = response.json()
        logger.info(
            f"✅ Reranker 응답: {len(result['results'])}개 문서, "
            f"{result['processing_time']:.4f}초"
        )

        return result
