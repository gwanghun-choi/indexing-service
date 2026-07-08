"""
임베딩 롤백 서비스

임베딩 파이프라인 실행 전 상태(registered)로 문서를 되돌립니다.
"""

import asyncio
import logging
from typing import Dict, List, Tuple

from app.config.constants import DEFAULT_VECTOR_DIMENSION
from app.crud.milvus.document_crud import (
    select_documents,
    update_documents_batch,
    delete_vectors,
    delete_vectors_by_ids,
)
from app.dto.document_status import DocumentStatus
from opensearchpy import OpenSearch

from app.service.opensearch_bm25_service import (
    create_opensearch_client,
    delete_documents_by_hash,
)
from app.worker.utils.async_runner import run_async

logger = logging.getLogger(__name__)


async def rollback_inserted_artifacts(
    group_id: int,
    inserted_ids: List[int],
    hash_sha256: str,
) -> Dict[str, int]:
    """이번 실행 산출물 정리: Milvus vector(id 기준) + 해당 문서 BM25(hash 기준).

    R-02: Milvus vector insert 성공 후 OpenSearch BM25 색인이 실패했을 때 호출한다.
    - 1순위: 이번 실행에서 insert된 vector를 id로 삭제(dense 노출 제거, 가장 신뢰도 높음)
    - 2순위: 해당 문서의 BM25를 hash로 정리(부분 색인된 sparse 노출 제거, best-effort)
    hash 기준 전체 vector 삭제(delete_vectors)는 사용하지 않으며 meta/status도 건드리지 않는다.

    Args:
        group_id: 그룹 ID
        inserted_ids: 이번 실행에서 insert된 Milvus PK(id) 리스트
        hash_sha256: 해당 문서 해시

    Returns:
        Dict[str, int]: {"deleted_vectors", "deleted_bm25_docs"}
    """
    # 1순위: 이번 실행 vector(id) 삭제 — Milvus 삭제는 신뢰도가 높아 먼저 확실히 정리
    deleted_vectors = await delete_vectors_by_ids(group_id, inserted_ids)

    # 2순위: 해당 문서 BM25 정리(best-effort). 동기 opensearch-py는 to_thread로 래핑
    os_client = create_opensearch_client()
    try:
        deleted_bm25 = await asyncio.to_thread(
            delete_documents_by_hash,
            client=os_client,
            group_id=group_id,
            hash_list=[hash_sha256],
        )
    finally:
        os_client.close()

    logger.info(
        f"✅ 이번 실행 산출물 롤백 완료: group_id={group_id}, "
        f"vector={deleted_vectors}개, bm25={deleted_bm25}개"
    )
    return {"deleted_vectors": deleted_vectors, "deleted_bm25_docs": deleted_bm25}


def try_rollback_run_artifacts(params: dict) -> None:
    """orchestrator except용 동기 래퍼 — 이번 실행 산출물을 best-effort로 정리한다.

    원래 실패 원인을 덮어쓰지 않도록 절대 예외를 던지지 않는다(로그만 남김).
    transformed_data가 없으면(임베딩 이전 단계 실패) no-op.

    Args:
        params: 파이프라인 매개변수(group_id, hash_sha256, transformed_data 사용)
    """
    inserted_ids = [
        item["id"]
        for item in params.get("transformed_data", [])
        if item.get("id") is not None
    ]
    if not inserted_ids:
        return

    try:
        run_async(
            rollback_inserted_artifacts(
                group_id=params["group_id"],
                inserted_ids=inserted_ids,
                hash_sha256=params["hash_sha256"],
            )
        )
    except Exception:
        logger.exception(
            "[rollback] ❌ 이번 실행 인덱싱 산출물 롤백 실패 — 원래 실패 원인 유지"
        )

# 롤백 가능한 상태 정의 (성능 가이드 Section 2: tuple이 list보다 5-10% 빠름)
ROLLBACK_ALLOWED_STATUSES = (
    DocumentStatus.UPLOADED,
    DocumentStatus.FAILED,
    DocumentStatus.RUNNING,
    DocumentStatus.OCR_REQUIRED,
    DocumentStatus.SKIPPED,
)

# 성능 최적화: frozenset으로 O(1) membership check (코드 컨벤션 Section 8.2)
ROLLBACK_ALLOWED_STATUS_VALUES = frozenset(s.value for s in ROLLBACK_ALLOWED_STATUSES)


