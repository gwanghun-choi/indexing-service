"""Sync MilvusClient + asyncio.to_thread 래퍼

동기 Milvus 클라이언트를 관리하고 비동기 래퍼를 제공합니다.

문제점:
- AsyncMilvusClient는 생성 시점의 Event Loop에 바인딩됨
- Celery ForkPoolWorker는 다른 Event Loop 사용 → "Event loop is closed" 오류

해결책 (커뮤니티 권장):
- Sync MilvusClient + asyncio.to_thread 패턴
- MilvusClient는 Event Loop 독립적 → 어디서든 동작
- FastAPI에서는 asyncio.to_thread로 논블로킹 호출
- Celery에서는 직접 동기 호출 가능

참고:
- https://milvus.io/api-reference/pymilvus/v2.5.x/MilvusClient/Client/AsyncMilvusClient.md
- https://github.com/milvus-io/pymilvus/issues/2591
"""
import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

from pymilvus import MilvusClient

from app.config.settings import settings

logger = logging.getLogger(__name__)

_sync_client: Optional[MilvusClient] = None
_client_lock = threading.Lock()


def get_milvus_client() -> MilvusClient:
    """
    동기 MilvusClient 싱글톤 인스턴스 반환 (Thread-Safe)

    Double-checked locking 패턴으로 스레드 안전성을 보장합니다.
    Event Loop에 독립적이므로 FastAPI와 Celery 모두에서 사용 가능합니다.

    Returns:
        MilvusClient: 동기 Milvus 클라이언트 인스턴스
    """
    global _sync_client

    if _sync_client is not None:
        return _sync_client

    with _client_lock:
        if _sync_client is not None:
            return _sync_client

        uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
        _sync_client = MilvusClient(uri=uri)
        logger.info(f"MilvusClient 연결 완료: {uri}")
        return _sync_client


# 하위 호환성을 위한 비동기 래퍼 (기존 코드 마이그레이션 지원)
async def get_async_milvus_client() -> MilvusClient:
    """
    [Deprecated] 하위 호환성을 위해 유지.
    내부적으로 get_milvus_client()를 호출합니다.

    새 코드에서는 async_xxx() 래퍼 함수를 직접 사용하세요.

    Returns:
        MilvusClient: 동기 Milvus 클라이언트 인스턴스
    """
    return get_milvus_client()


def close_milvus_client() -> None:
    """
    MilvusClient 연결 종료 (동기)

    애플리케이션 종료 시 호출하여 리소스를 정리합니다.
    """
    global _sync_client
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None
        logger.info("MilvusClient 연결 종료 완료")


async def close_async_milvus_client() -> None:
    """
    [Deprecated] 하위 호환성을 위해 유지.
    내부적으로 close_milvus_client()를 호출합니다.
    """
    close_milvus_client()


# ============================================
# FastAPI용 비동기 래퍼 (asyncio.to_thread)
# ============================================


async def async_query(
    collection_name: str,
    filter: str = "",
    output_fields: Optional[List[str]] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    비동기 query 래퍼

    Args:
        collection_name: 컬렉션 이름
        filter: 필터 표현식
        output_fields: 출력 필드 목록
        **kwargs: 추가 파라미터 (limit, offset, consistency_level 등)

    Returns:
        List[Dict[str, Any]]: 쿼리 결과
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.query,
        collection_name=collection_name,
        filter=filter,
        output_fields=output_fields,
        **kwargs
    )


async def async_query_iterate(
    collection_name: str,
    filter: str = "",
    output_fields: Optional[List[str]] = None,
    batch_size: int = 1000,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    query_iterator 기반 비동기 전량 조회 래퍼

    단일 query의 한도(응답 크기 64MB, offset+limit<16384)를 우회하기 위해
    query_iterator로 batch_size 단위로 끝까지 순회하여 전체 결과를 반환합니다.
    (sync iterator를 한 스레드 안에서 순회하여 asyncio.to_thread로 논블로킹 처리)

    Args:
        collection_name: 컬렉션 이름
        filter: 필터 표현식
        output_fields: 출력 필드 목록
        batch_size: 한 번에 가져올 행 수 (응답 크기 한도 회피용)
        **kwargs: 추가 파라미터 (consistency_level 등)

    Returns:
        List[Dict[str, Any]]: 전체 쿼리 결과
    """
    client = get_milvus_client()

    def _iterate() -> List[Dict[str, Any]]:
        iterator = client.query_iterator(
            collection_name=collection_name,
            filter=filter,
            output_fields=output_fields,
            batch_size=batch_size,
            **kwargs
        )
        results: List[Dict[str, Any]] = []
        try:
            while True:
                page = iterator.next()
                if not page:
                    break
                results.extend(page)
        finally:
            iterator.close()
        return results

    return await asyncio.to_thread(_iterate)


async def async_search(
    collection_name: str,
    data: List[List[float]],
    anns_field: str = "embedding_value",
    search_params: Optional[Dict[str, Any]] = None,
    limit: int = 10,
    output_fields: Optional[List[str]] = None,
    filter: str = "",
    **kwargs
) -> List[List[Dict[str, Any]]]:
    """
    비동기 search 래퍼

    Args:
        collection_name: 컬렉션 이름
        data: 검색할 벡터 데이터
        anns_field: 벡터 필드 이름
        search_params: 검색 파라미터
        limit: 최대 결과 수
        output_fields: 출력 필드 목록
        filter: 필터 표현식
        **kwargs: 추가 파라미터

    Returns:
        List[List[Dict[str, Any]]]: 검색 결과
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.search,
        collection_name=collection_name,
        data=data,
        anns_field=anns_field,
        search_params=search_params,
        limit=limit,
        output_fields=output_fields,
        filter=filter,
        **kwargs
    )


