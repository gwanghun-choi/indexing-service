"""
Celery 워커에서 비동기 코루틴 실행을 위한 통합 유틸리티

모든 워커 태스크에서 일관된 이벤트 루프 관리를 제공합니다.
전역 이벤트 루프를 변경하지 않아 asyncpg 연결 정리 시 발생하는
"Event loop is closed" 오류를 방지합니다.
"""

import asyncio
import logging
from contextlib import contextmanager
from typing import Any, TypeVar

import nest_asyncio

logger = logging.getLogger(__name__)
T = TypeVar("T")


@contextmanager
def task_async_runner():
    """
    태스크별 독립적인 asyncio.Runner 인스턴스를 제공하는 컨텍스트 매니저

    Celery 워커에서 안전하게 새로운 이벤트 루프를 생성하고 관리합니다.
    중요: 전역 이벤트 루프를 변경하지 않아 asyncpg 연결 정리 시
    이벤트 루프 충돌을 방지합니다.

    사용 예:
        with task_async_runner() as runner:
            result = runner.run(some_async_function())
    """
    # nest_asyncio 적용 (중첩 이벤트 루프 허용)
    nest_asyncio.apply()

    # 새로운 독립적인 루프 생성 (전역 이벤트 루프에 영향 주지 않음)
    new_loop = asyncio.new_event_loop()

    # Runner는 독립적인 루프로 실행
    runner = asyncio.Runner(loop_factory=lambda: new_loop)
    try:
        yield runner
    finally:
        try:
            runner.close()
        except Exception:
            pass
        # 루프 완전 정리
        try:
            if not new_loop.is_closed():
                new_loop.close()
        except Exception:
            pass
        # 중요: 전역 이벤트 루프를 변경하지 않음 (asyncio.set_event_loop 호출 안함)


def run_async(coro) -> Any:
    """
    동기 컨텍스트(Celery Task)에서 비동기 코루틴을 실행하는 헬퍼 함수

    Args:
        coro: 실행할 코루틴

    Returns:
        코루틴 실행 결과
    """
    with task_async_runner() as runner:
        return runner.run(coro)
