import logging

from celery.exceptions import Ignore

from app.worker.celery import app
from app.worker.utils.initialize_collection import initialize_collection_task
from app.service.utils.cleanup import cleanup_params, cleanup_temp_file
from app.worker.document_task import (
    download_document,
    extract_metadata,
    check_duplicate,
    insert_initial_metadata,
    parse_document_task,
    generate_document_summary,
    update_final_status,
    update_failed_status,
)
from app.worker.embedding_task import (
    filter_chunks_with_persona,
    generate_embeddings_task,
    transform_data_task,
    insert_to_milvus_task,
    update_bm25_index_task,
)
from app.service.embedding_rollback_service import try_rollback_run_artifacts
from app.utils.notification import create_notifier

logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    time_limit=3600,
    soft_time_limit=3540,
    max_retries=3,
    default_retry_delay=60,
)
def run_integrated_pipeline(self, params: dict):
    """
    통합 모드 문서 처리 파이프라인 실행 (등록 + 임베딩 한번에).

    문서 다운로드부터 메타데이터 등록, 임베딩 생성까지 전체 과정을 수행합니다.
    페르소나가 지정된 경우 선택적 청크 필터링을 적용합니다.

    타임아웃:
    - soft_time_limit: 59분 - 정상 종료 시도
    - time_limit: 60분 - 강제 종료
    """
    # SSE 알림 헬퍼 생성 (task_id 기반)
    notifier = create_notifier(params)

    try:
        # 📚 Phase 1: 초기화 및 기본 설정 (Foundation Setup)
        notifier.initializing()
        params = initialize_collection_task.run(params)

        notifier.downloading()
        params = download_document.run(params)

        notifier.extracting_metadata()
        params = extract_metadata.run(params)

        notifier.checking_duplicate()
        params = check_duplicate.run(params)

        notifier.saving_metadata()
        params = insert_initial_metadata.run(params)

        # 🤖 Phase 2: 문서 처리 및 AI 분석 (AI Document Processing)
        notifier.parsing()
        params = parse_document_task.run(params)

        notifier.generating_summary()
        params = generate_document_summary.run(params)

        notifier.filtering_persona()
        params = filter_chunks_with_persona.run(params)

        # 🔢 Phase 3: 벡터화 및 저장 (Vectorization & Persistence)
        notifier.embedding()
        params = generate_embeddings_task.run(params)

        notifier.transforming()
        params = transform_data_task.run(params)

        notifier.inserting()
        params = insert_to_milvus_task.run(params)

        # 🔍 BM25 인덱스 업데이트 (검색 정확도 향상)
        params = update_bm25_index_task.run(params)

        # ✅ Phase 4: 완료 처리 및 알림 (Finalization)
        notifier.finalizing()
        params = update_final_status.run(params)

        notifier.completed()
        return params

    except Exception as e:
        # Ignore 예외(중복 문서, OCR 필요 등)는 정상 종료로 처리
        if isinstance(e, Ignore):
            return params

        # R-02: Milvus insert 이후 단계(BM25 등) 실패 시, 이번 실행 산출물
        # (vector id + 해당 문서 BM25)만 정리해 split-brain을 방지한다.
        # 절대 예외를 던지지 않으므로 아래 기존 실패 처리 흐름은 그대로 유지된다.
        try_rollback_run_artifacts(params)

        # 실패 처리
        notifier.failed()
        update_failed_status.run(params)
        cleanup_temp_file(params)
        raise e

    finally:
        # 파이프라인 완료 후 메모리 정리
        cleanup_params(params)
