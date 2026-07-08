"""
임베딩 스케줄 태스크

Celery Beat로 주기적으로 실행되는 스케줄 관리 태스크를 정의합니다.
"""

import logging
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from celery import Task
from croniter import croniter

from app.crud.milvus.document_crud import validate_documents
from app.crud.postgres import schedule_crud
from app.service.embedding_generation_pipeline import run_embedding_generation_pipeline
from app.service.redis_sse_broker import get_redis_sse_broker
from app.worker.celery import app
from app.worker.utils.async_runner import run_async
from app.worker.utils.redis_lock import acquire_lock, release_lock

logger = logging.getLogger(__name__)


class AsyncTask(Task):
    """비동기 작업을 지원하는 Celery Task 기본 클래스"""

    def __call__(self, *args, **kwargs):
        """
        비동기 함수를 동기적으로 실행
        공통 run_async 유틸리티 사용
        """
        return run_async(self.run(*args, **kwargs))

    async def run(self, *args, **kwargs):
        """
        실제 비동기 작업을 수행하는 메서드
        서브클래스에서 오버라이드해야 함
        """
        raise NotImplementedError("Subclasses must implement the run() method")


@app.task(
    bind=True,
    base=AsyncTask,
    name="check_and_run_schedules",
    time_limit=300,  # 5분
    soft_time_limit=270,  # 4분 30초
)
async def check_and_run_schedules(self):
    """
    활성 스케줄을 확인하고 실행 시간이 도래한 스케줄을 실행합니다.

    1분마다 실행되며, 실행할 스케줄이 있으면 자동으로 임베딩 파이프라인을 시작합니다.
    """
    try:
        logger.info("[Scheduler] 🕐 스케줄 체크 시작")

        now = datetime.now(ZoneInfo("Asia/Seoul"))

        # 1. 실행할 활성 스케줄 조회
        schedules = await schedule_crud.select_active_schedules_to_run(now)

        logger.info(f"[Scheduler] 📋 활성 스케줄 {len(schedules)}개 발견")

        if not schedules:
            logger.info("[Scheduler] ℹ️ 실행할 스케줄 없음")
            return {
                "status": "success",
                "message": "실행할 스케줄 없음",
                "executed_count": 0,
            }

        executed_count = 0
        failed_count = 0

        # 2. 각 스케줄 실행
        for schedule in schedules:
            try:
                # 분산 락 획득 (중복 실행 방지)
                lock_key = f"schedule:{schedule.id}:lock"

                acquired = await acquire_lock(lock_key, expire=300, timeout=0)

                if not acquired:
                    logger.warning(
                        f"[Scheduler] ⏭️ 스케줄 {schedule.id} 이미 실행 중 (락 획득 실패)"
                    )
                    continue

                try:
                    # 스케줄 실행
                    await _execute_schedule(schedule)
                    executed_count += 1

                finally:
                    # 락 해제
                    await release_lock(lock_key)

            except Exception as e:
                logger.error(f"[Scheduler] ❌ 스케줄 {schedule.id} 실행 실패: {e}")
                failed_count += 1

        logger.info(
            f"[Scheduler] ✅ 스케줄 체크 완료: "
            f"성공 {executed_count}개, 실패 {failed_count}개"
        )

        return {
            "status": "success",
            "message": f"{executed_count}개 스케줄 실행 완료",
            "executed_count": executed_count,
            "failed_count": failed_count,
        }

    except Exception as e:
        logger.error(f"[Scheduler] ❌ 스케줄 체크 중 오류: {e}")
        raise


