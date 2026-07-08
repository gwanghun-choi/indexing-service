import logging
import time

from app.config.constants import DEFAULT_VECTOR_DIMENSION
from app.crud.milvus.document_crud import create_document
from app.crud.postgres.user_crud import select_embedding_models
from app.embedding.factory import create_embedding
from app.service.opensearch_bm25_service import (
    bulk_index_documents,
    create_opensearch_client,
    ensure_index_exists,
)
from app.service.persona_service import PersonaService
from app.service.simulate_cost import CostSimulator, count_tokens, model_registry
from app.worker.celery import app
from app.worker.utils.async_runner import run_async

logger = logging.getLogger(__name__)


def _validate_embedding_vectors(vector_list: list, expected_count: int) -> None:
    """임베딩 결과 벡터를 검증한다 (빈 벡터/차원 불일치 조기 차단).

    create_embedding이 빈 벡터([])나 잘못된 차원을 반환하더라도, Milvus insert
    전에 여기서 예외를 발생시켜 임베딩 단계에서 즉시 실패시킨다.

    Args:
        vector_list: 임베딩 벡터 리스트
        expected_count: 기대하는 벡터 개수 (입력 텍스트 개수)

    Raises:
        ValueError: 벡터가 None/개수 불일치/빈 벡터/차원 불일치인 경우
    """
    if vector_list is None:
        raise ValueError("임베딩 벡터 리스트가 None입니다")

    if len(vector_list) != expected_count:
        raise ValueError(
            f"임베딩 개수 불일치: expected={expected_count}, actual={len(vector_list)}"
        )

    for idx, vector in enumerate(vector_list):
        if vector is None:
            raise ValueError(f"임베딩 벡터가 None입니다: index={idx}")

        if not hasattr(vector, "__len__"):
            raise ValueError(
                f"임베딩 벡터가 시퀀스가 아닙니다: index={idx}, type={type(vector)}"
            )

        # numpy array 모호성 방지를 위해 명시적으로 len() 비교
        if len(vector) == 0:
            raise ValueError(f"빈 임베딩 벡터 반환됨: index={idx}")

        if len(vector) != DEFAULT_VECTOR_DIMENSION:
            raise ValueError(
                f"임베딩 차원 불일치: index={idx}, "
                f"expected={DEFAULT_VECTOR_DIMENSION}, actual={len(vector)}"
            )


@app.task(time_limit=600, soft_time_limit=570, max_retries=3, default_retry_delay=30)
def filter_chunks_with_persona(params: dict) -> dict:
    """
    페르소나 기반으로 청크를 필터링합니다.

    타임아웃:
    - soft_time_limit: 9분 30초 - 정상 종료 시도
    - time_limit: 10분 - 강제 종료
    """
    try:
        logger.info("[pipeline] 🎯 페르소나 기반 청크 필터링 시작...")

        # 페르소나 ID 없으면 전체 청크 사용
        if not params["persona_id"]:
            logger.info("[pipeline] 페르소나 ID 없음 - 전체 청크 사용")
            chunks = params.get("text_chunks", [])
            params["original_chunk_count"] = len(chunks)
            params["filtered_chunk_count"] = len(chunks)
            params["skip_embedding"] = False
            return params

        persona_id = params["persona_id"]
        filter_score = params["filter_score"]
        chunks = params["text_chunks"]

        if not chunks:
            logger.warning("[pipeline] ⚠️ 필터링할 청크가 없음")
            params["skip_embedding"] = True
            return params

        logger.info(
            f"[pipeline] 📊 페르소나 {persona_id} 기준으로 {len(chunks)}개 청크 필터링"
        )

        # 페르소나 기반 필터링 수행
        persona_service = PersonaService()
        persona_service.set_worker_context(True)

        filter_result = run_async(
            persona_service.filter_chunks_for_persona(
                chunks=chunks,
                persona_id=persona_id,
                filter_score=filter_score,
            )
        )

        filtered_chunks = filter_result["relevant_chunks"]
        reduction_rate = filter_result["cost_reduction"]["reduction_rate"]

        # 선택된 청크가 없으면 파이프라인 중단
        if not filtered_chunks:
            logger.warning(f"[pipeline] ⚠️ 페르소나 {persona_id}와 관련된 청크 없음")

            params["skip_embedding"] = True
            params["skip_reason"] = "no_relevant_chunks_for_persona"
            params["original_chunk_count"] = len(chunks)
            params["filtered_chunk_count"] = 0
            params["cost_reduction"] = filter_result["cost_reduction"]
            return params

        # 필터링 결과 저장
        params["text_chunks"] = filtered_chunks
        params["original_chunk_count"] = len(chunks)
        params["filtered_chunk_count"] = len(filtered_chunks)
        params["cost_reduction"] = filter_result["cost_reduction"]

        logger.info(
            f"[pipeline] ✅ 필터링 완료: {len(filtered_chunks)}/{len(chunks)}개 선별 (절감률: {reduction_rate}%)"
        )
        params["skip_embedding"] = False
        return params

    except Exception as e:
        logger.error(f"[pipeline] ❌ 페르소나 필터링 중 오류 발생: {e}")
        raise


