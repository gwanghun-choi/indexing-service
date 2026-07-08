import asyncio
import logging
import os
import time
from functools import lru_cache
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import orjson
import redis

from app.config.settings import settings

logger = logging.getLogger(__name__)


class RedisSSEBroker:
    """
    Redis를 통한 프로세스 간 SSE 이벤트 브로커
    Celery 워커와 FastAPI 프로세스 간 통신을 담당
    """

    def __init__(self):
        """Redis 클라이언트 초기화"""
        self.redis_client = None
        self._connect()

    def _connect(self):
        """Redis 연결 설정"""
        try:
            redis_url = settings.REDIS_URL
            parsed_url = urlparse(redis_url)

            # ConnectionPool을 사용하여 동시 연결 처리 개선
            pool = redis.ConnectionPool(
                host=parsed_url.hostname,
                port=parsed_url.port,
                password=parsed_url.password,
                db=0,
                decode_responses=True,
                max_connections=50,
                socket_keepalive=True,
            )
            self.redis_client = redis.Redis(connection_pool=pool)

            # 연결 테스트
            self.redis_client.ping()
            logger.info("✅ Redis SSE 브로커 초기화 성공")

        except Exception as e:
            logger.error(f"❌ Redis SSE 브로커 초기화 실패: {e}")
            self.redis_client = None

    def publish_event(
        self,
        task_id: str,
        user_id: str,
        stage: str,
        status: str,
        description: Optional[str] = None,
    ) -> None:
        """
        Redis에 SSE 이벤트 발행 (동기 함수 - Celery 워커에서 사용)

        Args:
            task_id: 작업 ID
            user_id: 사용자 ID (owner_key 저장용, event_data에는 미포함)
            stage: 파이프라인 단계
            status: 상태 (in_progress, completed, failed)
            description: 단계 설명 (프로그레스 바 표시용, optional)
        """
        try:
            # Redis 연결 확인 및 재연결
            if not self.redis_client:
                logger.warning("Redis 연결이 없음, 재연결 시도")
                self._connect()
                if not self.redis_client:
                    logger.error("Redis 재연결 실패")
                    return

            # 이벤트 데이터 구성 (task_id만 포함, user_id는 제외)
            event_data = {
                "task_id": task_id,
                "stage": stage,
                "status": status,
            }

            # description이 있으면 추가
            if description:
                event_data["description"] = description

            # Redis 채널에 발행 (각 task_id마다 고유한 채널)
            channel = f"sse:task:{task_id}"
            message = orjson.dumps(event_data).decode()
            state_key = f"task:state:{task_id}"
            owner_key = f"task:owner:{task_id}"

            # Redis Pipeline으로 배치 처리 (1회 네트워크 왕복)
            pipe = self.redis_client.pipeline()
            pipe.publish(channel, message)
            pipe.set(state_key, message, ex=14400)
            pipe.set(owner_key, user_id, ex=14400)

            # 작업이 진행중인 경우에만 heartbeat 갱신
            if status not in ("completed", "failed"):
                heartbeat_key = f"task:heartbeat:{task_id}"
                pipe.set(heartbeat_key, int(time.time()), ex=30)

            results = pipe.execute()
            subscriber_count = results[0]

            logger.info(
                f"📡 Redis 이벤트 발행 성공: task_id={task_id!r}, channel={channel}, "
                f"stage={stage}, status={status}, subscribers={subscriber_count}"
            )

        except Exception as e:
            logger.error(
                f"❌ Redis 이벤트 발행 실패: task_id={task_id}, error={e}",
                exc_info=True,
            )

    def publish_event_by_hash(
        self,
        user_id: str,
        hash_sha256: str,
        stage: str,
        status: str,
        description: Optional[str] = None,
    ) -> None:
        """
        Redis에 SSE 이벤트 발행 (hash 기반 - API 요청 파이프라인용)

        Args:
            user_id: 사용자 ID
            hash_sha256: 문서 해시값
            stage: 파이프라인 단계
            status: 상태 (in_progress, completed, failed)
            description: 단계 설명 (프로그레스 바 표시용, optional)
        """
        try:
            # Redis 연결 확인 및 재연결
            if not self.redis_client:
                logger.warning("Redis 연결이 없음, 재연결 시도")
                self._connect()
                if not self.redis_client:
                    logger.error("Redis 재연결 실패")
                    return

            # 이벤트 데이터 구성
            event_data = {
                "user_id": user_id,
                "hash_sha256": hash_sha256,
                "stage": stage,
                "status": status,
            }

            # description이 있으면 추가
            if description:
                event_data["description"] = description

            # Redis 채널에 발행 (user_id + hash 조합으로 고유 채널)
            channel = f"sse:doc:{user_id}:{hash_sha256}"
            message = orjson.dumps(event_data).decode()
            state_key = f"doc:state:{user_id}:{hash_sha256}"

            # Redis Pipeline으로 배치 처리 (1회 네트워크 왕복)
            pipe = self.redis_client.pipeline()
            pipe.publish(channel, message)
            pipe.set(state_key, message, ex=14400)

            if status not in ("completed", "failed"):
                heartbeat_key = f"doc:heartbeat:{user_id}:{hash_sha256}"
                pipe.set(heartbeat_key, int(time.time()), ex=30)

            results = pipe.execute()
            subscriber_count = results[0]

            logger.info(
                f"📡 Redis 이벤트 발행 성공 (hash): user_id={user_id}, hash={hash_sha256[:8]}..., "
                f"channel={channel}, stage={stage}, status={status}, subscribers={subscriber_count}"
            )

        except Exception as e:
            logger.error(
                f"❌ Redis 이벤트 발행 실패 (hash): user_id={user_id}, hash={hash_sha256[:8]}..., error={e}",
                exc_info=True,
            )

    def get_task_state(self, task_id: str) -> Optional[dict]:
        """
        저장된 작업 상태 가져오기

        Args:
            task_id: 작업 ID

        Returns:
            작업 상태 데이터
        """
        try:
            state_key = f"task:state:{task_id}"
            stored_state = self.redis_client.get(state_key)

            logger.info(f"[REDIS] get_task_state: key={state_key}, found={stored_state is not None}")

            if stored_state:
                parsed = orjson.loads(stored_state)
                logger.info(f"[REDIS] get_task_state 결과: task={task_id}, status={parsed.get('status')}, stage={parsed.get('stage')}")
                return parsed

            return None

        except Exception as e:
            logger.error(f"❌ Redis에서 작업 상태 가져오기 실패: task={task_id}, error={e}")
            return None

    def task_exists(self, task_id: str) -> bool:
        """
        작업 ID가 존재하는지 확인

        Args:
            task_id: 작업 ID

        Returns:
            작업 존재 여부
        """
        try:
            # Redis 연결 확인 및 재연결
            if not self.redis_client:
                logger.warning("Redis 연결이 없음, 재연결 시도")
                self._connect()
                if not self.redis_client:
                    logger.error("Redis 재연결 실패")
                    return False

            state_key = f"task:state:{task_id}"
            owner_key = f"task:owner:{task_id}"

            # exists 명령 직접 실행
            state_exists = self.redis_client.exists(state_key)
            owner_exists = self.redis_client.exists(owner_key)

            # 상태 키나 소유자 키 중 하나라도 존재하면 유효한 작업으로 간주
            result = state_exists > 0 or owner_exists > 0
            return result

        except Exception as e:
            logger.error(f"❌ Redis에서 작업 존재 여부 확인 실패: {e}", exc_info=True)
            return False

    def is_task_active(self, task_id: str) -> bool:
        """
        작업이 현재 활성 상태인지 확인 (heartbeat 기반)

        Args:
            task_id: 작업 ID

        Returns:
            작업 활성 여부 (30초 이내 heartbeat가 있으면 활성)
        """
        try:
            if not self.redis_client:
                self._connect()
                if not self.redis_client:
                    return False

            # heartbeat 키 확인
            heartbeat_key = f"task:heartbeat:{task_id}"
            heartbeat_exists = self.redis_client.exists(heartbeat_key)

            if heartbeat_exists > 0:
                # heartbeat가 존재하면 TTL 연장 (활성 작업 유지)
                self.extend_task_ttl(task_id)
                return True

            # heartbeat가 없어도 상태 확인
            state = self.get_task_state(task_id)
            if state:
                status = state.get("status", "")
                # 완료/실패 상태가 아니면 활성으로 간주
                if status not in ("completed", "failed"):
                    return True

            return False

        except Exception as e:
            logger.error(f"❌ 작업 활성 상태 확인 실패: {e}", exc_info=True)
            return False

    def extend_task_ttl(self, task_id: str) -> None:
        """
        활성 작업의 Redis TTL 연장

        Args:
            task_id: 작업 ID
        """
        try:
            if not self.redis_client:
                return

            # 상태 키와 소유자 키의 TTL 연장 (4시간)
            state_key = f"task:state:{task_id}"
            owner_key = f"task:owner:{task_id}"

            self.redis_client.expire(state_key, 14400)  # 4시간
            self.redis_client.expire(owner_key, 14400)  # 4시간

            logger.info(f"📌 작업 TTL 연장: task_id={task_id}")

        except Exception as e:
            logger.error(f"❌ TTL 연장 실패: {e}")

    def subscribe_task(self, task_id: str):
        """
        Redis Pub/Sub 채널 구독 (task_id 기반)

        Args:
            task_id: 작업 ID

        Returns:
            Redis PubSub 객체
        """
        try:
            pubsub = self.redis_client.pubsub()
            channel = f"sse:task:{task_id}"
            pubsub.subscribe(channel)

            # 현재 채널의 구독자 수 확인 (디버깅용)
            try:
                # PUBSUB NUMSUB 명령으로 구독자 수 확인
                result = self.redis_client.execute_command("PUBSUB", "NUMSUB", channel)
                subscriber_count = result[1] if result else 0
                logger.info(
                    f"[REDIS] 🎧 Redis 채널 구독: {channel}, 현재 구독자 수: {subscriber_count}"
                )
            except Exception:
                logger.info(f"[REDIS] 🎧 Redis 채널 구독: {channel}")

            return pubsub

        except Exception as e:
            logger.error(f"[REDIS] ❌ Redis 채널 구독 실패: {e}")
            return None

    def publish_user_notification(
        self,
        user_id: str,
        notification_type: str,
        data: dict,
    ) -> None:
        """
        사용자 레벨 알림 발행 (스케줄 실행 시작 등)

        Args:
            user_id: 사용자 ID
            notification_type: 알림 타입 (connected, schedule_started 등)
            data: 알림 데이터
        """
        try:
            # Redis 연결 확인 및 재연결
            if not self.redis_client:
                logger.warning("Redis 연결이 없음, 재연결 시도")
                self._connect()
                if not self.redis_client:
                    logger.error("Redis 재연결 실패")
                    return

            # 알림 데이터 구성
            notification_data = {
                "user_id": user_id,
                "type": notification_type,
                "timestamp": time.time(),
                **data,
            }

            # Redis 채널에 발행 (사용자별 알림 채널)
            channel = f"sse:user:{user_id}"
            message = orjson.dumps(notification_data).decode()

            # Redis Pub/Sub 채널에 발행
            subscriber_count = self.redis_client.publish(channel, message)

            logger.info(
                f"🔔 사용자 알림 발행 성공: user_id={user_id}, type={notification_type}, "
                f"channel={channel}, subscribers={subscriber_count}"
            )

        except Exception as e:
            logger.error(
                f"❌ 사용자 알림 발행 실패: user_id={user_id}, type={notification_type}, error={e}",
                exc_info=True,
            )

    def subscribe_user(self, user_id: str):
        """
        사용자 알림 채널 구독

        Args:
            user_id: 사용자 ID

        Returns:
            Redis PubSub 객체
        """
        try:
            pubsub = self.redis_client.pubsub()
            channel = f"sse:user:{user_id}"
            pubsub.subscribe(channel)

            # 현재 채널의 구독자 수 확인
            try:
                result = self.redis_client.execute_command("PUBSUB", "NUMSUB", channel)
                subscriber_count = result[1] if result else 0
                logger.info(
                    f"[REDIS] 🔔 사용자 알림 채널 구독: {channel}, 구독자 수: {subscriber_count}"
                )
            except Exception:
                logger.info(f"[REDIS] 🔔 사용자 알림 채널 구독: {channel}")

            return pubsub

        except Exception as e:
            logger.error(f"[REDIS] ❌ 사용자 알림 채널 구독 실패: {e}")
            return None

    def publish_user_task_event(
        self,
        user_id: str,
        task_id: str,
        hash_sha256: str,
        stage: str,
        status: str,
        description: Optional[str] = None,
        category: str = "",
    ) -> None:
        """
        사용자 통합 채널에 task 이벤트 발행 (배치 SSE용)

        모든 task 이벤트를 사용자별 단일 채널로 통합하여 발행합니다.
        HTTP/1.1 SSE 연결 제한(6개) 문제를 해결하기 위한 멀티플렉싱 채널입니다.

        Args:
            user_id: 사용자 ID
            task_id: 작업 ID
            hash_sha256: 문서 해시값
            stage: 파이프라인 단계
            status: 상태 (in_progress, completed, failed)
            description: 단계 설명 (optional)
            category: 문서 카테고리 (클라이언트 사이드 필터링용)
        """
        try:
            if not self.redis_client:
                logger.warning("Redis 연결이 없음, 재연결 시도")
                self._connect()
                if not self.redis_client:
                    logger.error("Redis 재연결 실패")
                    return

            # 이벤트 데이터 구성
            event_data = {
                "task_id": task_id,
                "hash_sha256": hash_sha256,
                "category": category,
                "stage": stage,
                "status": status,
                "timestamp": time.time(),
            }

            if description:
                event_data["description"] = description

            # 사용자 통합 채널에 발행
            channel = f"sse:user:{user_id}:tasks"
            message = orjson.dumps(event_data).decode()
            state_key = f"task:state:{task_id}"
            running_set_key = f"user:tasks:{user_id}"

            # Redis Pipeline으로 배치 처리 (1회 네트워크 왕복)
            pipe = self.redis_client.pipeline()
            pipe.publish(channel, message)

            # terminal 상태(completed/failed)인 경우: set에서 제거 + state 키 삭제
            # in_progress 상태인 경우: set에 추가 + state 키 저장
            if status in ("completed", "failed"):
                pipe.delete(state_key)
                pipe.srem(running_set_key, task_id)
            else:
                pipe.set(state_key, message, ex=14400)
                pipe.sadd(running_set_key, task_id)
                pipe.expire(running_set_key, 14400)

            results = pipe.execute()
            subscriber_count = results[0]

            logger.info(
                f"📡 사용자 통합 채널 이벤트 발행: user_id={user_id}, task_id={task_id}, "
                f"stage={stage}, status={status}, subscribers={subscriber_count}"
            )

        except Exception as e:
            logger.error(
                f"❌ 사용자 통합 채널 이벤트 발행 실패: user_id={user_id}, task_id={task_id}, error={e}",
                exc_info=True,
            )

    def subscribe_user_tasks(self, user_id: str):
        """
        사용자 통합 task 채널 구독 (배치 SSE용)

        Args:
            user_id: 사용자 ID

        Returns:
            Redis PubSub 객체
        """
        try:
            pubsub = self.redis_client.pubsub()
            channel = f"sse:user:{user_id}:tasks"
            pubsub.subscribe(channel)

            try:
                result = self.redis_client.execute_command("PUBSUB", "NUMSUB", channel)
                subscriber_count = result[1] if result else 0
                logger.info(
                    f"[REDIS] 📦 사용자 통합 task 채널 구독: {channel}, 구독자 수: {subscriber_count}"
                )
            except Exception:
                logger.info(f"[REDIS] 📦 사용자 통합 task 채널 구독: {channel}")

            return pubsub

        except Exception as e:
            logger.error(f"[REDIS] ❌ 사용자 통합 task 채널 구독 실패: {e}")
            return None

    def get_user_running_tasks(self, user_id: str) -> set:
        """
        사용자의 실행 중인 task 목록 조회

        Args:
            user_id: 사용자 ID

        Returns:
            실행 중인 task_id set
        """
        try:
            if not self.redis_client:
                return set()

            running_set_key = f"user:tasks:{user_id}"
            return self.redis_client.smembers(running_set_key)

        except Exception as e:
            logger.error(f"❌ 실행 중인 task 목록 조회 실패: user_id={user_id}, error={e}")
            return set()

    def get_multiple_task_states(self, task_ids: list) -> Dict[str, Any]:
        """
        여러 task의 상태를 한 번에 조회 (MGET 최적화)

        새로고침 시 클라이언트가 추적 중인 task들의 현재 상태를 조회합니다.
        Redis MGET을 사용하여 1번의 네트워크 왕복으로 모든 상태를 가져옵니다.

        Args:
            task_ids: 조회할 task_id 목록

        Returns:
            task_id를 키로, 상태 정보를 값으로 하는 딕셔너리
            예: {"task_1": {"stage": "completed", "status": "completed"}, ...}
        """
        result = {}

        if not task_ids:
            return result

        try:
            if not self.redis_client:
                logger.warning("Redis 연결이 없음, 재연결 시도")
                self._connect()
                if not self.redis_client:
                    logger.error("Redis 재연결 실패")
                    return result

            # MGET으로 한 번에 모든 상태 조회 (O(1) 네트워크 왕복)
            state_keys = [f"task:state:{task_id}" for task_id in task_ids]
            values = self.redis_client.mget(state_keys)

            # 결과 파싱
            for task_id, value in zip(task_ids, values):
                if value:
                    try:
                        result[task_id] = orjson.loads(value)
                    except (orjson.JSONDecodeError, TypeError) as e:
                        logger.warning(f"JSON 파싱 오류 (task={task_id}): {e}")

            logger.info(
                f"📊 다중 task 상태 조회 (MGET): 요청={len(task_ids)}개, 조회됨={len(result)}개"
            )

            return result

        except Exception as e:
            logger.error(f"❌ 다중 task 상태 조회 실패: error={e}", exc_info=True)
            return result


    def publish_category_event(
        self,
        user_id: str,
        task_id: str,
        hash_sha256: str,
        category: str,
        stage: str,
        status: str,
        description: Optional[str] = None,
    ) -> None:
        """
        카테고리 채널에 task 이벤트 발행

        카테고리별 SSE 필터링을 위한 전용 채널에 이벤트를 발행합니다.

        Args:
            user_id: 사용자 ID
            task_id: 작업 ID
            hash_sha256: 문서 해시값
            category: 문서 카테고리
            stage: 파이프라인 단계
            status: 상태 (in_progress, completed, failed)
            description: 단계 설명 (optional)
        """
        if not category:
            return

        try:
            if not self.redis_client:
                logger.warning("Redis 연결이 없음, 재연결 시도")
                self._connect()
                if not self.redis_client:
                    logger.error("Redis 재연결 실패")
                    return

            event_data = {
                "task_id": task_id,
                "hash_sha256": hash_sha256,
                "category": category,
                "stage": stage,
                "status": status,
                "timestamp": time.time(),
            }

            if description:
                event_data["description"] = description

            channel = f"sse:user:{user_id}:category:{category}"
            message = orjson.dumps(event_data).decode()
            running_set_key = f"user:category_tasks:{user_id}:{category}"

            pipe = self.redis_client.pipeline()
            pipe.publish(channel, message)

            if status in ("completed", "failed"):
                pipe.srem(running_set_key, task_id)
            else:
                pipe.sadd(running_set_key, task_id)
                pipe.expire(running_set_key, 14400)

            results = pipe.execute()
            subscriber_count = results[0]

            logger.info(
                f"📡 카테고리 채널 이벤트 발행: user_id={user_id}, category={category}, "
                f"task_id={task_id}, stage={stage}, status={status}, subscribers={subscriber_count}"
            )

        except Exception as e:
            logger.error(
                f"❌ 카테고리 채널 이벤트 발행 실패: user_id={user_id}, category={category}, error={e}",
                exc_info=True,
            )

    def subscribe_category(self, user_id: str, category: str):
        """
        카테고리 채널 구독

        Args:
            user_id: 사용자 ID
            category: 문서 카테고리

        Returns:
            Redis PubSub 객체
        """
        try:
            pubsub = self.redis_client.pubsub()
            channel = f"sse:user:{user_id}:category:{category}"
            pubsub.subscribe(channel)

            try:
                result = self.redis_client.execute_command("PUBSUB", "NUMSUB", channel)
                subscriber_count = result[1] if result else 0
                logger.info(
                    f"[REDIS] 📂 카테고리 채널 구독: {channel}, 구독자 수: {subscriber_count}"
                )
            except Exception:
                logger.info(f"[REDIS] 📂 카테고리 채널 구독: {channel}")

            return pubsub

        except Exception as e:
            logger.error(f"[REDIS] ❌ 카테고리 채널 구독 실패: {e}")
            return None

    def get_category_running_tasks(self, user_id: str, category: str) -> set:
        """
        카테고리별 실행 중인 task 목록 조회

        Args:
            user_id: 사용자 ID
            category: 문서 카테고리

        Returns:
            실행 중인 task_id set
        """
        try:
            if not self.redis_client:
                return set()

            running_set_key = f"user:category_tasks:{user_id}:{category}"
            return self.redis_client.smembers(running_set_key)

        except Exception as e:
            logger.error(
                f"❌ 카테고리 running task 조회 실패: user_id={user_id}, category={category}, error={e}"
            )
            return set()

    def get_category_multiple_task_states(self, user_id: str, category: str) -> Dict[str, Any]:
        """
        카테고리별 task 상태를 한 번에 조회 (MGET 최적화)

        Args:
            user_id: 사용자 ID
            category: 문서 카테고리

        Returns:
            task_id를 키로, 상태 정보를 값으로 하는 딕셔너리
        """
        task_ids = self.get_category_running_tasks(user_id, category)
        if not task_ids:
            return {}
        return self.get_multiple_task_states(list(task_ids))


