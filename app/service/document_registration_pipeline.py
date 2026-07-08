import logging

from celery.exceptions import Ignore

from app.worker.celery import app
from app.worker.utils.initialize_collection import initialize_collection_task
from app.service.utils.cleanup import cleanup_temp_file
from app.worker.document_task import (
    download_document,
    extract_metadata,
    check_duplicate,
    insert_initial_metadata,
    update_registration_status,
    update_failed_status,
)
from app.utils.notification import create_notifier

logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    time_limit=600,
    soft_time_limit=570,
    max_retries=3,
    default_retry_delay=60,
)
def run_document_registration_pipeline(self, params: dict):
    """
    문서 등록 파이프라인 (분리 모드) - 메타데이터 저장까지만 수행.

    문서를 임시로 다운로드하여 메타데이터를 추출하고 meta 컬렉션에 저장합니다.
    임베딩은 생성하지 않으며, 사용자가 나중에 별도로 요청할 수 있습니다.

    타임아웃:
    - soft_time_limit: 9분 30초 - 정상 종료 시도
    - time_limit: 10분 - 강제 종료
    """
    # SSE 알림 헬퍼 생성 (task_id 기반)
    notifier = create_notifier(params)

    try:
        # 📚 Phase 1: 초기화 및 메타데이터 등록
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

        # ✅ Phase 2: 등록 완료 처리
        notifier.finalizing()
        params = update_registration_status.run(params)

        notifier.completed()
        return params

    except Exception as e:
        # Ignore 예외(중복 문서, OCR 필요 등)는 정상 종료로 처리
        if isinstance(e, Ignore):
            return params

        # 실패 처리
        notifier.failed()
        update_failed_status.run(params)
        cleanup_temp_file(params)
        raise e
