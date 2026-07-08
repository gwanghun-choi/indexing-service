"""
Admin CRUD

관리자 전용 Milvus 컬렉션 관리 함수들을 정의합니다.
권한 검증 없이 모든 컬렉션에 대한 CRUD 작업을 수행합니다.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from pymilvus.exceptions import MilvusException

from app.config.database.async_milvus import (
    async_query,
    async_upsert,
    async_delete,
    async_list_collections,
)
from app.crud.milvus.schema_helper import get_output_fields
from app.utils.initialization import ensure_collection_loaded

logger = logging.getLogger(__name__)

# ========================================
# Constants
# ========================================
MIN_COLLECTION_NAME_PARTS = 3
MAX_SAMPLE_RECORDS = 10
DEFAULT_DB_TYPE = "unknown"
EMBEDDING_FIELD_NAME = "embedding_value"


# ========================================
# Helper Functions
# ========================================
def parse_collection_name(collection_name: str) -> Tuple[str, Optional[int]]:
    """
    컬렉션 이름에서 db_type과 group_id를 추출합니다.

    Args:
        collection_name: TB_{group_id}_{type} 형식의 컬렉션 이름

    Returns:
        Tuple[str, Optional[int]]: (db_type, group_id)
    """
    parts = collection_name.split("_")
    if len(parts) >= MIN_COLLECTION_NAME_PARTS:
        db_type = parts[-1]
        group_id = int(parts[1]) if parts[1].isdigit() else None
    else:
        db_type = DEFAULT_DB_TYPE
        group_id = None
    return db_type, group_id


async def _get_collection_row_count_async(collection_name: str) -> int:
    """컬렉션의 row_count를 비동기로 조회합니다."""
    try:
        db_type, _ = parse_collection_name(collection_name)
        await ensure_collection_loaded(collection_name, db_type if db_type in ["meta", "vector"] else "meta")

        # id >= 0 조건으로 모든 행 카운트
        results = await async_query(
            collection_name=collection_name,
            filter="id >= 0",
            output_fields=["id"]
        )
        return len(results)
    except Exception:
        return 0


async def list_all_collections() -> List[Dict[str, Any]]:
    """
    모든 Milvus 컬렉션 목록을 조회합니다.

    Returns:
        List[Dict[str, Any]]: 컬렉션 정보 목록
    """
    try:
        collection_names = await async_list_collections()

        result = []
        for name in collection_names:
            db_type, group_id = parse_collection_name(name)
            row_count = await _get_collection_row_count_async(name)
            result.append({
                "collection_name": name,
                "db_type": db_type,
                "group_id": group_id,
                "row_count": row_count,
            })

        logger.info(f"📋 컬렉션 목록 조회 완료: {len(result)}개")
        return result

    except MilvusException as e:
        logger.error(f"❌ Milvus 컬렉션 목록 조회 실패: {e}")
        raise


async def get_collection_detail(collection_name: str) -> Optional[Dict[str, Any]]:
    """
    컬렉션 상세 정보를 조회합니다.

    Args:
        collection_name: 컬렉션 이름

    Returns:
        Optional[Dict[str, Any]]: 컬렉션 상세 정보
    """
    try:
        collections = set(await async_list_collections())  # set 변환: O(1) 멤버십 체크
        if collection_name not in collections:
            return None

        db_type, _ = parse_collection_name(collection_name)
        await ensure_collection_loaded(collection_name, db_type if db_type in ["meta", "vector"] else "meta")

        # row_count 조회
        row_count = await _get_collection_row_count_async(collection_name)

        # 스키마 필드 정보 가져오기
        schema_fields = get_output_fields(db_type if db_type in ["meta", "vector"] else "meta", exclude_embedding=False)

        return {
            "collection_name": collection_name,
            "db_type": db_type,
            "row_count": row_count,
            "schema_fields": schema_fields,
            "indexes": [{"field": "embedding_value", "index_type": "COSINE"}],
        }

    except MilvusException as e:
        logger.error(f"❌ Milvus 컬렉션 상세 조회 실패: {collection_name}, {e}")
        raise


async def query_collection_data(
    collection_name: str,
    filter_expr: Optional[str] = None,
    output_fields: Optional[List[str]] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """
    컬렉션 데이터를 조회합니다.

    Args:
        collection_name: 컬렉션 이름
        filter_expr: 필터 표현식
        output_fields: 출력 필드 목록
        page: 페이지 번호
        page_size: 페이지 크기

    Returns:
        Dict[str, Any]: 데이터 목록 및 페이지 정보
    """
    try:
        db_type, _ = parse_collection_name(collection_name)
        await ensure_collection_loaded(collection_name, db_type if db_type in ["meta", "vector"] else "meta")

        if not output_fields:
            output_fields = get_output_fields(db_type if db_type in ["meta", "vector"] else "meta")

        expr = filter_expr if filter_expr else "id >= 0"

        # 전체 개수 조회
        all_results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=["id"]
        )
        total = len(all_results)

        offset = (page - 1) * page_size
        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=output_fields,
            offset=offset,
            limit=page_size,
        )

        return {
            "items": results,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except MilvusException as e:
        logger.error(f"❌ Milvus 컬렉션 데이터 조회 실패: {collection_name}, {e}")
        raise


async def preview_delete(
    collection_name: str,
    filter_expr: str,
) -> Dict[str, Any]:
    """
    삭제 대상 데이터를 미리보기합니다.

    Args:
        collection_name: 컬렉션 이름
        filter_expr: 필터 표현식

    Returns:
        Dict[str, Any]: 삭제 대상 정보
    """
    try:
        db_type, _ = parse_collection_name(collection_name)
        await ensure_collection_loaded(collection_name, db_type if db_type in ["meta", "vector"] else "meta")

        output_fields = get_output_fields(db_type if db_type in ["meta", "vector"] else "meta")
        results = await async_query(
            collection_name=collection_name,
            filter=filter_expr,
            output_fields=output_fields
        )
        affected_count = len(results)

        logger.info(f"🔍 삭제 미리보기: {collection_name}, 영향받는 레코드: {affected_count}개")

        return {
            "collection_name": collection_name,
            "affected_count": affected_count,
            "sample_records": results[:MAX_SAMPLE_RECORDS],
        }

    except MilvusException as e:
        logger.error(f"❌ Milvus 삭제 미리보기 실패: {collection_name}, {e}")
        raise


async def _modify_collection_data(
    collection_name: str,
    items: List[Dict[str, Any]],
    mode: str,
    db_type: str,
) -> Optional[Dict[str, Any]]:
    """
    컬렉션 데이터를 수정합니다 (내부 공통 함수).

    partial_update=True를 사용하여 Milvus가 내부에서 필드 머지를 처리합니다.
    기존 데이터 조회(read-merge-upsert) 없이 수정 필드만 전달합니다.

    Args:
        collection_name: 컬렉션 이름
        items: 수정할 데이터 목록 (각 항목에 id 필수)
        mode: "put" (전체 교체) 또는 "patch" (부분 수정)
        db_type: 데이터베이스 타입 ("meta" 또는 "vector")

    Returns:
        Optional[Dict[str, Any]]: 수정 결과, 컬렉션 없으면 None

    Raises:
        ValueError: 존재하지 않는 id로 수정 시도 시
    """
    collections = set(await async_list_collections())
    if collection_name not in collections:
        return None

    if not items:
        return {
            "collection_name": collection_name,
            "modified_count": 0,
            "items": [],
        }

    await ensure_collection_loaded(collection_name, db_type)
    response_fields = get_output_fields(db_type)

    # 일괄 존재 확인
    ids = [item["id"] for item in items]
    existing = await async_query(
        collection_name=collection_name,
        filter=f"id in {ids}",
        output_fields=["id"],
    )
    existing_ids = {record["id"] for record in existing}
    missing_ids = [id_ for id_ in ids if id_ not in existing_ids]
    if missing_ids:
        raise ValueError(f"존재하지 않는 id: {missing_ids[0]}")

    # 수정 필드만 전달하여 partial_update upsert
    # auto_id=True 컬렉션에서는 upsert 시 새 ID가 생성되므로 반환값에서 수집
    new_ids = []
    for item in items:
        result = await async_upsert(
            collection_name=collection_name,
            data=[item],
            partial_update=True,
        )
        new_ids.append(result["ids"][0])

    # 수정된 레코드 재조회 (응답용: embedding 제외)
    id_filter = f"id in {new_ids}"
    updated_records = await async_query(
        collection_name=collection_name,
        filter=id_filter,
        output_fields=response_fields,
    )

    logger.info(
        f"✅ 데이터 {mode} 완료: {collection_name}, {len(new_ids)}개"
    )

    return {
        "collection_name": collection_name,
        "modified_count": len(new_ids),
        "items": updated_records,
    }


async def modify_meta_data(
    collection_name: str,
    items: List[Dict[str, Any]],
    mode: str,
) -> Optional[Dict[str, Any]]:
    """
    Meta 컬렉션 데이터를 수정합니다.

    Args:
        collection_name: 컬렉션 이름
        items: 수정할 데이터 목록 (각 항목에 id 필수)
        mode: "put" (전체 교체) 또는 "patch" (부분 수정)

    Returns:
        Optional[Dict[str, Any]]: 수정 결과, 컬렉션 없으면 None
    """
    return await _modify_collection_data(collection_name, items, mode, "meta")


async def modify_vector_data(
    collection_name: str,
    items: List[Dict[str, Any]],
    mode: str,
) -> Optional[Dict[str, Any]]:
    """
    Vector 컬렉션 데이터를 수정합니다.

    Args:
        collection_name: 컬렉션 이름
        items: 수정할 데이터 목록 (각 항목에 id 필수)
        mode: "put" (전체 교체) 또는 "patch" (부분 수정)

    Returns:
        Optional[Dict[str, Any]]: 수정 결과, 컬렉션 없으면 None
    """
    return await _modify_collection_data(collection_name, items, mode, "vector")


async def delete_collection_data(
    collection_name: str,
    filter_expr: str,
) -> Dict[str, Any]:
    """
    컬렉션 데이터를 삭제합니다.

    Args:
        collection_name: 컬렉션 이름
        filter_expr: 필터 표현식

    Returns:
        Dict[str, Any]: 삭제 결과
    """
    try:
        db_type, _ = parse_collection_name(collection_name)
        await ensure_collection_loaded(collection_name, db_type if db_type in ["meta", "vector"] else "meta")

        before_results = await async_query(
            collection_name=collection_name,
            filter=filter_expr,
            output_fields=["id"]
        )
        deleted_count = len(before_results)

        await async_delete(
            collection_name=collection_name,
            filter=filter_expr
        )
        # flush() 제거: MilvusClient 자동 flush

        logger.info(f"✅ 데이터 삭제 완료: {collection_name}, {deleted_count}개")

        return {
            "collection_name": collection_name,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}개 레코드가 삭제되었습니다.",
        }

    except MilvusException as e:
        logger.error(f"❌ Milvus 데이터 삭제 실패: {collection_name}, {e}")
        raise
