# Standard Library
import asyncio
import logging
import os
import random
from functools import lru_cache
from typing import List, Tuple

# Third-Party
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_api_keys() -> Tuple[str, ...]:
    """
    환경 변수에서 OpenAI API 키 목록 가져오기

    성능 최적화: lru_cache로 환경 변수 조회 캐싱 (코드 컨벤션 Section 8.10)
    반환 타입이 tuple인 이유: lru_cache 호환성을 위해 hashable 타입 사용
    """
    return (
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_API_KEY1"),
        os.getenv("OPENAI_API_KEY2"),
    )


def _get_random_api_key() -> str:
    """API 키를 랜덤하게 선택"""
    api_keys = _get_api_keys()
    return random.choice(api_keys)


# OpenAI API 배치 크기 제한 (text-embedding-3-small/large, ada-002 모두 2048)
OPENAI_EMBEDDING_BATCH_SIZE = 2048


async def _call_openai_api_batch(texts: List[str], model: str) -> List[List[float]]:
    """
    텍스트 리스트를 한 번의 API 호출로 배치 임베딩

    Args:
        texts: 임베딩할 텍스트 리스트
        model: 사용할 임베딩 모델

    Returns:
        임베딩 벡터 리스트 (입력 순서 유지)
    """
    api_key = _get_random_api_key()
    client = OpenAI(api_key=api_key)

    try:
        response = await asyncio.to_thread(
            client.embeddings.create, model=model, input=texts
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]
    except Exception:
        # 실패를 빈 벡터로 치환하지 않고 그대로 전파한다.
        # (빈 벡터가 Milvus까지 흘러가 차원 오류로 둔갑하는 것을 방지)
        logger.exception(
            f"OpenAI 배치 임베딩 실패: model={model}, text_count={len(texts)}"
        )
        raise
    finally:
        if hasattr(client, "close"):
            client.close()


async def embed_openai(texts: List[str], model: str = None) -> List[List[float]]:
    """
    OpenAI 임베딩 생성 (배치 처리)

    OpenAI API의 배치 입력 기능을 활용하여 한 번의 API 호출로
    여러 텍스트를 임베딩합니다.

    Args:
        texts: 임베딩할 텍스트 리스트
        model: 사용할 임베딩 모델 (기본값: 환경변수 EMBEDDING_MODEL)

    Returns:
        임베딩 벡터 리스트
    """
    if model is None:
        model = os.getenv("EMBEDDING_MODEL")

    if not texts:
        return []

    text_count = len(texts)
    logger.debug(f"OpenAI 배치 임베딩 시작: model={model}, texts={text_count}")

    # 배치 크기로 분할하여 처리
    all_embeddings = []
    for i in range(0, text_count, OPENAI_EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + OPENAI_EMBEDDING_BATCH_SIZE]
        batch_embeddings = await _call_openai_api_batch(batch, model=model)
        all_embeddings.extend(batch_embeddings)

    logger.debug(f"OpenAI 배치 임베딩 완료: {len(all_embeddings)}개 벡터 생성")
    return all_embeddings
