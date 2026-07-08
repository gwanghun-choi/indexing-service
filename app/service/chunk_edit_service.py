"""청크 텍스트 수정 서비스

단일 청크의 parsed_text를 수정하고 임베딩 자동 갱신 + Milvus upsert + OpenSearch 재색인
"""

import logging
from typing import Any, Dict

from app.config.database.async_milvus import async_upsert
from app.crud.postgres.user_crud import select_embedding_models
from app.embedding.factory import create_embedding
from app.service.opensearch_bm25_service import (
    bulk_index_documents,
    create_opensearch_client,
    ensure_index_exists,
)
from app.service.simulate_cost import count_tokens, CostSimulator, model_registry

logger = logging.getLogger(__name__)

EMBEDDING_TYPE = "openai"
EMBEDDING_MODEL = "text-embedding-ada-002"


async def update_vector_chunk(
    group_id: int,
    chunk_data: Dict[str, Any],
    new_parsed_text: str,
) -> int:
    """청크 텍스트 수정 + 임베딩 자동 갱신 + token/cost 재계산 + Milvus upsert

    Args:
        group_id: 그룹 ID
        chunk_data: 기존 청크 데이터 (select_documents 결과)
        new_parsed_text: 수정할 텍스트

    Returns:
        int: upsert 후 새로 부여된 Milvus PK (auto_id=True로 인해 변경됨)
    """
    collection_name = f"TB_{group_id}_vector"

    # 새 임베딩 벡터 생성
    vectors = await create_embedding(EMBEDDING_TYPE, [new_parsed_text], EMBEDDING_MODEL)
    new_embedding = vectors[0]

    # token/cost 재계산 (레지스트리 미초기화 시 DB에서 모델 목록 로드)
    new_token = await count_tokens(new_parsed_text, EMBEDDING_MODEL)
    if not model_registry.models:
        models = await select_embedding_models()
        await model_registry.initialize(models)
    cost_simulator = CostSimulator()
    new_cost = await cost_simulator.simulate_embedding_cost(new_token, EMBEDDING_MODEL)

    # 기존 메타데이터 유지 + parsed_text/embedding_value/token/cost 교체
    upsert_data = {
        "id": chunk_data["id"],
        "category": chunk_data["category"],
        "title": chunk_data["title"],
        "filename": chunk_data["filename"],
        "parsed_text": new_parsed_text,
        "page_number": chunk_data["page_number"],
        "chunk_index": chunk_data["chunk_index"],
        "token": new_token,
        "cost": new_cost,
        "group_id": chunk_data["group_id"],
        "user_id": chunk_data["user_id"],
        "role_ids": chunk_data["role_ids"],
        "hash_sha256": chunk_data["hash_sha256"],
        "date": chunk_data["date"],
        "embedding_value": new_embedding,
    }

    result = await async_upsert(collection_name=collection_name, data=[upsert_data])
    new_id = result["ids"][0]
    logger.info(
        f"✅ 벡터 청크 upsert 완료: old_id={chunk_data['id']} → new_id={new_id}, "
        f"token={new_token}, cost={new_cost}"
    )
    return new_id


async def reindex_bm25_chunk(
    group_id: int,
    chunk_data: Dict[str, Any],
    new_parsed_text: str,
    expiration_date: int,
) -> None:
    """OpenSearch BM25 단건 재색인

    Args:
        group_id: 그룹 ID
        chunk_data: 기존 청크 데이터
        new_parsed_text: 수정할 텍스트
        expiration_date: 문서 만료일 (Unix timestamp, meta 컬렉션에서 조회)

    Raises:
        Exception: OpenSearch 색인 실패 시 예외 전파
    """
    os_client = create_opensearch_client()
    try:
        ensure_index_exists(os_client, group_id)

        document = {
            "milvus_id": chunk_data["id"],
            "page_content": new_parsed_text,
            "hash_sha256": chunk_data["hash_sha256"],
            "title": chunk_data["title"],
            "filename": chunk_data["filename"],
            "page_number": chunk_data["page_number"],
            "chunk_index": chunk_data["chunk_index"],
            "category": chunk_data["category"],
            "role_ids": list(chunk_data["role_ids"]),
            "expiration_date": expiration_date,
            "group_id": chunk_data["group_id"],
        }

        bulk_index_documents(os_client, group_id, [document])
        logger.info(
            f"✅ BM25 재색인 완료: hash={chunk_data['hash_sha256']}_chunk={chunk_data['chunk_index']}"
        )
    finally:
        os_client.close()
