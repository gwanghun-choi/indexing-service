import logging
from typing import Optional

from app.dto.pipeline_status_dto import (
    PipelineStage,
    PipelineStatus,
    STAGE_DESCRIPTIONS,
)
from app.service.redis_sse_broker import get_redis_sse_broker

logger = logging.getLogger(__name__)


# ========================================
# Pipeline Notifier Classes
# ========================================


class PipelineNotifier:
    """
    파이프라인 진행 상황을 SSE로 알리는 헬퍼 클래스.

    파이프라인 코드를 깔끔하게 유지하면서 모든 단계에서 SSE를 발행합니다.
    각 task 실행 전에 적절한 메서드를 호출하여 자동으로 description을 포함한 SSE 메시지를 발행합니다.
    """

    def __init__(
        self, task_id: str, user_id: str, hash_sha256: str = "", category: str = ""
    ):
        """
        Args:
            task_id: 작업 ID
            user_id: 사용자 ID
            hash_sha256: 문서 해시값 (파일 다운로드 전에는 빈 문자열)
            category: 문서 카테고리 (클라이언트 사이드 필터링용)
        """
        self.task_id = task_id
        self.user_id = str(user_id)
        self.hash_sha256 = hash_sha256
        self.category = category

    def _publish(
        self, stage: str, status: str = "in_progress", description: Optional[str] = None
    ) -> None:
        """SSE 메시지 발행 (hash 기반 + batch 채널 + 카테고리 채널)"""
        try:
            broker = get_redis_sse_broker()
            if broker is None:
                logger.error("Redis SSE Broker를 가져올 수 없음")
                return

            # description이 없으면 STAGE_DESCRIPTIONS에서 가져오기
            if not description:
                description = STAGE_DESCRIPTIONS.get(stage)

            # 1. hash 기반 채널에 발행 (hash가 있을 때만)
            if self.hash_sha256:
                broker.publish_event_by_hash(
                    user_id=self.user_id,
                    hash_sha256=self.hash_sha256,
                    stage=stage,
                    status=status,
                    description=description,
                )

            # 2. batch 채널에도 발행 (sse:user:{user_id}:tasks)
            broker.publish_user_task_event(
                user_id=self.user_id,
                task_id=self.task_id,
                hash_sha256=self.hash_sha256,
                stage=stage,
                status=status,
                description=description,
                category=self.category,
            )

            # 3. 카테고리 채널에도 발행 (category가 있을 때만)
            if self.category:
                broker.publish_category_event(
                    user_id=self.user_id,
                    task_id=self.task_id,
                    hash_sha256=self.hash_sha256,
                    category=self.category,
                    stage=stage,
                    status=status,
                    description=description,
                )
        except Exception as e:
            logger.error(f"❌ SSE (hash 기반) 발행 실패: {e}", exc_info=True)

    def notify(
        self, stage: str, status: str = "in_progress", description: Optional[str] = None
    ) -> None:
        """
        SSE 알림 발행.

        description이 없으면 자동으로 STAGE_DESCRIPTIONS에서 조회.
        """
        self._publish(stage, status, description)

    # ========================================
    # Task별 편의 메서드들 (각 task 실행 전에 호출)
    # ========================================

    def initializing(self):
        """컬렉션 초기화 중"""
        self.notify(PipelineStage.INITIALIZING, PipelineStatus.IN_PROGRESS)

    def downloading(self):
        """문서 다운로드 중"""
        self.notify(PipelineStage.DOWNLOADING, PipelineStatus.IN_PROGRESS)

    def extracting_metadata(self):
        """메타데이터 추출 중"""
        self.notify(PipelineStage.METADATA_EXTRACT, PipelineStatus.IN_PROGRESS)

    def checking_duplicate(self):
        """중복 확인 중"""
        self.notify(PipelineStage.DUPLICATE_CHECK, PipelineStatus.IN_PROGRESS)

    def saving_metadata(self):
        """메타데이터 저장 중"""
        self.notify(PipelineStage.METADATA_SAVE, PipelineStatus.IN_PROGRESS)

    def validating_status(self):
        """문서 상태 검증 중"""
        self.notify(PipelineStage.VALIDATE_STATUS, PipelineStatus.IN_PROGRESS)

    def parsing(self):
        """문서 파싱 중"""
        self.notify(PipelineStage.PARSING, PipelineStatus.IN_PROGRESS)

    def generating_summary(self):
        """요약 생성 중"""
        self.notify(PipelineStage.SUMMARY_GENERATION, PipelineStatus.IN_PROGRESS)

    def filtering_persona(self):
        """페르소나 필터링 중"""
        self.notify(PipelineStage.PERSONA_FILTER, PipelineStatus.IN_PROGRESS)

    def embedding(self):
        """임베딩 생성 중"""
        self.notify(PipelineStage.EMBEDDING, PipelineStatus.IN_PROGRESS)

    def transforming(self):
        """데이터 변환 중"""
        self.notify(PipelineStage.TRANSFORMING, PipelineStatus.IN_PROGRESS)

    def inserting(self):
        """벡터 데이터 저장 중"""
        self.notify(PipelineStage.INSERTING, PipelineStatus.IN_PROGRESS)

    def finalizing(self):
        """작업 완료 처리 중"""
        self.notify(PipelineStage.FINALIZING, PipelineStatus.IN_PROGRESS)

    def completed(self):
        """작업 완료"""
        self.notify(PipelineStage.FINALIZING, PipelineStatus.COMPLETED)

    def failed(self):
        """작업 실패"""
        self.notify(PipelineStage.FINALIZING, PipelineStatus.FAILED)

    def duplicate(self):
        """중복 문서 감지됨"""
        self.notify(PipelineStage.DUPLICATE, PipelineStatus.COMPLETED)

    def ocr_required(self):
        """OCR 필요"""
        self.notify(PipelineStage.OCR_REQUIRED, PipelineStatus.COMPLETED)


