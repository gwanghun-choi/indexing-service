"""
Redis 분산 락 유틸리티

여러 워커 프로세스 간 동시 실행을 방지하기 위한 분산 락을 제공합니다.
"""

import asyncio
import logging
import time
from typing import Optional

from app.config.infrastructure.cache.redis_cache import RedisCache, RedisConfig

logger = logging.getLogger(__name__)


class RedisLock:
    """Redis 기반 분산 락"""

    def __init__(self, redis_cache: Optional[RedisCache] = None):
        """
        Redis Lock 초기화

        Args:
            redis_cache: Redis 캐시 인스턴스 (없으면 새로 생성)
        """
        if redis_cache is None:
            redis_config = RedisConfig()
            self.redis_cache = RedisCache(redis_config)
        else:
            self.redis_cache = redis_cache

        self._redis = None

    async def connect(self):
        """Redis 연결"""
        if self._redis is None:
            await self.redis_cache.connect()
            self._redis = self.redis_cache.redis
            logger.info("✅ Redis Lock connected")

    async def acquire(
        self,
        lock_key: str,
        expire: int = 300,
        timeout: int = 0,
    ) -> bool:
        """
        락 획득

        Args:
            lock_key: 락 키
            expire: 락 만료 시간 (초, 기본: 300초 = 5분)
            timeout: 락 획득 대기 시간 (초, 기본: 0 = 대기 안함)

        Returns:
            bool: 락 획득 성공 여부
        """
        if self._redis is None:
            await self.connect()

        try:
            start_time = time.time()

            while True:
                # SET NX (Not eXists) - 키가 없을 때만 설정
                acquired = await self._redis.set(
                    lock_key,
                    "locked",
                    ex=expire,
                    nx=True,
                )

                if acquired:
                    logger.debug(f"✅ 락 획득 성공: {lock_key}")
                    return True

                # 타임아웃 확인
                if timeout == 0:
                    logger.debug(f"⚠️ 락 획득 실패 (이미 사용 중): {lock_key}")
                    return False

                # 타임아웃 초과
                if time.time() - start_time >= timeout:
                    logger.warning(
                        f"⚠️ 락 획득 타임아웃: {lock_key} (대기 시간: {timeout}초)"
                    )
                    return False

                # 재시도 전 대기 (100ms)
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"❌ 락 획득 중 오류: {lock_key}, {e}")
            return False

    async def release(self, lock_key: str) -> bool:
        """
        락 해제

        Args:
            lock_key: 락 키

        Returns:
            bool: 락 해제 성공 여부
        """
        if self._redis is None:
            await self.connect()

        try:
            deleted = await self._redis.delete(lock_key)

            if deleted > 0:
                logger.debug(f"✅ 락 해제 성공: {lock_key}")
                return True
            else:
                logger.debug(f"⚠️ 락 해제 실패 (이미 해제됨): {lock_key}")
                return False

        except Exception as e:
            logger.error(f"❌ 락 해제 중 오류: {lock_key}, {e}")
            return False

    async def is_locked(self, lock_key: str) -> bool:
        """
        락 상태 확인

        Args:
            lock_key: 락 키

        Returns:
            bool: 락 사용 중 여부
        """
        if self._redis is None:
            await self.connect()

        try:
            exists = await self._redis.exists(lock_key)
            return exists > 0

        except Exception as e:
            logger.error(f"❌ 락 상태 확인 중 오류: {lock_key}, {e}")
            return False

    async def extend(self, lock_key: str, expire: int = 300) -> bool:
        """
        락 만료 시간 연장

        Args:
            lock_key: 락 키
            expire: 연장할 만료 시간 (초)

        Returns:
            bool: 연장 성공 여부
        """
        if self._redis is None:
            await self.connect()

        try:
            # 락이 존재하는 경우에만 연장
            if await self.is_locked(lock_key):
                await self._redis.expire(lock_key, expire)
                logger.debug(f"✅ 락 연장 성공: {lock_key}, expire={expire}초")
                return True
            else:
                logger.warning(f"⚠️ 락 연장 실패 (존재하지 않음): {lock_key}")
                return False

        except Exception as e:
            logger.error(f"❌ 락 연장 중 오류: {lock_key}, {e}")
            return False

    async def close(self):
        """Redis 연결 종료"""
        if self.redis_cache:
            await self.redis_cache.close()
            logger.info("✅ Redis Lock closed")


# 싱글톤 인스턴스 (전역)
_redis_lock_instance: Optional[RedisLock] = None


async def get_redis_lock() -> RedisLock:
    """
    Redis Lock 싱글톤 인스턴스 반환

    Returns:
        RedisLock: Redis Lock 인스턴스
    """
    global _redis_lock_instance

    if _redis_lock_instance is None:
        _redis_lock_instance = RedisLock()
        await _redis_lock_instance.connect()

    return _redis_lock_instance


# 간편 함수
async def acquire_lock(lock_key: str, expire: int = 300, timeout: int = 0) -> bool:
    """
    락 획득 (간편 함수)

    Args:
        lock_key: 락 키
        expire: 락 만료 시간 (초)
        timeout: 락 획득 대기 시간 (초)

    Returns:
        bool: 락 획득 성공 여부
    """
    lock = await get_redis_lock()
    return await lock.acquire(lock_key, expire, timeout)


async def release_lock(lock_key: str) -> bool:
    """
    락 해제 (간편 함수)

    Args:
        lock_key: 락 키

    Returns:
        bool: 락 해제 성공 여부
    """
    lock = await get_redis_lock()
    return await lock.release(lock_key)

