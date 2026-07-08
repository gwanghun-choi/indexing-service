"""
Relation 컬렉션 CRUD (Milvus)

관계 타입 벡터 저장 및 검색을 위한 CRUD 함수
High-level 키워드 매칭에 사용
"""

import logging
from typing import List, Dict, Optional, Any

from pymilvus import Collection, CollectionSchema, utility

from app.config.database import connect_to_milvus
from app.entity.milvus.relation_info_entity import relation_fields
from app.utils.embedding import embed_query

logger = logging.getLogger(__name__)


# ------------------------------------------
# 컬렉션 초기화
# ------------------------------------------


async def initialize_relation_collection(group_id: int) -> Collection:
    """
    Relation 컬렉션 초기화

    Args:
        group_id: 그룹 ID

    Returns:
        Collection: 초기화된 Relation 컬렉션 객체
    """
    await connect_to_milvus()

    collection_name = f"TB_{group_id}_relation"

    if not utility.has_collection(collection_name):
        schema = CollectionSchema(
            fields=relation_fields,
            description="관계 타입 벡터 컬렉션",
        )
        collection = Collection(name=collection_name, schema=schema)
        logger.info(f"✅ Relation 컬렉션 '{collection_name}' 생성 완료")

        # FLAT 인덱스 생성 (관계 타입 수가 적어서 정확도 우선)
        index_params = {
            "index_type": "FLAT",
            "metric_type": "COSINE",
        }
        collection.create_index(field_name="embedding_value", index_params=index_params)
        logger.info(f"✅ Relation 컬렉션 '{collection_name}' 인덱스 생성 완료")
    else:
        collection = Collection(name=collection_name)
        logger.debug(f"✅ Relation 컬렉션 '{collection_name}'이 이미 존재함")

    collection.load()
    return collection


# ------------------------------------------
# CREATE
# ------------------------------------------


async def create_relation_type(
    group_id: int,
    relation_type: str,
    description: str,
    synonyms: List[str],
    role_ids: List[int],
    user_id: int,
) -> int:
    """
    관계 타입 삽입

    동일한 relation_type이 존재하면 기존 ID 반환,
    없으면 새로 생성합니다.

    Args:
        group_id: 그룹 ID
        relation_type: 관계 타입 (담당함, 소속됨, ...)
        description: 관계 설명
        synonyms: 동의어 배열
        role_ids: 접근 가능한 역할 ID 리스트
        user_id: 사용자 ID

    Returns:
        int: 관계 타입 ID
    """
    try:
        collection = await initialize_relation_collection(group_id)

        # 기존 관계 타입 조회
        existing = await select_relation_type_by_name(
            group_id=group_id,
            relation_type=relation_type,
        )

        if existing:
            logger.info(f"✅ 관계 타입 '{relation_type}' 이미 존재: id={existing['id']}")
            return existing["id"]

        # 새 관계 타입 생성 - 설명 + 동의어를 합쳐서 임베딩
        embedding_text = f"{relation_type}: {description}. {', '.join(synonyms)}"
        embedding = await embed_query(embedding_text)

        relation_data = {
            "relation_type": relation_type,
            "description": description,
            "synonyms": synonyms,
            "role_ids": role_ids,
            "user_id": user_id,
            "embedding_value": embedding,
        }

        result = collection.insert([relation_data])
        collection.flush()

        relation_id = result.primary_keys[0]
        logger.info(f"✅ 관계 타입 '{relation_type}' 생성 완료: id={relation_id}")

        return relation_id

    except Exception as e:
        logger.error(f"❌ 관계 타입 삽입 중 오류 발생: {e}")
        raise


async def create_default_relation_types(
    group_id: int,
    role_ids: List[int],
    user_id: int,
) -> List[int]:
    """
    기본 관계 타입들을 배치 삽입

    Args:
        group_id: 그룹 ID
        role_ids: 접근 가능한 역할 ID 리스트
        user_id: 사용자 ID

    Returns:
        List[int]: 생성된 관계 타입 ID 리스트
    """
    default_relations = [
        {
            "relation_type": "담당함",
            "description": "사람이 프로젝트/업무를 담당",
            "synonyms": ["맡다", "책임지다", "진행하다"],
        },
        {
            "relation_type": "소속됨",
            "description": "사람이 조직에 소속",
            "synonyms": ["속하다", "근무하다", "재직하다"],
        },
        {
            "relation_type": "작성함",
            "description": "사람이 문서를 작성",
            "synonyms": ["쓰다", "생성하다", "만들다"],
        },
        {
            "relation_type": "참여함",
            "description": "사람이 프로젝트/이벤트에 참여",
            "synonyms": ["참가하다", "합류하다"],
        },
        {
            "relation_type": "관련됨",
            "description": "일반적인 연관 관계",
            "synonyms": ["연관되다", "관계있다"],
        },
        {
            "relation_type": "포함함",
            "description": "상위 개념이 하위를 포함",
            "synonyms": ["구성되다", "이루어지다"],
        },
    ]

    relation_ids = []

    for rel in default_relations:
        relation_id = await create_relation_type(
            group_id=group_id,
            relation_type=rel["relation_type"],
            description=rel["description"],
            synonyms=rel["synonyms"],
            role_ids=role_ids,
            user_id=user_id,
        )
        relation_ids.append(relation_id)

    logger.info(f"✅ {len(relation_ids)}개 기본 관계 타입 삽입 완료")
    return relation_ids


# ------------------------------------------
# READ
# ------------------------------------------