# ========================================
# Factory Functions (프로세스별 독립 인스턴스)
# ========================================


@lru_cache(maxsize=128)
def _create_broker_for_pid(pid: int) -> RedisSSEBroker:
    """
    특정 프로세스 ID에 대한 Redis SSE Broker 인스턴스 생성.

    Args:
        pid: 프로세스 ID

    Returns:
        RedisSSEBroker 인스턴스

    Note:
        lru_cache를 사용하여 같은 PID에 대해서는 같은 인스턴스 반환.
        fork 후에는 PID가 달라지므로 새 인스턴스가 자동 생성됨.
    """
    logger.info(f"[REDIS] 새로운 Redis SSE Broker 인스턴스 생성: PID={pid}")
    return RedisSSEBroker()


def get_redis_sse_broker() -> Optional[RedisSSEBroker]:
    """
    현재 프로세스에 맞는 Redis SSE Broker 인스턴스 반환.

    각 프로세스(Celery worker, FastAPI)는 독립적인 Redis 연결을 가짐.
    fork-safety를 보장하기 위해 프로세스 ID 기반으로 캐싱.

    Returns:
        RedisSSEBroker 인스턴스 또는 None (실패 시)

    Example:
        >>> broker = get_redis_sse_broker()
        >>> if broker:
        ...     broker.publish_event(task_id="123", user_id="1", stage="parsing", status="in_progress")
    """
    try:
        current_pid = os.getpid()
        return _create_broker_for_pid(current_pid)
    except Exception as e:
        logger.error(
            f"[REDIS] Redis SSE Broker 인스턴스 생성 실패: PID={os.getpid()}, error={e}"
        )
        return None


