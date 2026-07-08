from typing import Optional, Any, List
from redis.asyncio import Redis
import json
import time
from pydantic import BaseModel, field_validator, ConfigDict
from datetime import datetime
from urllib.parse import urlparse
from app.config.settings import settings

import logging

logger = logging.getLogger(__name__)


class RedisError(Exception):
    """기본 Redis 에러 클래스"""

    pass


class RedisConnectionError(RedisError):
    """연결 관련 에러"""

    pass


class RedisCacheError(RedisError):
    """캐시 작업 관련 에러"""

    pass


class LockError(RedisError):
    """분산락 오류"""

    pass


class RedisConfig(BaseModel):
    # REDIS_URL 파싱하여 호스트와 포트 추출
    _parsed_url = urlparse(settings.REDIS_URL)
    host: str = _parsed_url.hostname
    port: int = _parsed_url.port
    db: int = int(_parsed_url.path.strip('/')) if _parsed_url.path != '/' else 0
    prefix: str = "cache:"
    default_ttl: int = 3600
    pool_size: int = 5
    retry_attempts: int = 3
    retry_delay: float = 0.1
    model_config = ConfigDict(
        env_prefix="REDIS_", extra="allow", validate_assignment=True
    )

    @field_validator("pool_size")
    def validate_pool_size(cls, v):
        if v < 1:
            raise ValueError("pool_size must be positive")
        return v

    @field_validator("retry_attempts")
    def validate_retry_attempts(cls, v):
        if v < 0:
            raise ValueError("retry_attempts must be non-negative")
        return v


class CachePolicy:
    """캐시 정책"""

    def __init__(self, ttl: int = 3600, max_size: int = 1024 * 1024):
        self.ttl = ttl  # 캐시 유효 시간 (초)
        self.max_size = max_size  # 최대 캐시 크기 (바이트)

    async def should_cache(self, value: Any) -> bool:
        """캐싱 여부 결정 로직"""
        try:
            value_size = len(json.dumps(value, cls=JSONEncoder))
            return value_size <= self.max_size
        except Exception as e:
            logger.error(f"Error in should_cache: {str(e)}")
            return False


class ExtendedCacheMetrics:
    """확장된 캐시 메트릭스"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.set_operations = 0
        self.delete_operations = 0
        self._response_times: List[float] = []
        self.last_reset = datetime.now()

    @property
    def average_response_time(self) -> float:
        if not self._response_times:
            return 0.0
        return sum(self._response_times) / len(self._response_times)

    def add_response_time(self, time: float):
        self._response_times.append(time)
        if len(self._response_times) > 1000:  # 최근 1000개만 유지
            self._response_times.pop(0)

    def reset(self):
        """메트릭스 초기화"""
        self.__init__()


class JSONEncoder(json.JSONEncoder):
    """Custom JSON Encoder to handle datetime serialization."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()  # Convert datetime to ISO 8601 string
        return super().default(obj)


class RedisCache:
    def __init__(self, config: RedisConfig, policy: Optional[CachePolicy] = None):
        self.config = config
        self.policy = policy or CachePolicy(
            ttl=config.default_ttl, max_size=1024 * 1024
        )  # 기본 정책: 1MB
        self.redis: Optional[Redis] = None
        self.metrics = ExtendedCacheMetrics()

    async def connect(self):
        """Redis 연결 설정 with 커넥션 풀"""
        try:
            self.redis = Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                max_connections=self.config.pool_size,
                decode_responses=True,
            )
            await self.redis.ping()  # 연결 테스트
            logging.info("✅ Connected to Redis successfully")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {str(e)}")
            raise RedisConnectionError(f"Redis connection failed: {str(e)}")

    async def get(self, key: str, default: Any = None) -> Optional[Any]:
        """캐시 데이터 조회 with 메트릭스"""
        full_key = f"{self.config.prefix}{key}"
        start_time = time.time()
        try:
            if not self.redis:
                return default

            value = await self.redis.get(full_key)
            if value:
                self.metrics.hits += 1
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in cache for key: {key}")
                    await self.delete(key)
                    return default
            self.metrics.misses += 1
            return default
        finally:
            self.metrics.add_response_time(time.time() - start_time)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """캐시 데이터 저장 with 정책 및 재시도 로직"""
        if not await self.policy.should_cache(value):
            return  # 정책에 따라 캐싱하지 않음

        full_key = f"{self.config.prefix}{key}"
        start_time = time.time()

        for attempt in range(self.config.retry_attempts):
            try:
                if not self.redis:
                    return

                # Custom JSONEncoder 적용
                await self.redis.set(
                    full_key,
                    json.dumps(value, cls=JSONEncoder),
                    ex=ttl or self.config.default_ttl,
                )
                return
            except Exception as e:
                if attempt == self.config.retry_attempts - 1:
                    logger.error(
                        f"Cache set failed after {attempt + 1} attempts: {key}"
                    )
                    raise RedisCacheError(f"Cache set failed: {str(e)}")
                continue
            finally:
                self.metrics.add_response_time(time.time() - start_time)

    async def delete(self, key: str):
        """캐시 데이터 삭제"""
        full_key = f"{self.config.prefix}{key}"
        try:
            if not self.redis:
                return

            await self.redis.delete(full_key)
            self.metrics.delete_operations += 1
            logger.debug(f"Cache delete: {key}")
        except Exception as e:
            logger.error(f"Cache delete failed: {key}")
            raise RedisCacheError(f"Cache delete failed: {str(e)}")

    async def cleanup_expired_cache(self):
        """만료된 캐시 정리"""
        try:
            if not self.redis:
                return

            async for key in self.redis.scan_iter(f"{self.config.prefix}*"):
                ttl = await self.redis.ttl(key)
                if ttl < 0:
                    await self.redis.delete(key)
                    logger.debug(f"Expired cache cleaned: {key}")
        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}")
            raise RedisCacheError(f"Cache cleanup failed: {str(e)}")

    async def get_metrics(self) -> dict:
        """캐시 메트릭스 조회"""
        total = self.metrics.hits + self.metrics.misses
        hit_rate = (self.metrics.hits / total * 100) if total > 0 else 0
        return {
            "hits": self.metrics.hits,
            "misses": self.metrics.misses,
            "errors": self.metrics.errors,
            "set_operations": self.metrics.set_operations,
            "delete_operations": self.metrics.delete_operations,
            "hit_rate": f"{hit_rate:.2f}%",
            "average_response_time": f"{self.metrics.average_response_time:.3f}s",
            "metrics_since": self.metrics.last_reset.isoformat(),
        }