@app.task(time_limit=1800, soft_time_limit=1770, max_retries=3, default_retry_delay=60)
def generate_embeddings_task(params: dict) -> dict:
    """
    청크 데이터에 대한 임베딩을 생성하고 비용을 계산합니다.

    타임아웃:
    - soft_time_limit: 29분 30초 - 정상 종료 시도
    - time_limit: 30분 - 강제 종료
    """
    try:
        # 페르소나 필터링으로 인한 스킵 확인
        if params["skip_embedding"]:
            logger.info(f"[pipeline] ⏭️ 임베딩 생성 건너뜀: {params['skip_reason']}")
            params["status"] = "skipped"
            return params

        logger.info("[pipeline] 📊 임베딩 생성 시작...")

        # 임베딩 시작 시간 기록
        params["embedding_start_date"] = int(time.time())

        embedding_model = params["embedding_model"]
        model_name = params["model_name"]

        # 비용 시뮬레이터 초기화
        simulator = None

        # models 리스트 가져오기 및 초기화
        models = run_async(select_embedding_models(use_worker_context=True))
        if models:
            run_async(model_registry.initialize(models))
            simulator = CostSimulator()
            run_async(simulator.select_model(model_name))

        if not simulator:
            logger.warning("[pipeline] ⚠️ 모델 레지스트리 초기화 실패 - 기본 비용 사용")

        # 임베딩 생성
        vector_list = run_async(
            create_embedding(
                embedding_model,
                [c["text"] for c in params["text_chunks"]],
                model=model_name,
            )
        )

        # 빈 벡터/차원 불일치를 Milvus insert 전에 차단 (임베딩 단계에서 즉시 실패)
        _validate_embedding_vectors(
            vector_list, expected_count=len(params["text_chunks"])
        )

        logger.info(f"[pipeline] ✅ {len(vector_list)}개 임베딩 생성 완료")

        # 토큰 수와 비용 계산 (병렬 처리)
        chunks = params["text_chunks"]

        async def calculate_tokens_and_costs():
            # 토큰/비용 계산은 외부 API가 아니라 로컬 계산(tiktoken/산술)이므로
            # 청크 수만큼 한 번에 gather하지 않고 순차 처리하여 메모리 피크를 완화한다.
            # (결과/순서/폴백 로직은 기존 gather 방식과 동일)
            processed_tokens = []
            cost_results = []
            for c in chunks:
                # 1. 토큰 계산
                if simulator:
                    token = await simulator.count_tokens(c["text"], model_name)
                else:
                    token = await count_tokens(c["text"], model_name)

                # 2. 토큰 결과 처리 (None/0인 경우 대체값 사용)
                token = token or len(c["text"].split()) // 2
                processed_tokens.append(token)

                # 3. 비용 계산
                if simulator:
                    cost = await simulator.simulate_embedding_cost(token, model_name)
                else:
                    cost = (token / 1000) * 0.0001
                cost_results.append(cost)

            return processed_tokens, cost_results

        token_list, cost_list = run_async(calculate_tokens_and_costs())

        # 결과 병합
        total_tokens = 0
        total_cost = 0

        for i, content in enumerate(chunks):
            content["vector"] = vector_list[i]
            content["token"] = token_list[i]
            content["cost"] = cost_list[i]
            total_tokens += token_list[i]
            total_cost += cost_list[i]

        # 임베딩 종료 시간 기록
        params["embedding_end_date"] = int(time.time())

        logger.info(
            f"[pipeline] 💰 총 토큰: {total_tokens}, 총 비용: ${total_cost:.6f}"
        )
        logger.info(
            f"[pipeline] ⏱️ 임베딩 소요 시간: {params['embedding_end_date'] - params['embedding_start_date']}초"
        )

        params["total_tokens"] = total_tokens
        params["total_cost"] = total_cost
        params["status"] = "embedded"

        return params
    except Exception as e:
        # 실패 사유를 params["error"]에 실어 기존 update_failed_status의 SSE 메시지에 노출
        # (스키마 변경 없음, 기존 실패 처리 흐름 그대로 재사용)
        params["error"] = str(e)
        logger.exception("[pipeline] ❌ 임베딩 생성 중 오류 발생")
        raise


