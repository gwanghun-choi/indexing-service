"""
RAGAS 평가 Celery 태스크

평가를 백그라운드에서 실행하고 결과를 DB에 저장합니다.
"""

import asyncio
import base64
import io
import logging
import time
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional

from zoneinfo import ZoneInfo

from app.crud.milvus.document_crud import get_hash_by_title
from app.crud.postgres.ragas_evaluation_crud import RagasEvaluationCRUD
from app.service.ragas_eval_service import (
    build_ragas_samples,
    parse_excel_dataset,
    run_ragas_evaluation,
)
from app.worker.celery import app
from app.worker.utils.async_runner import task_async_runner

logger = logging.getLogger(__name__)

SEARCH_MAX_CONCURRENCY = 10


def _get_hybrid_search_service():
    """HybridSearchService lazy import (워커 프로세스에서 지연 로드)"""
    from app.crud.milvus.search_crud import get_hybrid_search_service

    return get_hybrid_search_service()


# 테스트에서 패치할 수 있도록 모듈 레벨로 노출
get_hybrid_search_service = _get_hybrid_search_service


def _execute_evaluation(
    evaluation_id: int,
    dataset_bytes: bytes,
    config: Dict[str, Any],
) -> None:
    """
    RAGAS 평가 실행 로직 (테스트 가능한 순수 함수)

    Args:
        evaluation_id: 평가 ID
        dataset_bytes: Excel 파일 바이트
        config: 검색 설정 + 사용자 정보
    """
    crud = RagasEvaluationCRUD(use_worker_session=True)

    try:
        eval_mode = config.get("eval_mode", "retrieval")
        llm_model = config.get("llm_model", "gpt-4o")

        # 2. Excel 파싱
        dataset = parse_excel_dataset(io.BytesIO(dataset_bytes))
        logger.info(f"[RAGAS 태스크] 데이터셋 로드: {len(dataset)}건")

        # Phase 1: status→running → (generation/all) 응답 채우기 → 검색 → hash 조회를
        # 단일 이벤트 루프에서 실행한다. (여러 task_async_runner() 사용 시 루프 충돌)
        #
        # status→running 을 "가장 먼저" 박는다: 느린 agent 응답 채우기(행당 최대
        # AGENT_TIMEOUT)가 진행되는 동안에도 화면에 '진행중'이 표시되고, 리퍼의
        # pending 타임아웃이 동작 중 평가를 오살(orphaned 처리)하지 않도록 한다.
        with task_async_runner() as runner:

            async def run_pre_evaluation():
                """status 갱신 + (응답 채우기) + 검색 + hash 조회를 단일 루프에서 실행"""
                # 1. status → running (가장 먼저)
                await crud.update_status(
                    evaluation_id,
                    "running",
                    started_at=datetime.now(ZoneInfo("Asia/Seoul")),
                )

                # 2. generation/all 모드: agent(/v1/invoke)로 빈 response를 채운다.
                #    (기존값 있는 행은 보존, 실패 행은 response 없이 진행)
                if eval_mode in ("generation", "all"):
                    from app.service.ragas_agent_client import (
                        fill_responses_via_agent,
                    )

                    fill_stats = await fill_responses_via_agent(
                        dataset=dataset,
                        user_id=config["user_id"],
                        evaluation_id=evaluation_id,
                        user_passport=config["user_passport"],
                    )
                    # 생성도 0, 기존 보존도 0 → 쓸 수 있는 response가 없으면 실패 처리
                    if fill_stats["filled"] == 0 and not fill_stats["skipped"]:
                        raise ValueError(
                            "agent로부터 응답을 하나도 받지 못했습니다. "
                            f"(scenario_id / agent 상태 확인 필요, "
                            f"실패 id={fill_stats['failed']})"
                        )

                # 3. 검색 실행
                search_service = get_hybrid_search_service()
                try:
                    search_results = await _search_all(search_service, dataset, config)
                finally:
                    search_service.cleanup()

                # 4. source_document → hash_sha256 매핑
                hash_map = await _build_source_doc_hash_map(dataset, config)

                return search_results, hash_map

            all_search_results, source_doc_hash_map = runner.run(run_pre_evaluation())

        # 5. RAGAS 샘플 생성
        samples = []
        for item, search_results in zip(dataset, all_search_results):
            sample = build_ragas_samples(
                user_input=item.user_input,
                search_results=search_results,
                reference_contexts=item.reference_contexts,
                response=item.response,
            )
            samples.append(sample)

        # Phase 2: RAGAS 평가 실행 (동기, 내부적으로 자체 이벤트 루프 사용)
        eval_start = time.time()
        scores = run_ragas_evaluation(
            samples, eval_mode=eval_mode, llm_model=llm_model
        )
        duration_seconds = int(time.time() - eval_start)

        # 7. 결과 조립
        item_results = _build_item_results(dataset, all_search_results, scores, source_doc_hash_map)
        result_data = _build_result_data(item_results, duration_seconds)

        # Phase 3: DB 저장 (새로운 단일 루프)
        with task_async_runner() as runner:
            runner.run(crud.save_result(evaluation_id, result_data, item_results))

        logger.info(
            f"[RAGAS 태스크] 평가 완료: id={evaluation_id}, "
            f"items={len(dataset)}, duration={duration_seconds}s"
        )

    except Exception as e:
        logger.error(f"[RAGAS 태스크] 평가 실패: id={evaluation_id}, error={e}")
        with task_async_runner() as runner:
            runner.run(crud.save_failure(evaluation_id, str(e)))


