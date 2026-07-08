import logging

from celery.exceptions import Ignore

from app.worker.celery import app
from app.service.utils.cleanup import cleanup_temp_file
from app.worker.document_task import (
    validate_document_status,
    update_status_to_running,
    download_document,
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
def run_embedding_generation_pipeline(self, params: dict):
    """
    임베딩 생성 전용 파이프라인 - 등록된 문서의 임베딩 생성.

    이미 등록된 문서(status=registered)에 대해 임베딩을 생성합니다.
    메타 컬렉션에서 download_url을 조회하여 문서를 재다운로드합니다.

    Args:
        params: 파이프라인 실행에 필요한 매개변수
            - user_id: 사용자 ID
            - hash_sha256: 문서 해시값 (SSE 통신 식별자)
            - group_id: 그룹 ID
            - role_ids: 역할 ID 목록
            - embedding_model: 임베딩 모델
            - model_name: 모델명
            - persona_id: 페르소나 ID (optional)
            - filter_score: 필터 점수 (optional)

    타임아웃:
    - soft_time_limit: 59분 - 정상 종료 시도
    - time_limit: 60분 - 강제 종료

    메모리 최적화:
    - worker_max_tasks_per_child=10: 10개 태스크 후 워커 재시작
    - worker_max_memory_per_child=512000: 512MB 초과 시 워커 재시작
    - 워커 재시작 시 OS에 메모리 완전 반환 보장
    """
    # SSE 알림 헬퍼 생성 (hash_sha256 기반)
    notifier = create_notifier(params)

    try:
        # Phase 1: 문서 검증 및 재다운로드 (Document Validation & Reload)
        notifier.validating_status()
        params = validate_document_status.run(params)

        # 문서 상태를 'running'으로 변경 (클라이언트 폴링용)
        params = update_status_to_running.run(params)

        notifier.downloading()
        params = download_document.run(params)

        # Phase 2: 문서 처리 및 AI 분석 (AI Document Processing)
        notifier.parsing()
        params = parse_document_task.run(params)

        notifier.generating_summary()
        params = generate_document_summary.run(params)

        notifier.filtering_persona()
        params = filter_chunks_with_persona.run(params)

        # Phase 3: 벡터화 및 저장 (Vectorization & Persistence)
        notifier.embedding()
        params = generate_embeddings_task.run(params)

        notifier.transforming()
        params = transform_data_task.run(params)

        notifier.inserting()
        params = insert_to_milvus_task.run(params)

        # BM25 인덱스 업데이트 (검색 정확도 향상)
        params = update_bm25_index_task.run(params)

        # Phase 4: 완료 처리 및 알림 (Finalization)
        notifier.finalizing()
        params = update_final_status.run(params)

        notifier.completed()
        return params

    except Exception as e:
        # Ignore 예외(중복 문서, OCR 필요 등)는 정상 종료로 처리
        if isinstance(e, Ignore):
            notifier.completed()
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
