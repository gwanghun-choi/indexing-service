import asyncio
import logging
from contextlib import contextmanager
from typing import Any, Dict

from app.utils.initialization import connect_to_milvus, initialize_milvus
from app.utils.notification import publish_task_start
from app.worker.celery import app

logger = logging.getLogger(__name__)


@contextmanager
def task_async_runner():
    """
    태스크별 독립적인 asyncio.Runner 인스턴스를 제공하는 컨텍스트 매니저

    각 태스크마다 새로운 Runner를 생성하고 사용 후 정리합니다.

    사용 예:
        with task_async_runner() as runner:
            result = runner.run(some_async_function())
    """
    runner = asyncio.Runner()
    try:
        yield runner
    finally:
        runner.close()


@app.task(time_limit=120, soft_time_limit=110, max_retries=3, default_retry_delay=10)
def initialize_collection_task(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    새로운 Milvus 컬렉션 생성

    그룹 ID를 기반으로 메타데이터 및 벡터 저장용 컬렉션을 생성합니다.

    타임아웃:
    - soft_time_limit: 1분 50초 - 정상 종료 시도
    - time_limit: 2분 - 강제 종료

    Args:
        params: RAG 파이프라인 요청 파라미터

    Returns:
        Dict[str, Any]: 업데이트된 파라미터 (컬렉션 헤더 정보 추가)

    Raises:
        Exception: 컬렉션 초기화 중 오류 발생 시
    """
    try:
        logger.info("[pipeline] ✅ 컬렉션 초기화를 시작합니다...")

        # 작업 시작 알림
        publish_task_start(
            task_id=params["task_id"],
            user_id=str(params["user_id"]),
            message=f"임베딩 작업 시작: {params['title']}",
            metadata={"title": params["title"]},
        )

        # Milvus 연결 - 비동기 함수를 동기적으로 호출
        with task_async_runner() as runner:
            runner.run(connect_to_milvus())

        # 컬렉션 네이밍 규칙: TB_{group_id}_{meta|vector}
        collection_header = f"TB_{params['group_id']}"
        params["collection_header"] = collection_header
        logger.debug(f"[pipeline] ✅ 컬렉션 헤더 생성: {collection_header}")

        # 메타데이터 컬렉션 생성 - 비동기 함수를 동기적으로 호출
        with task_async_runner() as runner:
            runner.run(initialize_milvus(f"{collection_header}_meta", "meta"))
        logger.debug(f"[pipeline] ✅ 메타데이터 컬렉션 생성 완료: {collection_header}_meta")

        # 벡터 컬렉션 생성 - 비동기 함수를 동기적으로 호출
        with task_async_runner() as runner:
            runner.run(initialize_milvus(f"{collection_header}_vector", "vector"))
        logger.debug(f"[pipeline] ✅ 벡터 컬렉션 생성 완료: {collection_header}_vector")

        logger.info(f"[pipeline] ✅ 컬렉션 초기화 완료: {collection_header}")
        return params
    except Exception as e:
        logger.error(f"[pipeline] ❌ 컬렉션 초기화 중 오류 발생: {e}")
        raise e