def _extract_stem(source_document: str) -> str:
    """source_document에서 확장자를 제거하여 stem 반환"""
    return PurePosixPath(source_document).stem


async def _build_source_doc_hash_map(
    dataset: list,
    config: Dict[str, Any],
) -> Dict[str, Optional[str]]:
    """
    데이터셋의 source_document별 hash_sha256 매핑 생성

    고유 source_document stem 기준으로 조회하여 중복 쿼리를 방지한다.

    Returns:
        {source_document: hash_sha256 또는 None} 딕셔너리
    """
    group_id = config["group_id"]
    role_ids = config["total_role"]

    # 고유 source_document → stem 매핑
    unique_docs = {item.source_document for item in dataset}
    stem_map = {doc: _extract_stem(doc) for doc in unique_docs}

    # 고유 stem별 hash 조회
    stem_hash: Dict[str, Optional[str]] = {}
    for stem in set(stem_map.values()):
        stem_hash[stem] = await get_hash_by_title(group_id, role_ids, stem)

    # source_document → hash 매핑
    return {doc: stem_hash[stem] for doc, stem in stem_map.items()}


async def _search_all(
    search_service: Any,
    dataset: list,
    config: Dict[str, Any],
    max_concurrency: int = SEARCH_MAX_CONCURRENCY,
) -> List[list]:
    """
    모든 질의에 대해 병렬 검색 실행 (동시성 제한)

    Args:
        search_service: HybridSearchService 인스턴스
        dataset: 데이터셋 아이템 리스트
        config: 검색 설정
        max_concurrency: 최대 동시 검색 수 (기본 10)
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _search_one(item: Any) -> list:
        async with semaphore:
            return await search_service.search(
                query=item.user_input,
                group_id=config["group_id"],
                total_role=config["total_role"],
                limit=config["limit"],
                search_mode=config["search_mode"],
                dense_weight=config["dense_weight"],
                sparse_weight=config["sparse_weight"],
                rerank_top_n=config["rerank_top_n"],
                use_multi_query=config["use_multi_query"],
                threshold=config["threshold"],
                user_passport=config["user_passport"],
                reranker=config["reranker"],
            )

    return await asyncio.gather(*[_search_one(item) for item in dataset])


METRIC_NAMES = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")


def _build_item_results(
    dataset: list,
    all_search_results: list,
    scores: Dict[str, list],
    source_doc_hash_map: Dict[str, Optional[str]],
) -> List[Dict[str, Any]]:
    """개별 질문 결과 딕셔너리 리스트 생성"""
    n = len(dataset)
    results = []
    for i, item in enumerate(dataset):
        result = {
            "item_id": item.id,
            "user_input": item.user_input,
            "category": item.category,
            "source_document": item.source_document,
            "source_document_hash": source_doc_hash_map.get(item.source_document),
            "context_precision": scores.get("context_precision", [None] * n)[i],
            "context_recall": scores.get("context_recall", [None] * n)[i],
            "faithfulness": scores.get("faithfulness", [None] * n)[i],
            "answer_relevancy": scores.get("answer_relevancy", [None] * n)[i],
            "response": item.response,
            "reference_contexts": [
                {"text": ctx, "page_number": page}
                for ctx, page in zip(item.reference_contexts, item.reference_pages)
            ],
            "retrieved_contexts": [r["parsed_text"] for r in all_search_results[i]],
            "retrieved_chunks": [
                {
                    "id": r["id"],
                    "hash_sha256": r["hash_sha256"],
                    "chunk_index": r["chunk_index"],
                    "page_number": r["page_number"],
                    "parsed_text": r["parsed_text"],
                }
                for r in all_search_results[i]
            ],
            "num_results": len(all_search_results[i]),
        }
        results.append(result)
    return results


def _safe_mean(values: list) -> float:
    """None을 제외한 평균 계산"""
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else 0.0


def _build_result_data(
    item_results: List[Dict[str, Any]],
    duration_seconds: int,
) -> Dict[str, Any]:
    """전체 결과 데이터 (summary, by_document, by_category) 생성"""
    summary: Dict[str, float] = {}
    for metric in METRIC_NAMES:
        vals = [r[metric] for r in item_results if r[metric] is not None]
        if vals:
            summary[metric] = sum(vals) / len(vals)

    by_document = _aggregate_by_key(item_results, "source_document")
    by_category = _aggregate_by_key(item_results, "category")

    return {
        "summary": summary,
        "by_document": by_document,
        "by_category": by_category,
        "total_items": len(item_results),
        "duration_seconds": duration_seconds,
    }


def _aggregate_by_key(
    results: List[Dict[str, Any]],
    key: str,
) -> Dict[str, Any]:
    """지정 키로 그룹화하여 평균 집계"""
    from collections import defaultdict

    groups: Dict[str, list] = defaultdict(list)
    for r in results:
        groups[r[key]].append(r)

    aggregated = {}
    for group_key, items in groups.items():
        entry: Dict[str, Any] = {"count": len(items)}
        for metric in METRIC_NAMES:
            valid = [i[metric] for i in items if i[metric] is not None]
            if valid:
                entry[metric] = sum(valid) / len(valid)
        aggregated[group_key] = entry
    return aggregated


@app.task(time_limit=3600, soft_time_limit=3540, max_retries=0)
def run_ragas_evaluation_task(
    evaluation_id: int,
    dataset_base64: str,
    config: Dict[str, Any],
) -> None:
    """
    RAGAS 평가 Celery 태스크

    Args:
        evaluation_id: 평가 ID (DB)
        dataset_base64: Excel 파일 (base64 인코딩 문자열, JSON 직렬화 호환)
        config: 검색 설정 + 사용자 정보
    """
    dataset_bytes = base64.b64decode(dataset_base64)
    _execute_evaluation(evaluation_id, dataset_bytes, config)


@app.task(
    name="cleanup_stale_ragas_evaluations",
    time_limit=120,
    soft_time_limit=110,
    max_retries=0,
)
def cleanup_stale_ragas_evaluations() -> None:
    """오래된 pending/running RAGAS 평가를 failed로 정리한다 (주기 실행).

    task 유실 등으로 pending/running에 영구 정지된 레코드가 화면 무한 로딩을
    유발하는 것을 방지한다. 임계값은 settings에서 읽는다.
    """
    from app.config.settings import settings

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    pending_before = now - timedelta(minutes=settings.RAGAS_PENDING_TIMEOUT_MINUTES)
    running_before = now - timedelta(minutes=settings.RAGAS_RUNNING_TIMEOUT_MINUTES)

    crud = RagasEvaluationCRUD(use_worker_session=True)
    with task_async_runner() as runner:
        failed_ids = runner.run(
            crud.fail_stale_evaluations(pending_before, running_before)
        )

    if failed_ids:
        logger.info(
            f"[RAGAS reaper] stale 평가 {len(failed_ids)}건 자동 failed 처리: {failed_ids}"
        )