def reset_broker_cache() -> None:
    """
    브로커 인스턴스 캐시 초기화.

    테스트나 워커 재시작 시 사용.
    현재 프로세스의 캐시만 정리됨.
    """
    _create_broker_for_pid.cache_clear()
    logger.info(f"[REDIS] 브로커 캐시 초기화: PID={os.getpid()}")


# ========================================
# 비동기 래퍼 함수 (FastAPI용 - asyncio.to_thread)
# ========================================
# Milvus 패턴과 동일하게 asyncio.to_thread를 사용하여
# 동기 Redis 메서드를 비동기로 래핑합니다.
# 이를 통해 FastAPI Event Loop 블로킹을 방지합니다.


async def async_task_exists(task_id: str) -> bool:
    """
    작업 ID 존재 여부 확인 (비동기 래퍼)

    Args:
        task_id: 작업 ID

    Returns:
        작업 존재 여부
    """
    broker = get_redis_sse_broker()
    if broker is None:
        return False
    return await asyncio.to_thread(broker.task_exists, task_id)


async def async_get_task_state(task_id: str) -> Optional[Dict[str, Any]]:
    """
    저장된 작업 상태 가져오기 (비동기 래퍼)

    Args:
        task_id: 작업 ID

    Returns:
        작업 상태 데이터
    """
    broker = get_redis_sse_broker()
    if broker is None:
        return None
    return await asyncio.to_thread(broker.get_task_state, task_id)