async def rollback_embeddings(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    hash_sha256_list: List[str],
) -> Dict:
    """
    임베딩 롤백 - 문서를 registered 상태로 되돌립니다.

    처리 순서:
    1. 문서 조회 및 상태 검증
    2. BM25 인덱스에서 문서 제거 (막힐 위험이 큰 쪽을 먼저)
    3. Vector 컬렉션에서 청크+벡터 삭제
    4. Meta 컬렉션 초기화 (summary 등 + status → registered)

    split-brain 방지: BM25 → Vector 순차 삭제. 한쪽이 실패하면 다음 단계를
    진행하지 않고 즉시 중단한다. 삭제는 멱등이므로 원인(예: OpenSearch
    디스크 가득참) 해소 후 롤백을 재실행하면 남은 쪽이 마저 정리된다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 역할 ID 리스트
        hash_sha256_list: 롤백할 문서의 해시값 리스트

    Returns:
        Dict: 롤백 결과
            - success_count: 성공한 문서 수
            - failed_count: 실패한 문서 수
            - deleted_vectors: 삭제된 벡터 수
            - deleted_bm25_docs: BM25에서 삭제된 문서 수
            - valid_docs: 롤백 성공한 문서 리스트
            - failed_docs: 롤백 실패한 문서 리스트
    """
    os_client = None

    try:
        logger.info(
            f"🔄 임베딩 롤백 시작: group_id={group_id}, 문서 수={len(hash_sha256_list)}"
        )

        # 1. 문서 조회 및 상태 검증
        valid_docs, failed_docs = await _validate_rollback_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=role_ids,
            hash_sha256_list=hash_sha256_list,
        )

        if not valid_docs:
            logger.warning(f"⚠️ 롤백 가능한 문서 없음: 실패 {len(failed_docs)}개")
            return {
                "success_count": 0,
                "failed_count": len(failed_docs),
                "deleted_vectors": 0,
                "deleted_bm25_docs": 0,
                "valid_docs": [],
                "failed_docs": failed_docs,
            }

        valid_hashes = [doc["hash_sha256"] for doc in valid_docs]

        # OpenSearch 클라이언트 미리 생성 (병렬 실행 전)
        os_client = create_opensearch_client()

        # 2~3. 순차 삭제 (split-brain 방지).
        # flood-stage(디스크 가득참)로 막히는 건 항상 BM25 쪽이므로 BM25를 "먼저"
        # 시도한다. BM25가 실패하면 Milvus는 손대지 않고 즉시 중단 → 반쪽 삭제 예방.
        deleted_bm25 = await _delete_bm25_documents_safe(
            os_client, group_id, valid_hashes
        )
        deleted_vectors = await _delete_vectors_safe(group_id, valid_hashes)

        logger.info(
            f"✅ 삭제 완료: BM25={deleted_bm25}개, Vector={deleted_vectors}개"
        )

        # 4. Meta 컬렉션 초기화
        await _reset_meta_documents(
            group_id=group_id,
            role_ids=role_ids,
            valid_docs=valid_docs,
        )

        logger.info(
            f"✅ 임베딩 롤백 완료: 성공 {len(valid_docs)}개, 실패 {len(failed_docs)}개"
        )

        return {
            "success_count": len(valid_docs),
            "failed_count": len(failed_docs),
            "deleted_vectors": deleted_vectors,
            "deleted_bm25_docs": deleted_bm25,
            "valid_docs": valid_docs,
            "failed_docs": failed_docs,
        }

    except Exception as e:
        logger.error(f"❌ 임베딩 롤백 중 오류: {e}")
        raise

    finally:
        if os_client:
            os_client.close()


async def _delete_bm25_documents(
    os_client: OpenSearch,
    group_id: int,
    hash_list: List[str],
) -> int:
    """
    BM25 인덱스에서 문서 삭제

    opensearch-py는 동기 라이브러리이므로 asyncio.to_thread로 래핑하여
    이벤트 루프 블로킹을 방지합니다.

    Args:
        os_client: OpenSearch 클라이언트
        group_id: 그룹 ID
        hash_list: 삭제할 문서 해시 리스트

    Returns:
        int: 삭제된 문서 수
    """
    return await asyncio.to_thread(
        delete_documents_by_hash,
        client=os_client,
        group_id=group_id,
        hash_list=hash_list,
    )


async def _delete_bm25_documents_safe(
    os_client: OpenSearch,
    group_id: int,
    hash_list: List[str],
) -> int:
    """BM25 삭제 + 실패 시 상세 로그/명확한 에러.

    BM25(먼저 시도하는 쪽)가 실패하면 RuntimeError로 중단시켜 이후 Milvus 삭제를
    막는다 → split-brain(반쪽 삭제) 예방. 아직 아무것도 삭제되지 않은 상태다.
    """
    try:
        return await _delete_bm25_documents(os_client, group_id, hash_list)
    except Exception as bm25_error:
        logger.error(
            "❌ BM25 삭제 실패 → Milvus 미삭제로 롤백 중단(split-brain 방지): "
            f"group_id={group_id}, 대상={len(hash_list)}건, "
            f"{type(bm25_error).__name__}: {bm25_error}"
        )
        raise RuntimeError(
            "BM25 인덱스 삭제 실패로 롤백을 중단했습니다(데이터 미변경). "
            "OpenSearch 디스크/상태를 확인 후 롤백을 재실행하세요. "
            f"원인: {type(bm25_error).__name__}: {bm25_error}"
        ) from bm25_error