async def select_relation_type_by_name(
    group_id: int,
    relation_type: str,
) -> Optional[Dict[str, Any]]:
    """
    관계 타입명으로 조회

    Args:
        group_id: 그룹 ID
        relation_type: 관계 타입

    Returns:
        Optional[Dict]: 관계 타입 정보 또는 None
    """
    try:
        collection = await initialize_relation_collection(group_id)

        expr = f"relation_type == '{relation_type}'"

        output_fields = [
            field.name
            for field in collection.schema.fields
            if field.name != "embedding_value"
        ]

        results = collection.query(expr=expr, output_fields=output_fields, limit=1)

        return results[0] if results else None

    except Exception as e:
        logger.error(f"❌ 관계 타입 조회 중 오류 발생: {e}")
        return None


async def search_relation_types(
    group_id: int,
    query: str,
    role_ids: List[int],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    관계 타입 벡터 유사도 검색 (High-level 키워드 매칭)

    Args:
        group_id: 그룹 ID
        query: 검색 쿼리 (관계 의도)
        role_ids: 접근 가능한 역할 ID 리스트
        top_k: 반환할 최대 결과 수

    Returns:
        List[Dict]: 유사한 관계 타입 리스트 (score 포함)
    """
    try:
        collection = await initialize_relation_collection(group_id)

        # 쿼리 임베딩
        query_embedding = await embed_query(query)

        # role_ids 필터
        role_filter = " || ".join(
            [f"array_contains(role_ids, {role_id})" for role_id in role_ids]
        )
        expr = f"({role_filter})"

        # 벡터 검색
        search_params = {"metric_type": "COSINE", "params": {}}

        output_fields = [
            field.name
            for field in collection.schema.fields
            if field.name != "embedding_value"
        ]

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding_value",
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=output_fields,
        )

        relation_types = []
        for hits in results:
            for hit in hits:
                relation = {
                    "id": hit.id,
                    "score": hit.score,
                    **hit.entity,
                }
                relation_types.append(relation)

        logger.info(
            f"✅ 관계 타입 검색 완료: query='{query}', 결과={len(relation_types)}개"
        )
        return relation_types

    except Exception as e:
        logger.error(f"❌ 관계 타입 검색 중 오류 발생: {e}")
        return []


async def select_relation_types(
    group_id: int,
    role_ids: List[int],
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    관계 타입 목록 조회

    Args:
        group_id: 그룹 ID
        role_ids: 접근 가능한 역할 ID 리스트
        limit: 최대 조회 수

    Returns:
        List[Dict]: 관계 타입 목록
    """
    try:
        collection = await initialize_relation_collection(group_id)

        # role_ids 필터
        role_filter = " || ".join(
            [f"array_contains(role_ids, {role_id})" for role_id in role_ids]
        )
        expr = f"({role_filter})"

        output_fields = [
            field.name
            for field in collection.schema.fields
            if field.name != "embedding_value"
        ]

        results = collection.query(
            expr=expr,
            output_fields=output_fields,
            limit=limit,
        )

        logger.debug(f"✅ 관계 타입 목록 조회: {len(results)}개")
        return results

    except Exception as e:
        logger.error(f"❌ 관계 타입 목록 조회 중 오류 발생: {e}")
        return []


# ------------------------------------------
# UPDATE
# ------------------------------------------


async def update_relation_type(
    group_id: int,
    relation_id: int,
    update_data: Dict[str, Any],
) -> bool:
    """
    관계 타입 업데이트

    description 또는 synonyms 변경 시 임베딩 재생성합니다.

    Args:
        group_id: 그룹 ID
        relation_id: 관계 타입 ID
        update_data: 업데이트할 데이터

    Returns:
        bool: 성공 여부
    """
    try:
        collection = await initialize_relation_collection(group_id)

        # 기존 데이터 조회
        output_fields = [field.name for field in collection.schema.fields]
        results = collection.query(
            expr=f"id == {relation_id}",
            output_fields=output_fields,
        )

        if not results:
            logger.warning(f"⚠️ 관계 타입을 찾을 수 없습니다: id={relation_id}")
            return False

        existing = results[0]

        # description 또는 synonyms 변경 시 임베딩 재생성
        need_reembed = False
        if "description" in update_data:
            if update_data["description"] != existing.get("description"):
                need_reembed = True
        if "synonyms" in update_data:
            if update_data["synonyms"] != existing.get("synonyms"):
                need_reembed = True

        # 업데이트 적용
        for key, value in update_data.items():
            existing[key] = value

        if need_reembed:
            embedding_text = (
                f"{existing['relation_type']}: {existing['description']}. "
                f"{', '.join(existing.get('synonyms', []))}"
            )
            existing["embedding_value"] = await embed_query(embedding_text)
            logger.info(f"✅ 관계 타입 '{existing['relation_type']}' 임베딩 재생성")

        collection.upsert([existing])
        collection.flush()

        logger.info(f"✅ 관계 타입 업데이트 완료: id={relation_id}")
        return True

    except Exception as e:
        logger.error(f"❌ 관계 타입 업데이트 중 오류 발생: {e}")
        return False


# ------------------------------------------
# DELETE
# ------------------------------------------


async def delete_relation_type(
    group_id: int,
    relation_id: int,
) -> bool:
    """
    관계 타입 삭제

    Args:
        group_id: 그룹 ID
        relation_id: 관계 타입 ID

    Returns:
        bool: 성공 여부
    """
    try:
        collection = await initialize_relation_collection(group_id)

        collection.delete(expr=f"id == {relation_id}")
        collection.flush()

        logger.info(f"✅ 관계 타입 삭제 완료: id={relation_id}")
        return True

    except Exception as e:
        logger.error(f"❌ 관계 타입 삭제 중 오류 발생: {e}")
        return False