async def async_is_task_active(task_id: str) -> bool:
    """
    작업이 현재 활성 상태인지 확인 (비동기 래퍼)

    Args:
        task_id: 작업 ID

    Returns:
        작업 활성 여부
    """
    broker = get_redis_sse_broker()
    if broker is None:
        return False
    return await asyncio.to_thread(broker.is_task_active, task_id)


async def async_debug_redis_keys(
    task_id: str,
) -> tuple[bool, bool, int]:
    """
    Redis 키 디버깅 정보 조회 (비동기 래퍼)

    Args:
        task_id: 작업 ID

    Returns:
        (state_exists, owner_exists, state_ttl) 튜플
    """
    broker = get_redis_sse_broker()
    if broker is None or broker.redis_client is None:
        return (False, False, -1)

    def _check():
        state_key = f"task:state:{task_id}"
        owner_key = f"task:owner:{task_id}"
        state_exists = broker.redis_client.exists(state_key) > 0
        owner_exists = broker.redis_client.exists(owner_key) > 0
        state_ttl = broker.redis_client.ttl(state_key)
        return (state_exists, owner_exists, state_ttl)

    return await asyncio.to_thread(_check)


async def async_get_user_running_tasks(user_id: str) -> set:
    """
    사용자의 실행 중인 task 목록 조회 (비동기 래퍼)

    Args:
        user_id: 사용자 ID

    Returns:
        실행 중인 task_id set
    """
    broker = get_redis_sse_broker()
    if broker is None:
        return set()
    return await asyncio.to_thread(broker.get_user_running_tasks, user_id)