@app.task(time_limit=300, soft_time_limit=285, max_retries=3, default_retry_delay=30)
def transform_data_task(params: dict) -> dict:
    """
    Milvus에 맞는 데이터 형태로 변환합니다.

    타임아웃:
    - soft_time_limit: 4분 45초 - 정상 종료 시도
    - time_limit: 5분 - 강제 종료
    """
    try:
        # 페르소나 필터링으로 인한 스킵 확인
        if params["skip_embedding"]:
            logger.info(f"[pipeline] ⏭️ 데이터 변환 건너뜀: {params['skip_reason']}")
            params["status"] = "skipped"
            params["transformed_data"] = []
            return params

        logger.info(
            f"[pipeline] 📊 데이터 변환 시작... "
            f"hash={params['hash_sha256'][:16]}..., category={params['category']}"
        )

        # 데이터 변환
        transformed_data = [
            {
                "category": params["category"],
                "title": params["title"],
                "filename": params["filename"],
                "embedding_value": content["vector"],
                "parsed_text": content["text"],
                "page_number": content["page_number"],
                "chunk_index": content["chunk_index"],
                "token": content["token"],
                "cost": content["cost"],
                "group_id": int(params["group_id"]),
                "user_id": int(params["user_id"]),
                "role_ids": params["total_role"],
                "hash_sha256": params["hash_sha256"],
                "date": int(time.time()),
            }
            for content in params["text_chunks"]
        ]

        params["transformed_data"] = transformed_data
        # 최종 상태 업데이트용 chunk_count 선저장(transformed_data 제거 대비)
        params["chunk_count"] = len(transformed_data)
        # text_chunks는 transformed_data 생성 이후 미사용 → 메모리 해제
        params.pop("text_chunks", None)
        logger.info(f"[pipeline] ✅ 데이터 변환 완료: {len(transformed_data)}개")
        return params
    except Exception as e:
        logger.error(f"[pipeline] ❌ 데이터 변환 중 오류 발생: {e}")
        raise