async def _delete_vectors_safe(
    group_id: int,
    hash_list: List[str],
) -> int:
    """Milvus 벡터 삭제 + 실패 시 상세 로그/명확한 에러.

    이 단계 실패 시 BM25는 이미 삭제된 상태다. 삭제는 멱등이므로 롤백을
    재실행하면 BM25는 0건(no-op)으로 통과하고 남은 Milvus 벡터가 정리되어 수렴한다.
    """
    try:
        return await delete_vectors(group_id=group_id, hash_sha256_list=hash_list)
    except Exception as milvus_error:
        logger.error(
            "❌ Milvus 벡터 삭제 실패(BM25는 삭제됨, 롤백 재실행으로 복구 가능): "
            f"group_id={group_id}, 대상={len(hash_list)}건, "
            f"{type(milvus_error).__name__}: {milvus_error}"
        )
        raise RuntimeError(
            "Milvus 벡터 삭제 실패로 롤백을 중단했습니다"
            "(BM25는 삭제됨 — 롤백 재실행 시 나머지 정리). "
            f"원인: {type(milvus_error).__name__}: {milvus_error}"
        ) from milvus_error


async def _validate_rollback_documents(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    hash_sha256_list: List[str],
) -> Tuple[List[Dict], List[Dict]]:
    """
    롤백 대상 문서 검증

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 역할 ID 리스트
        hash_sha256_list: 검증할 문서 해시값 리스트

    Returns:
        Tuple[List[Dict], List[Dict]]: (유효한 문서 리스트, 실패한 문서 리스트)
    """
    # 문서 조회
    documents = await select_documents(
        group_id=group_id,
        user_id=user_id,
        role_ids=role_ids,
        db_type="meta",
        hash_sha256_option=hash_sha256_list,
    )

    # 조회된 문서를 hash_sha256로 매핑
    doc_map = {doc["hash_sha256"]: doc for doc in documents}

    valid_docs = []
    failed_docs = []

    # 상태 검증
    for hash_sha256 in hash_sha256_list:
        if hash_sha256 not in doc_map:
            failed_docs.append({
                "hash_sha256": hash_sha256,
                "reason": "문서를 찾을 수 없습니다",
            })
            continue

        doc = doc_map[hash_sha256]
        doc_status = doc["status"]

        # 성능 최적화: frozenset으로 O(1) membership check (코드 컨벤션 Section 8.2)
        if doc_status not in ROLLBACK_ALLOWED_STATUS_VALUES:
            failed_docs.append({
                "hash_sha256": hash_sha256,
                "title": doc["title"],
                "reason": f"문서 상태가 롤백 가능 상태가 아닙니다 (현재: {doc_status})",
            })
            continue

        valid_docs.append(doc)

    return valid_docs, failed_docs


async def _reset_meta_documents(
    group_id: int,
    role_ids: List[int],
    valid_docs: List[Dict],
) -> None:
    """
    Meta 컬렉션의 문서 정보 초기화

    임베딩 파이프라인 실행 전 상태(registered)로 모든 필드를 초기화합니다.

    Args:
        group_id: 그룹 ID
        role_ids: 역할 ID 리스트
        valid_docs: 초기화할 문서 리스트
    """
    # 초기화할 데이터 정의
    update_data = {
        # 상태 필드
        "status": DocumentStatus.REGISTERED,
        # 요약 관련 필드
        "summary": "",
        "summary_token": 0,
        "summary_cost": 0.0,
        # 청크/토큰 관련 필드
        "chunk_count": 0,
        "token": 0,
        "cost": 0.0,
        # 임베딩 시간 필드
        "embedding_start_date": 0,
        "embedding_end_date": 0,
        # 청크 카운트 필드
        "original_chunk_count": 0,
        "filtered_chunk_count": 0,
        # 청크 설정 필드
        "chunk_size": 0,
        "chunk_overlap": 0,
        # 비식별화 관련 필드
        "anonymization_strategy": "",
        "enable_pii_anonymization": 0,
        "pii_types": "",
        # 임베딩 벡터 (코드 컨벤션: Magic Number 상수화)
        "embedding_value": [0.0] * DEFAULT_VECTOR_DIMENSION,
    }

    # 해시 리스트 추출
    hash_list = [doc["hash_sha256"] for doc in valid_docs]

    # 배치 업데이트로 한 번에 처리 (N번 → 1번 Milvus 호출)
    updated_count = await update_documents_batch(
        group_id=group_id,
        hash_sha256_list=hash_list,
        update_data=update_data,
        include_embedding_value=False,
    )

    logger.info(f"✅ Meta 초기화 완료: {updated_count}개 문서")