def create_notifier(params: dict) -> PipelineNotifier:
    """params dict로부터 PipelineNotifier 생성."""
    return PipelineNotifier(
        task_id=params["task_id"],
        user_id=params["user_id"],
        hash_sha256=params.get("hash_sha256", ""),
        category=params["category"],
    )


# ========================================
# Legacy Functions (Backward Compatibility)
# ========================================


def publish_pipeline_progress(
    task_id: str, user_id: str, stage: str, status: str = "in_progress"
) -> None:
    """
    파이프라인 진행 상태를 Redis를 통해 발행합니다.

    Args:
        task_id: 작업 ID
        user_id: 사용자 ID
        stage: 현재 단계 (PipelineStage enum 값)
        status: 상태 (in_progress, completed, failed)
    """
    try:
        broker = get_redis_sse_broker()
        if broker is None:
            logger.error("Redis SSE Broker를 가져올 수 없음")
            return

        broker.publish_event(
            task_id=task_id, user_id=user_id, stage=stage, status=status
        )
        logger.info(
            f"✅ 파이프라인 진행상황 발행 성공: task={task_id}, stage={stage}, status={status}"
        )
    except Exception as e:
        logger.error(f"❌ 파이프라인 진행상황 발행 실패: {e}", exc_info=True)


def publish_task_start(
    task_id: str,
    user_id: str,
    message: str,
    metadata: Optional[dict] = None,
) -> None:
    """작업 시작 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.INITIALIZING,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_metadata_update(task_id: str, user_id: str) -> None:
    """메타데이터 업데이트 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.METADATA_UPDATE,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_s3_upload(task_id: str, user_id: str) -> None:
    """S3 업로드 시작 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.UPLOADING,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_task_parsing(
    task_id: str,
    user_id: str,
    message: str,
    metadata: Optional[dict] = None,
) -> None:
    """문서 파싱 시작 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.PARSING,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_qa_generation(task_id: str, user_id: str) -> None:
    """Q&A 생성 시작 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.QA_GENERATION,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_task_embedding(
    task_id: str,
    user_id: str,
    message: str,
    metadata: Optional[dict] = None,
) -> None:
    """임베딩 생성 시작 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.EMBEDDING,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_data_transform(task_id: str, user_id: str) -> None:
    """데이터 변환 시작 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.TRANSFORMING,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_db_insert(task_id: str, user_id: str) -> None:
    """DB 삽입 시작 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.INSERTING,
        status=PipelineStatus.IN_PROGRESS,
    )


def publish_upload_completed(
    task_id: str,
    user_id: str,
    message: str,
    metadata: Optional[dict] = None,
) -> None:
    """작업 완료 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.FINALIZING,
        status=PipelineStatus.COMPLETED,
    )


def publish_upload_failed(
    task_id: str,
    user_id: str,
    message: str,
    metadata: Optional[dict] = None,
) -> None:
    """작업 실패 알림"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.FINALIZING,
        status=PipelineStatus.FAILED,
    )


def publish_duplicate_detected(
    task_id: str,
    user_id: str,
) -> None:
    """중복 문서 감지 알림 (SSE)"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.DUPLICATE,
        status=PipelineStatus.COMPLETED,
    )


def publish_ocr_required(
    task_id: str,
    user_id: str,
) -> None:
    """OCR 필요 문서 감지 알림 (SSE)"""
    publish_pipeline_progress(
        task_id=task_id,
        user_id=user_id,
        stage=PipelineStage.OCR_REQUIRED,
        status=PipelineStatus.COMPLETED,
    )


def publish_pipeline_status_updated(
    notification_channel: str,
    user_id: str,
    stage: str,
    status: str,
    message: Optional[str] = None,
) -> None:
    """
    파이프라인 상태 업데이트 알림 (hash 기반)

    Args:
        notification_channel: 알림 채널 (보통 hash_sha256)
        user_id: 사용자 ID
        stage: 파이프라인 단계
        status: 상태 (running, completed, failed)
        message: 커스텀 메시지 (선택적)
    """
    try:
        broker = get_redis_sse_broker()
        if broker is None:
            logger.error("Redis SSE Broker를 가져올 수 없음")
            return

        # message를 description으로 사용, 없으면 기본값
        description = message if message else STAGE_DESCRIPTIONS.get(stage)

        # hash 기반 채널에 발행
        broker.publish_event_by_hash(
            user_id=str(user_id),
            hash_sha256=notification_channel,
            stage=stage,
            status=status,
            description=description,
        )
        logger.debug(
            f"✅ 파이프라인 상태 업데이트 발행: channel={notification_channel}, "
            f"stage={stage}, status={status}"
        )
    except Exception as e:
        logger.error(f"❌ 파이프라인 상태 업데이트 발행 실패: {e}", exc_info=True)
