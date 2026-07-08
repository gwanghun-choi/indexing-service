"""메타 문서 요약 수정 서비스

메타 문서의 메타데이터 및 요약을 수정하고, summary 변경 시 임베딩 자동 갱신
"""

import logging
from typing import List

from app.config.database.async_milvus import async_upsert
from app.crud.milvus.document_crud import get_meta_doc_by_id
from app.crud.postgres.user_crud import select_embedding_models
from app.dto.summary_dto import MetaDocUpdateRequestDTO, MetaDocUpdateResponseDTO
from app.embedding.factory import create_embedding
from app.service.simulate_cost import count_tokens, CostSimulator, model_registry

logger = logging.getLogger(__name__)

EMBEDDING_TYPE = "openai"
EMBEDDING_MODEL = "text-embedding-ada-002"


async def update_meta_document(
    group_id: int,
    doc_id: int,
    request: MetaDocUpdateRequestDTO,
    role_ids: List[int],
) -> MetaDocUpdateResponseDTO:
    """메타 문서 수정 (summary 변경 시 임베딩 자동 갱신)

    Args:
        group_id: 그룹 ID
        doc_id: Milvus PK
        request: 수정 요청 DTO
        role_ids: JWT에서 추출한 사용자 역할 ID 리스트

    Returns:
        MetaDocUpdateResponseDTO: 수정 결과

    Raises:
        ValueError: 문서를 찾을 수 없는 경우
        PermissionError: 수정 권한이 없는 경우
    """
    # 1. 기존 메타 문서 조회
    doc = await get_meta_doc_by_id(group_id=group_id, doc_id=doc_id)
    if not doc:
        raise ValueError(f"메타 문서를 찾을 수 없습니다: id={doc_id}")

    # 2. 권한 검증
    item_role_ids = doc["role_ids"]
    if not set(role_ids) & set(item_role_ids):
        raise PermissionError(f"해당 메타 문서에 대한 수정 권한이 없습니다: id={doc_id}")

    # 3. 요청된 필드 업데이트
    summary_changed = request.summary is not None and request.summary != doc["summary"]

    if request.title is not None:
        doc["title"] = request.title
    if request.category is not None:
        doc["category"] = request.category
    if request.expiration_date is not None:
        doc["expiration_date"] = request.expiration_date

    # 4. summary 변경 시 임베딩 재생성 + 토큰/비용 재계산
    if summary_changed:
        logger.info(
            f"📝 메타 문서 요약 수정: id={doc_id}, "
            f"원본='{doc['summary'][:100]}...'"
        )
        doc["summary"] = request.summary

        vectors = await create_embedding(EMBEDDING_TYPE, [request.summary], EMBEDDING_MODEL)
        doc["embedding_value"] = vectors[0]

        new_token = await count_tokens(request.summary, EMBEDDING_MODEL)
        if not model_registry.models:
            models = await select_embedding_models()
            await model_registry.initialize(models)
        cost_simulator = CostSimulator()
        new_cost = await cost_simulator.simulate_embedding_cost(new_token, EMBEDDING_MODEL)

        doc["summary_token"] = new_token
        doc["summary_cost"] = new_cost

        logger.info(
            f"✅ 요약 임베딩 갱신 완료: id={doc_id}, "
            f"token={new_token}, cost={new_cost}"
        )

    # 5. Milvus upsert
    collection_name = f"TB_{group_id}_meta"
    await async_upsert(collection_name=collection_name, data=[doc])
    logger.info(f"✅ 메타 문서 upsert 완료: id={doc_id}")

    # 6. 응답 생성 (embedding_value 제외)
    return MetaDocUpdateResponseDTO(
        id=doc["id"],
        title=doc["title"],
        category=doc["category"],
        expiration_date=doc["expiration_date"],
        summary=doc["summary"],
        summary_token=doc["summary_token"],
        summary_cost=doc["summary_cost"],
    )
