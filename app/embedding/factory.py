from typing import List
from app.embedding.openai_embedding import embed_openai


async def create_embedding(
    embedding_type: str, texts: List[str], model: str = None
) -> List[List[float]]:
    """
    임베딩 팩토리 함수 (함수형 방식)

    Args:
        embedding_type: 임베딩 타입 ('openai')
        texts: 임베딩할 텍스트 리스트
        model: 사용할 모델명 (선택적)

    Returns:
        List[List[float]]: 임베딩 벡터 리스트

    Raises:
        ValueError: 지원하지 않는 임베딩 유형인 경우
    """
    embedding_type_lower = embedding_type.lower()

    if embedding_type_lower == "openai":
        return await embed_openai(texts, model=model)
    else:
        raise ValueError(f"지원하지 않는 임베딩 유형: {embedding_type}")