@app.task(time_limit=600, soft_time_limit=570, max_retries=3, default_retry_delay=30)
def insert_to_milvus_task(params: dict) -> dict:
    """
    Milvus에 데이터를 삽입합니다.

    타임아웃:
    - soft_time_limit: 9분 30초 - 정상 종료 시도
    - time_limit: 10분 - 강제 종료
    """
    try:
        # 페르소나 필터링으로 인한 스킵 확인
        if params["skip_embedding"]:
            logger.info(f"[pipeline] ⏭️ Milvus 삽입 건너뜀: {params['skip_reason']}")
            logger.info(
                f"[pipeline] 📊 필터링 통계 - 원본: {params['original_chunk_count']}개, 선택: {params['filtered_chunk_count']}개"
            )
            params["status"] = "skipped_no_data"
            return params

        # 삽입할 데이터 확인
        transformed_data = params["transformed_data"]
        if not transformed_data:
            logger.warning("[pipeline] ⚠️ 삽입할 데이터가 없음")
            params["status"] = "skipped_empty_data"
            return params

        logger.info("[pipeline] 📊 Milvus 데이터 삽입 시작...")

        # 임베딩은 항상 vector 컬렉션에 저장
        db_type = "vector"
        collection_header = f"TB_{params['group_id']}"
        collection_name = f"{collection_header}_{db_type}"

        inserted_ids = run_async(create_document(collection_name, db_type, transformed_data))

        # Milvus PK를 transformed_data에 역주입 (BM25 인덱싱에서 사용)
        for item, milvus_id in zip(transformed_data, inserted_ids):
            item["id"] = milvus_id

        logger.info(f"[pipeline] ✅ Milvus에 {len(transformed_data)}개 삽입 완료")
        return params

    except Exception as e:
        logger.error(f"[pipeline] ❌ Milvus 데이터 삽입 중 오류 발생: {e}")
        raise


@app.task(time_limit=300, soft_time_limit=285, max_retries=3, default_retry_delay=30)
def update_bm25_index_task(params: dict) -> dict:
    """
    OpenSearch BM25 인덱스를 업데이트합니다.

    새로 임베딩된 문서의 청크를 OpenSearch BM25 인덱스에 추가합니다.

    타임아웃:
    - soft_time_limit: 4분 45초 - 정상 종료 시도
    - time_limit: 5분 - 강제 종료
    """
    os_client = None

    try:
        # 페르소나 필터링으로 인한 스킵 확인
        if params["skip_embedding"]:
            logger.info(
                f"[pipeline] ⏭️ BM25 인덱스 업데이트 건너뜀: {params['skip_reason']}"
            )
            return params

        # 데이터 확인
        transformed_data = params["transformed_data"]
        if not transformed_data:
            logger.warning("[pipeline] ⚠️ BM25 업데이트할 데이터가 없음")
            return params

        logger.info("[pipeline] 🔨 OpenSearch BM25 인덱스 업데이트 시작...")

        # OpenSearch 클라이언트 생성
        os_client = create_opensearch_client()

        group_id = params["group_id"]

        # 인덱스 존재 확인 및 생성
        ensure_index_exists(os_client, group_id)

        # OpenSearch에 인덱싱할 문서 형식으로 변환
        documents = [
            {
                "milvus_id": item["id"],
                "page_content": item["parsed_text"],
                "hash_sha256": item["hash_sha256"],
                "title": item["title"],
                "filename": item["filename"],
                "page_number": item["page_number"],
                "chunk_index": item["chunk_index"],
                "category": item["category"],
                "role_ids": params["total_role"],
                "expiration_date": params["expiration_date"],
                "group_id": group_id,
            }
            for item in transformed_data
        ]

        # OpenSearch 벌크 인덱싱
        success_count = bulk_index_documents(os_client, group_id, documents)

        # BM25 실패 승격: bulk는 raise_on_error=False라 부분/전체 실패에도 예외가 없다.
        # success_count가 전체 문서 수와 다르면 RuntimeError로 승격해, orchestrator
        # except에서 이번 실행 Milvus 산출물을 롤백하도록 한다(split-brain 방지).
        expected_count = len(documents)
        if success_count != expected_count:
            raise RuntimeError(
                f"BM25 색인 불완전: expected={expected_count}, success={success_count} "
                f"(flood-stage/디스크풀/read-only block 등 의심)"
            )

        logger.info(
            f"[pipeline] ✅ OpenSearch BM25 인덱스 업데이트 완료: {success_count}개 청크 추가"
        )
        # Milvus insert + BM25 색인 정상 완료 후 transformed_data는 미사용 → 메모리 해제
        # (최종 상태 업데이트는 선저장된 params["chunk_count"] 사용)
        params.pop("transformed_data", None)
        return params

    except Exception as e:
        logger.error(f"[pipeline] ❌ BM25 인덱스 업데이트 중 오류 발생: {e}")
        raise

    finally:
        if os_client:
            os_client.close()
            logger.debug("✅ OpenSearch 연결 종료")