async def _execute_schedule(schedule) -> None:
    """
    스케줄을 실행하여 임베딩 파이프라인 시작

    Args:
        schedule: EmbeddingSchedule 객체
    """
    schedule_id = schedule.id
    logger.info(f"[Scheduler] 🚀 스케줄 {schedule_id} 실행 시작: {schedule.name}")

    # 1. 실행 이력 생성
    history_data = {
        "schedule_id": schedule_id,
        "execution_time": datetime.now(ZoneInfo("Asia/Seoul")),
        "status": "running",
        "started_at": datetime.now(ZoneInfo("Asia/Seoul")),
    }

    history = await schedule_crud.create_execution_history(history_data)
    execution_id = history.id

    try:
        # 2. 문서 해시 리스트 가져오기
        document_hashes = schedule.document_hashes

        if not document_hashes or len(document_hashes) == 0:
            logger.warning(f"[Scheduler] ⚠️ 스케줄 {schedule_id}: 처리할 문서 없음")

            # 실행 이력 업데이트 (성공, 문서 0개)
            await schedule_crud.update_execution_history(
                execution_id,
                {
                    "status": "success",
                    "documents_processed": 0,
                    "completed_at": datetime.now(ZoneInfo("Asia/Seoul")),
                    "duration_seconds": 0,
                },
            )

            # 스케줄 통계 업데이트
            await schedule_crud.update_schedule_execution_stats(
                schedule_id, datetime.now(ZoneInfo("Asia/Seoul")), success=True
            )

            # 다음 실행 시간 업데이트 (반복 스케줄인 경우)
            await _update_next_execution_time(schedule)

            return

        logger.info(
            f"[Scheduler] 📄 스케줄 {schedule_id}: {len(document_hashes)}개 문서 발견"
        )

        # 3. 문서 상태 검증 (status='registered'인 문서만 처리)
        valid_docs, failed_docs = await validate_documents(
            group_id=schedule.group_id,
            hash_sha256_list=document_hashes,
            user_id=schedule.user_id,
            role_ids=schedule.role_ids,
        )

        if not valid_docs:
            logger.warning(
                f"[Scheduler] ⚠️ 스케줄 {schedule_id}: 실행 가능한 문서가 없음 "
                f"(전체: {len(document_hashes)}, 실패: {len(failed_docs)})"
            )

            # 실행 이력 업데이트 (성공, 문서 0개)
            await schedule_crud.update_execution_history(
                execution_id,
                {
                    "status": "success",
                    "documents_processed": 0,
                    "completed_at": datetime.now(ZoneInfo("Asia/Seoul")),
                    "duration_seconds": 0,
                },
            )

            # 스케줄 통계 업데이트
            await schedule_crud.update_schedule_execution_stats(
                schedule_id, datetime.now(ZoneInfo("Asia/Seoul")), success=True
            )

            # 다음 실행 시간 업데이트 (반복 스케줄인 경우)
            await _update_next_execution_time(schedule)

            return

        logger.info(
            f"[Scheduler] ✅ 문서 검증 완료: "
            f"유효 {len(valid_docs)}개, 실패 {len(failed_docs)}개"
        )

        # 4. 임베딩 설정
        embedding_config = schedule.embedding_config or {}

        # 4-1. 사용자 알림 발송 (스케줄 실행 시작)
        try:
            broker = get_redis_sse_broker()
            if broker:
                documents = [{"hash_sha256": doc["hash_sha256"]} for doc in valid_docs]
                broker.publish_user_notification(
                    user_id=str(schedule.user_id),
                    notification_type="schedule_started",
                    data={
                        "schedule_id": schedule.id,
                        "documents": documents,
                    },
                )
                logger.info(
                    f"[Scheduler] 🔔 사용자 알림 발송 완료: schedule_id={schedule_id}, "
                    f"user_id={schedule.user_id}, documents={len(documents)}"
                )
        except Exception as e:
            logger.error(f"[Scheduler] ⚠️ 사용자 알림 발송 실패: {e}")

        # 5. 각 문서에 대해 임베딩 파이프라인 실행 (유효한 문서만)
        task_ids = []
        success_count = 0
        failed_count = 0

        for doc in valid_docs:
            doc_hash = doc["hash_sha256"]
            try:
                task_id = str(uuid.uuid4())

                # 임베딩 파이프라인 페이로드 구성
                payload = {
                    "task_id": task_id,
                    "user_id": schedule.user_id,
                    "group_id": schedule.group_id,
                    "total_role": schedule.role_ids,
                    "hash_sha256": doc_hash,
                    "embedding_model": "openai",
                    "model_name": "text-embedding-ada-002",
                    "chunk_size": embedding_config["chunk_size"],
                    "chunk_overlap": embedding_config["chunk_overlap"],
                    "enable_pii_anonymization": embedding_config["enable_pii_anonymization"],
                    "pii_strategy": embedding_config["pii_strategy"],
                    "pii_types": embedding_config["pii_types"],
                    "persona_id": embedding_config["persona_id"],
                    "filter_score": embedding_config["filter_score"],
                    "document_parser": embedding_config["document_parser"],
                }

                # Redis 초기 상태 저장 (타이밍 이슈 방지)
                try:
                    broker = get_redis_sse_broker()
                    if broker:
                        broker.publish_event_by_hash(
                            user_id=str(schedule.user_id),
                            hash_sha256=doc_hash,
                            stage="initializing",
                            status="in_progress",
                            description="스케줄 실행으로 작업 시작 준비 중",
                        )
                except Exception as e:
                    logger.warning(
                        f"[Scheduler] ⚠️ Redis 초기 상태 저장 실패 (무시): hash={doc_hash[:16]}..., error={e}"
                    )

                # Celery 태스크 실행
                run_embedding_generation_pipeline.apply_async(
                    args=[payload], task_id=task_id
                )

                task_ids.append(task_id)
                success_count += 1

                logger.debug(
                    f"[Scheduler] ✅ 태스크 등록: task_id={task_id}, hash={doc_hash[:16]}..."
                )

            except Exception as e:
                logger.error(
                    f"[Scheduler] ❌ 태스크 등록 실패: hash={doc_hash[:16]}..., error={e}"
                )
                failed_count += 1

        # 6. 실행 이력 업데이트
        duration = (datetime.now(ZoneInfo("Asia/Seoul")) - history.started_at).total_seconds()

        await schedule_crud.update_execution_history(
            execution_id,
            {
                "status": "success" if failed_count == 0 else "failed",
                "documents_processed": len(valid_docs),
                "documents_success": success_count,
                "documents_failed": failed_count,
                "task_ids": task_ids,
                "completed_at": datetime.now(ZoneInfo("Asia/Seoul")),
                "duration_seconds": int(duration),
            },
        )

        # 7. 스케줄 통계 업데이트
        await schedule_crud.update_schedule_execution_stats(
            schedule_id, datetime.now(ZoneInfo("Asia/Seoul")), success=(failed_count == 0)
        )

        # 8. 다음 실행 시간 업데이트 (반복 스케줄인 경우)
        await _update_next_execution_time(schedule)

        logger.info(
            f"[Scheduler] ✅ 스케줄 {schedule_id}: "
            f"{len(task_ids)}개 태스크 등록 완료 "
            f"(성공: {success_count}, 실패: {failed_count})"
        )

    except Exception as e:
        logger.error(f"[Scheduler] ❌ 스케줄 {schedule_id} 실행 실패: {e}")

        # 실행 이력 업데이트 (실패)
        duration = (datetime.now(ZoneInfo("Asia/Seoul")) - history.started_at).total_seconds()

        await schedule_crud.update_execution_history(
            execution_id,
            {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(ZoneInfo("Asia/Seoul")),
                "duration_seconds": int(duration),
            },
        )

        # 스케줄 통계 업데이트
        await schedule_crud.update_schedule_execution_stats(
            schedule_id, datetime.now(ZoneInfo("Asia/Seoul")), success=False
        )

        raise


