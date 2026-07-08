import asyncio
import logging
import os

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from app.config.database.session import WorkerEngineManager
from app.config.settings import settings
from app.service.redis_sse_broker import get_redis_sse_broker, reset_broker_cache
from app.worker.utils.beat_config import get_beat_schedule

logger = logging.getLogger(__name__)


app = Celery(
    "Celery Worker",
    broker=settings.CELERY_BROKER_URL,
    include=[
        "app.worker.document_task",
        "app.worker.embedding_task",
        "app.worker.schedule_tasks",
        "app.worker.ragas_eval_task",
        "app.service.integrated_pipeline",
        "app.service.document_registration_pipeline",
        "app.service.embedding_generation_pipeline",
    ],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    enable_utc=True,
    task_ignore_result=True,
    worker_prefetch_multiplier=2,  # 한 번에 2개까지 미리 가져와 병렬 처리
    worker_max_tasks_per_child=10,  # 10개 태스크 후 워커 재시작 (메모리 집약적 태스크)
    worker_max_memory_per_child=768000,  # 750MB 초과 시 워커 재시작
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Celery Beat 스케줄 설정 로드
try:
    app.conf.beat_schedule = get_beat_schedule()
    logger.info("✅ Celery Beat 스케줄 설정 로드 완료")
except Exception as e:
    logger.warning(f"⚠️ Celery Beat 스케줄 설정 로드 실패: {e}")


@worker_process_init.connect
def setup_worker_process(**kwargs):
    """
    각 워커 프로세스 시작 시 초기화.
    - 새 이벤트 루프 설정
    - Redis 연결 재생성 (fork-safety 보장)
    """
    current_pid = os.getpid()
    logger.info(f"[WORKER-INIT] 워커 프로세스 초기화 시작: PID={current_pid}")

    # 1. 기존 이벤트 루프 정리 및 새 루프 생성
    try:
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            loop.close()
    except RuntimeError:
        pass

    asyncio.set_event_loop(asyncio.new_event_loop())
    logger.info(f"[WORKER-INIT] ✅ 새 이벤트 루프 생성: PID={current_pid}")

    # 2. Redis SSE Broker 연결 재설정 (fork-safety 보장)
    try:
        # 현재 프로세스용 새 브로커 인스턴스 생성
        broker = get_redis_sse_broker()
        if broker and broker.redis_client:
            # 연결 테스트
            broker.redis_client.ping()
            logger.info(
                f"[WORKER-INIT] ✅ Redis SSE Broker 초기화 완료: PID={current_pid}"
            )
        else:
            logger.error(f"[WORKER-INIT] ❌ Redis 클라이언트 없음: PID={current_pid}")

    except Exception as e:
        logger.error(
            f"[WORKER-INIT] ❌ Redis SSE Broker 초기화 실패: PID={current_pid}, error={e}"
        )


@worker_process_shutdown.connect
def cleanup_worker_process(**kwargs):
    """
    워커 종료 시 정리.
    - AsyncEngine 정리 (WorkerEngineManager)
    - 이벤트 루프 및 연결 정리
    - Redis 연결 종료
    """
    current_pid = os.getpid()
    logger.info(f"[WORKER-SHUTDOWN] 워커 프로세스 종료 시작: PID={current_pid}")

    # 1. AsyncEngine 정리 (비동기 작업)
    try:
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            loop.run_until_complete(WorkerEngineManager.dispose())
        else:
            # 루프가 닫혀있으면 새 루프로 정리
            new_loop = asyncio.new_event_loop()
            try:
                new_loop.run_until_complete(WorkerEngineManager.dispose())
            finally:
                new_loop.close()

        logger.info(f"[WORKER-SHUTDOWN] ✅ AsyncEngine 정리 완료: PID={current_pid}")
    except Exception as e:
        logger.error(f"[WORKER-SHUTDOWN] ❌ AsyncEngine 정리 실패: {e}")

    # 2. Redis 브로커 연결 정리
    try:
        # 현재 프로세스의 브로커 가져오기 (있다면)
        broker = get_redis_sse_broker()
        if broker and broker.redis_client:
            broker.redis_client.close()
            logger.info(f"[WORKER-SHUTDOWN] ✅ Redis 연결 종료: PID={current_pid}")

        # 캐시 정리
        reset_broker_cache()

    except Exception as e:
        logger.error(f"[WORKER-SHUTDOWN] ❌ Redis 연결 종료 실패: {e}")

    # 3. 이벤트 루프 정리
    try:
        loop = asyncio.get_event_loop()
        if loop and not loop.is_closed():
            # 남은 태스크 정리
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.close()
        logger.info(f"[WORKER-SHUTDOWN] ✅ 이벤트 루프 정리 완료: PID={current_pid}")
    except RuntimeError:
        pass
