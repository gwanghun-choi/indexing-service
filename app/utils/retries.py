import functools
import asyncio
import logging
import time
import random
from typing import Callable, TypeVar, Optional, Dict

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int, Dict], None]] = None,
):
    """
    🔄 지수 백오프 전략으로 함수 재시도 데코레이터

    함수 호출 실패 시 지수적으로 증가하는 대기 시간 후 재시도합니다.
    비동기 및 동기 함수 모두 지원하며, 재시도 이벤트를 콜백 함수로 알릴 수 있습니다.

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 초기 대기 시간(초)
        max_delay: 최대 대기 시간(초)
        backoff_factor: 백오프 증가 계수
        retryable_exceptions: 재시도할 예외 클래스 튜플
        on_retry: 재시도 이벤트 콜백 함수 (예외, 재시도 횟수, 컨텍스트를 인자로 받음)

    Returns:
        데코레이터 함수

    예시:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def fetch_data():
            # 실패할 수 있는 비동기 작업 수행
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            context = kwargs.get("context", {})
            attempt = 0

            while True:
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(f"최대 재시도 횟수({max_retries}) 초과: {e} ❌")
                        raise

                    delay = min(
                        base_delay * (backoff_factor ** (attempt - 1)), max_delay
                    )
                    jitter = random.uniform(0, 0.1 * delay)
                    total_delay = delay + jitter

                    logger.warning(
                        f"재시도 {attempt}/{max_retries} - {func.__name__} 호출 실패: {e}. "
                        f"{total_delay:.2f}초 후 재시도. ⚠️"
                    )

                    if on_retry:
                        on_retry(e, attempt, context)

                    await asyncio.sleep(total_delay)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            context = kwargs.get("context", {})
            attempt = 0

            while True:
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(f"최대 재시도 횟수({max_retries}) 초과: {e} ❌")
                        raise

                    delay = min(
                        base_delay * (backoff_factor ** (attempt - 1)), max_delay
                    )
                    jitter = random.uniform(0, 0.1 * delay)
                    total_delay = delay + jitter

                    logger.warning(
                        f"재시도 {attempt}/{max_retries} - {func.__name__} 호출 실패: {e}. "
                        f"{total_delay:.2f}초 후 재시도. ⚠️"
                    )

                    if on_retry:
                        on_retry(e, attempt, context)

                    time.sleep(total_delay)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