async def _update_next_execution_time(schedule) -> None:
    """
    스케줄의 다음 실행 시간 업데이트

    Args:
        schedule: EmbeddingSchedule 객체
    """
    try:
        # 반복 스케줄이 아니면 비활성화
        if not schedule.cron_expression:
            logger.info(
                f"[Scheduler] ℹ️ 스케줄 {schedule.id}: " f"1회성 스케줄이므로 비활성화"
            )

            await schedule_crud.update_schedule(
                schedule.id,
                schedule.user_id,
                schedule.group_id,
                {"is_active": False},
            )

            return

        # Cron 표현식으로 다음 실행 시간 계산
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        cron = croniter(schedule.cron_expression, now)
        next_time = cron.get_next(datetime)

        logger.info(
            f"[Scheduler] 📅 스케줄 {schedule.id}: " f"다음 실행 시간 = {next_time}"
        )

        # 다음 실행 시간 업데이트
        await schedule_crud.update_schedule(
            schedule.id,
            schedule.user_id,
            schedule.group_id,
            {"scheduled_at": next_time},
        )

    except Exception as e:
        logger.error(
            f"[Scheduler] ❌ 스케줄 {schedule.id} " f"다음 실행 시간 업데이트 실패: {e}"
        )


@app.task(
    bind=True,
    name="cleanup_old_execution_history",
    time_limit=600,  # 10분
)
def cleanup_old_execution_history(self):
    """
    90일 이상 지난 실행 이력 정리

    매일 새벽 3시에 실행됩니다.
    """
    try:
        logger.info("[Scheduler] 🗑️ 오래된 실행 이력 정리 시작")

        cutoff_date = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=90)

        deleted_count = run_async(
            schedule_crud.delete_old_execution_history(cutoff_date)
        )

        logger.info(f"[Scheduler] ✅ 오래된 실행 이력 {deleted_count}개 정리 완료")

        return {
            "status": "success",
            "message": f"{deleted_count}개 이력 삭제 완료",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"[Scheduler] ❌ 실행 이력 정리 실패: {e}")
        raise
