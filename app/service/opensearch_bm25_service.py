"""
OpenSearch BM25 검색 서비스
opensearch-py를 직접 사용한 BM25 검색 구현
"""

# Standard Library
import logging
import math
from typing import Any, Dict, List

# Third-Party
from langchain_core.documents import Document
import numpy as np
from opensearchpy import NotFoundError, OpenSearch
from opensearchpy.helpers import bulk

# Custom
from app.config.opensearch_config import get_index_body, get_index_name
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


def create_opensearch_client() -> OpenSearch:
    """OpenSearch 클라이언트 생성"""
    settings = get_settings()
    return OpenSearch(
        hosts=[{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=60,  # 기본 timeout 60초로 증가
    )


def ensure_index_exists(client: OpenSearch, group_id: int) -> None:
    """인덱스 존재 확인 및 생성"""
    index_name = get_index_name(group_id)

    if not client.indices.exists(index=index_name):
        index_body = get_index_body()
        client.indices.create(index=index_name, body=index_body)


def bulk_index_documents(
    client: OpenSearch, group_id: int, documents: List[Dict[str, Any]]
) -> int:
    """
    벌크 문서 인덱싱

    Args:
        client: OpenSearch 클라이언트
        group_id: 그룹 ID
        documents: 인덱싱할 문서 리스트

    Returns:
        성공적으로 인덱싱된 문서 수
    """
    index_name = get_index_name(group_id)

    actions = [
        {
            "_index": index_name,
            "_id": f"{doc['hash_sha256']}_{doc['chunk_index']}",
            "_source": doc,
        }
        for doc in documents
    ]

    success_count, _ = bulk(client, actions, raise_on_error=False)
    return success_count


def delete_documents_by_hash(
    client: OpenSearch, group_id: int, hash_list: List[str]
) -> int:
    """해시값으로 문서 삭제"""
    index_name = get_index_name(group_id)

    if not client.indices.exists(index=index_name):
        return 0

    response = client.delete_by_query(
        index=index_name,
        body={"query": {"terms": {"hash_sha256": hash_list}}},
        request_timeout=120,  # 대량 삭제를 위해 120초로 설정
    )

    return response["deleted"]


def delete_chunk_by_doc_id(
    client: OpenSearch, group_id: int, hash_sha256: str, chunk_index: int
) -> int:
    """BM25 인덱스에서 청크 단위 삭제

    Args:
        client: OpenSearch 클라이언트
        group_id: 그룹 ID
        hash_sha256: 문서 해시
        chunk_index: 청크 인덱스

    Returns:
        삭제된 문서 수 (1: 성공, 0: 미존재)
    """
    index_name = get_index_name(group_id)

    if not client.indices.exists(index=index_name):
        return 0

    doc_id = f"{hash_sha256}_{chunk_index}"

    try:
        client.delete(index=index_name, id=doc_id)
        return 1
    except NotFoundError:
        return 0


def search_bm25(
    client: OpenSearch,
    group_id: int,
    query: str,
    role_ids: List[int],
    current_time: int,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """BM25 검색 실행"""
    if not query or not query.strip():
        return []

    index_name = get_index_name(group_id)

    if not client.indices.exists(index=index_name):
        return []

    search_query = {
        "bool": {
            "must": [
                {
                    "match": {
                        "page_content": {
                            "query": query,
                            "analyzer": "korean_analyzer",
                        }
                    }
                }
            ],
            "filter": [
                {"terms": {"role_ids": role_ids}},
                {"range": {"expiration_date": {"gte": current_time}}},
            ],
        }
    }

    response = client.search(
        index=index_name,
        body={
            "query": search_query,
            "size": top_k,
        },
    )

    results = []
    for hit in response["hits"]["hits"]:
        doc = hit["_source"]
        doc["score"] = hit["_score"]
        results.append(doc)

    return results


def search_with_filter(
    client: OpenSearch,
    group_id: int,
    query: str,
    role_ids: List[int],
    current_time: int,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    BM25 검색 + 권한 필터링 수행 (HybridSearchService 호환용)

    기존 BM25Service.search_with_filter()와 동일한 반환 형식을 유지합니다.

    Args:
        client: OpenSearch 클라이언트
        group_id: 그룹 ID
        query: 검색 쿼리
        role_ids: 사용자 역할 ID 리스트
        current_time: 현재 시간 (Unix timestamp)
        top_k: 반환할 최대 결과 수

    Returns:
        검색 결과 리스트 (document, score, metadata 포함)
    """
    results = search_bm25(
        client=client,
        group_id=group_id,
        query=query,
        role_ids=role_ids,
        current_time=current_time,
        top_k=top_k,
    )

    if not results:
        return []

    # 점수 정규화
    raw_scores = [r["score"] for r in results]
    normalized = normalize_scores(raw_scores)

    # 기존 BM25Service.search_with_filter() 반환 형식에 맞춤
    formatted_results = []
    for result, norm_score in zip(results, normalized):
        doc = Document(
            page_content=result["page_content"],
            metadata={
                "hash_sha256": result["hash_sha256"],
                "title": result["title"],
                "filename": result["filename"],
                "page_number": result["page_number"],
                "chunk_index": result["chunk_index"],
                "category": result["category"],
            },
        )
        formatted_results.append(
            {
                "document": doc,
                "score": norm_score,
                "id": result.get("milvus_id"),
                "hash_sha256": result["hash_sha256"],
                "title": result["title"],
                "filename": result["filename"],
                "page_number": result["page_number"],
                "chunk_index": result["chunk_index"],
            }
        )

    return formatted_results


def normalize_scores(raw_scores: List[float]) -> List[float]:
    """
    BM25 점수를 3단계로 정규화 (0~1 범위)

    Step 1: log1p 변환 (점수 분포 압축)
    Step 2: 분포 기반 게이트 (하위 20% percentile 이하 제거)
    Step 3: Min-Max 정규화

    Args:
        raw_scores: 원본 BM25 점수 리스트

    Returns:
        정규화된 점수 리스트 (0~1 범위)
    """
    if not raw_scores:
        return []

    if len(raw_scores) == 1:
        return [1.0]

    # Step 1: log1p 변환 (점수 분포 압축)
    log_scores = [math.log1p(score) for score in raw_scores]
    logger.debug(f"Step 1 (log1p): {raw_scores} → {log_scores}")

    # Step 2: 분포 기반 게이트 (하위 20% percentile 이하 제거)
    # 결과가 3개 이상일 때만 게이트 적용
    if len(log_scores) >= 3:
        percentile_20 = float(np.percentile(log_scores, 20))
        gated_scores = [s if s > percentile_20 else 0.0 for s in log_scores]
        logger.debug(f"Step 2 (gate p20={percentile_20:.4f}): {gated_scores}")
    else:
        # 2개 이하일 때는 게이트 없이 log1p 점수를 그대로 사용
        gated_scores = log_scores
        logger.debug(f"Step 2 (skip gate, n={len(log_scores)}): {gated_scores}")

    # Step 3: 정규화
    non_zero_scores = [s for s in gated_scores if s > 0]

    if not non_zero_scores:
        logger.debug("Step 3: 모든 점수가 게이트에서 제거됨")
        return [0.0] * len(raw_scores)

    max_score = max(non_zero_scores)

    # 2개 이하일 때는 Max 기준 비율 정규화 (극단적 분포 방지)
    if len(raw_scores) <= 2:
        normalized = [s / max_score for s in gated_scores]
        logger.debug(f"Step 3 (ratio to max): {normalized}")
        return normalized

    min_score = min(non_zero_scores)

    if max_score == min_score:
        return [0.5 if s > 0 else 0.0 for s in gated_scores]

    # 3개 이상일 때는 Min-Max 정규화
    normalized = []
    for score in gated_scores:
        if score == 0:
            normalized.append(0.0)
        else:
            norm_score = (score - min_score) / (max_score - min_score)
            normalized.append(norm_score)

    logger.debug(f"Step 3 (min-max): {normalized}")
    return normalized