async def async_get_multiple_task_states(task_ids: list) -> Dict[str, Any]:
    """
    여러 task의 상태를 한 번에 조회 (비동기 래퍼)

    Args:
        task_ids: 조회할 task_id 목록

    Returns:
        task_id를 키로, 상태 정보를 값으로 하는 딕셔너리
    """
    broker = get_redis_sse_broker()
    if broker is None:
        return {}
    return await asyncio.to_thread(broker.get_multiple_task_states, task_ids)


async def async_get_category_running_tasks(user_id: str, category: str) -> set:
    """
    카테고리별 실행 중인 task 목록 조회 (비동기 래퍼)

    Args:
        user_id: 사용자 ID
        category: 문서 카테고리

    Returns:
        실행 중인 task_id set
    """
    broker = get_redis_sse_broker()
    if broker is None:
        return set()
    return await asyncio.to_thread(broker.get_category_running_tasks, user_id, category)


async def async_get_category_multiple_task_states(user_id: str, category: str) -> Dict[str, Any]:
    """
    카테고리별 task 상태를 한 번에 조회 (비동기 래퍼)

    Args:
        user_id: 사용자 ID
        category: 문서 카테고리

    Returns:
        task_id를 키로, 상태 정보를 값으로 하는 딕셔너리
    """
    broker = get_redis_sse_broker()
    if broker is None:
        return {}
    return await asyncio.to_thread(broker.get_category_multiple_task_states, user_id, category)