async def async_insert(
    collection_name: str,
    data: List[Dict[str, Any]],
    **kwargs
) -> Dict[str, Any]:
    """
    비동기 insert 래퍼

    Args:
        collection_name: 컬렉션 이름
        data: 삽입할 데이터
        **kwargs: 추가 파라미터

    Returns:
        Dict[str, Any]: 삽입 결과
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.insert,
        collection_name=collection_name,
        data=data,
        **kwargs
    )


async def async_upsert(
    collection_name: str,
    data: List[Dict[str, Any]],
    **kwargs
) -> Dict[str, Any]:
    """
    비동기 upsert 래퍼

    Args:
        collection_name: 컬렉션 이름
        data: upsert할 데이터
        **kwargs: 추가 파라미터

    Returns:
        Dict[str, Any]: upsert 결과
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.upsert,
        collection_name=collection_name,
        data=data,
        **kwargs
    )


async def async_delete(
    collection_name: str,
    filter: str = "",
    **kwargs
) -> Dict[str, Any]:
    """
    비동기 delete 래퍼

    Args:
        collection_name: 컬렉션 이름
        filter: 삭제할 데이터의 필터 표현식
        **kwargs: 추가 파라미터

    Returns:
        Dict[str, Any]: 삭제 결과
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.delete,
        collection_name=collection_name,
        filter=filter,
        **kwargs
    )


async def async_list_collections(**kwargs) -> List[str]:
    """
    비동기 list_collections 래퍼

    Returns:
        List[str]: 컬렉션 이름 목록
    """
    client = get_milvus_client()
    return await asyncio.to_thread(client.list_collections, **kwargs)


async def async_list_indexes(
    collection_name: str,
    field_name: Optional[str] = None,
    **kwargs
) -> List[str]:
    """
    비동기 list_indexes 래퍼

    컬렉션의 인덱스 목록을 조회합니다.
    field_name을 지정하지 않으면 모든 인덱스를 반환합니다.

    Args:
        collection_name: 컬렉션 이름
        field_name: 특정 필드의 인덱스만 조회할 경우 필드 이름

    Returns:
        List[str]: 인덱스 이름 목록
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.list_indexes,
        collection_name=collection_name,
        field_name=field_name,
        **kwargs
    )


async def async_load_collection(collection_name: str, **kwargs) -> None:
    """
    비동기 load_collection 래퍼

    Args:
        collection_name: 로드할 컬렉션 이름
        **kwargs: 추가 파라미터
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.load_collection,
        collection_name=collection_name,
        **kwargs
    )


async def async_create_collection(
    collection_name: str,
    schema: Any = None,
    **kwargs
) -> None:
    """
    비동기 create_collection 래퍼

    Args:
        collection_name: 생성할 컬렉션 이름
        schema: 컬렉션 스키마
        **kwargs: 추가 파라미터
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.create_collection,
        collection_name=collection_name,
        schema=schema,
        **kwargs
    )


async def async_create_index(
    collection_name: str,
    index_params: Any,
    **kwargs
) -> None:
    """
    비동기 create_index 래퍼

    MilvusClient.create_index()는 IndexParams 객체를 요구합니다.
    IndexParams는 MilvusClient.prepare_index_params()로 생성하고,
    add_index()로 인덱스 설정을 추가합니다.

    Args:
        collection_name: 컬렉션 이름
        index_params: IndexParams 객체 (MilvusClient.prepare_index_params()로 생성)
        **kwargs: 추가 파라미터
    """
    client = get_milvus_client()
    return await asyncio.to_thread(
        client.create_index,
        collection_name=collection_name,
        index_params=index_params,
        **kwargs
    )
