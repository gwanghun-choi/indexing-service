import asyncio
import logging
import threading
from functools import lru_cache
from typing import AsyncGenerator, Dict, Optional

import orjson
import redis

from app.crud.milvus.document_crud import select_documents_by_status
from app.dto.document_status import DocumentStatus
from app.service.redis_sse_broker import (
    async_debug_redis_keys,
    async_get_category_running_tasks,
    async_get_multiple_task_states,
    async_get_task_state,
    async_get_user_running_tasks,
    async_is_task_active,
    get_redis_sse_broker,
)

logger = logging.getLogger(__name__)


class SSEManager:
    """
    Redis 기반 SSE(Server-Sent Events) 연결 관리
    각 task_id당 하나의 SSE 연결만 허용
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # task_id -> (queue, listener_thread, stop_event)
        self.active_connections: Dict[str, tuple] = {}

        # 동시성 제어용 락
        self._lock = threading.Lock()

        self._initialized = True
        logger.info("[SSE] ✅ SSE 매니저 초기화 완료")

    async def connect(self, task_id: str) -> AsyncGenerator[str, None]:
        """
        task_id별 SSE 스트림 연결 생성

        Args:
            task_id: 작업 ID (고유값)

        Yields:
            SSE 형식의 이벤트 문자열
        """
        logger.info(f"[SSE] 🚀 connect 메서드 호출됨: task={task_id!r}, len={len(task_id)}")

        queue = asyncio.Queue()
        current_loop = asyncio.get_running_loop()

        # 기존 연결이 있으면 정리 (새로고침 대응) - asyncio.to_thread로 래핑
        await asyncio.to_thread(self._cleanup_existing_connection, task_id)

        # 새 연결 등록 - asyncio.to_thread로 래핑
        logger.info(f"[SSE] 📝 새 연결 등록 중: task={task_id}")
        await asyncio.to_thread(self._register_connection, task_id, queue, current_loop)

        try:
            # 초기 상태 전송 (비동기 래퍼 사용 - Event Loop 블로킹 방지)
            initial_state = await async_get_task_state(task_id)
            logger.info(f"[SSE] 🔍 초기 상태 조회 결과: task={task_id}, state={initial_state}")

            if initial_state:
                logger.info(f"[SSE] 📤 초기 상태 전송: task={task_id}, status={initial_state['status']}")
                yield f"data: {orjson.dumps(initial_state).decode()}\n\n"

                # 초기 상태가 완료/실패면 즉시 종료 (새로고침 후 완료된 작업 처리)
                initial_status = initial_state["status"]
                if initial_status in ("completed", "failed"):
                    logger.info(f"[SSE] ✅ 초기 상태가 {initial_status}이므로 즉시 종료: task={task_id}")
                    return
            else:
                # 디버깅: Redis 키 확인
                try:
                    state_exists, owner_exists, state_ttl = await async_debug_redis_keys(task_id)
                    logger.warning(
                        f"[SSE] ⚠️ 초기 상태 없음: task={task_id}, "
                        f"state_exists={state_exists}, owner_exists={owner_exists}, ttl={state_ttl}"
                    )
                except Exception as e:
                    logger.warning(f"[SSE] ⚠️ 초기 상태 없음 (디버깅 실패): {e}")

            # 이벤트 스트리밍
            logger.info(f"[SSE] 스트리밍 시작: task={task_id}")
            heartbeat_interval = 3.0  # 3초마다 heartbeat (프록시 타임아웃 방지)
            heartbeat_counter = 0  # 상태 전송용 카운터

            while True:
                try:
                    # 10초 타임아웃으로 이벤트 대기
                    data = await asyncio.wait_for(
                        queue.get(), timeout=heartbeat_interval
                    )

                    if data is None:
                        logger.info(
                            f"[SSE] None 데이터 수신 - 정상 종료 신호: task={task_id}"
                        )
                        break

                    logger.info(
                        f"[SSE] 📤 이벤트 전송: task={task_id}, stage={data.get('stage')}"
                    )
                    yield f"data: {orjson.dumps(data).decode()}\n\n"

                    # 종료 상태 확인
                    status = data["status"]
                    if status in ("completed", "failed"):
                        logger.info(
                            f"[SSE] ✅ 작업 완료: task={task_id}, status={status}"
                        )
                        break

                except asyncio.TimeoutError:
                    # Heartbeat 전송 (10초마다) - 무조건 연결 유지
                    yield ": heartbeat\n\n"
                    heartbeat_counter += 1

                    # 주기적으로 작업 진행 상태 전송 (매 3번째 heartbeat마다 = 30초)
                    # 비동기 래퍼 사용 - Event Loop 블로킹 방지
                    if heartbeat_counter % 3 == 0:
                        current_state = await async_get_task_state(task_id)

                        if current_state:
                            # 작업이 완료되었는지 최종 확인
                            status = current_state["status"]
                            if status in ("completed", "failed"):
                                logger.info(
                                    f"[SSE] ✅ 작업 완료 확인: task={task_id}, status={status}"
                                )
                                yield f"data: {orjson.dumps(current_state).decode()}\n\n"
                                break

                            # 진행중인 작업의 상태 전송
                            current_state["heartbeat"] = True
                            yield f"data: {orjson.dumps(current_state).decode()}\n\n"
                            logger.info(
                                f"[SSE] 상태 업데이트 전송: task={task_id}, heartbeat #{heartbeat_counter}"
                            )

                    # 작업 활성 상태 확인 및 TTL 연장 (비동기 래퍼 사용)
                    await async_is_task_active(task_id)

                    # 타임아웃 없음 - 작업이 완료되거나 오류가 발생할 때까지 무한 유지

        except asyncio.CancelledError:
            # 클라이언트가 연결을 끊었거나 서버가 종료되는 경우
            logger.info(
                f"[SSE] 📱 클라이언트 연결 종료 (CancelledError): task={task_id}"
            )
            # 작업 상태 확인 - 아직 진행중이면 경고 (비동기 래퍼 사용)
            try:
                final_state = await async_get_task_state(task_id)
                if final_state:
                    status = final_state["status"]
                    if status not in ("completed", "failed"):
                        logger.warning(
                            f"[SSE] ⚠️ 작업이 아직 진행중인데 연결이 종료됨: task={task_id}, status={status}"
                        )
            except Exception:
                pass  # 정리 단계에서의 오류는 무시
        except GeneratorExit:
            logger.info(f"[SSE] 📤 Generator 정상 종료 (GeneratorExit): task={task_id}")
        except Exception as e:
            logger.error(f"[SSE] ❌ SSE 오류: task={task_id}, error={e}", exc_info=True)
        finally:
            self.disconnect(task_id)

    def _cleanup_existing_connection(self, task_id: str) -> bool:
        """
        기존 연결이 있으면 정리 후 False 반환

        새로고침 시 기존 연결의 event_loop이 죽어있을 수 있으므로,
        항상 기존 연결을 정리하고 새 연결을 생성해야 함.

        Returns:
            bool: 항상 False (새 연결 생성 필요)
        """
        with self._lock:
            if task_id in self.active_connections:
                logger.info(f"[SSE] 🔄 기존 연결 정리 중: task={task_id}")

        # Lock 밖에서 disconnect 호출 (deadlock 방지)
        if task_id in self.active_connections:
            self.disconnect(task_id)
            logger.info(f"[SSE] ✅ 기존 연결 정리 완료: task={task_id}")

        return False  # 항상 새 연결 생성

    def _register_connection(
        self, task_id: str, queue: asyncio.Queue, event_loop: asyncio.AbstractEventLoop
    ) -> threading.Thread:
        """새 연결 등록 및 리스너 시작"""

        # 스레드 중단용 이벤트
        stop_event = threading.Event()

        # Redis 리스너 스레드 시작
        listener_thread = threading.Thread(
            target=self._redis_listener,
            args=(task_id, queue, event_loop, stop_event),
            daemon=True,
            name=f"redis-{task_id}",
        )
        listener_thread.start()

        # 연결 정보 저장 (stop_event 포함)
        with self._lock:
            self.active_connections[task_id] = (queue, listener_thread, stop_event)

        logger.info(f"[SSE] 🔌 연결 생성: task={task_id}")
        return listener_thread

    def _redis_listener_generic(
        self,
        connection_key: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
        stop_event: threading.Event,
        subscribe_fn: callable,
        log_prefix: str,
    ) -> None:
        """
        범용 Redis 메시지 수신 스레드

        모든 리스너 타입(task, document, user, batch)에서 공통으로 사용하는
        Redis Pub/Sub 메시지 수신 로직을 처리합니다.

        Args:
            connection_key: 연결 식별자 (로깅용)
            queue: 이벤트를 전달할 asyncio Queue
            event_loop: 이벤트를 전달할 asyncio 이벤트 루프
            stop_event: 스레드 중단 신호
            subscribe_fn: Redis 채널 구독 함수 (pubsub 객체 반환)
            log_prefix: 로그 메시지 접두사 (예: "[SSE-REDIS]")
        """
        pubsub = None
        message_count = 0
        try:
            logger.info(f"{log_prefix} 🎯 Redis 리스너 스레드 시작: key={connection_key}")
            pubsub = subscribe_fn()
            if not pubsub:
                logger.error(f"{log_prefix} ❌ Redis 구독 실패: key={connection_key}")
                return

            logger.info(f"{log_prefix} 📡 리스너 시작 성공: key={connection_key}")

            while not stop_event.is_set():
                try:
                    message = pubsub.get_message(timeout=0.5)

                    if message is None:
                        continue

                    message_count += 1

                    if message_count % 5 == 0:
                        logger.info(
                            f"{log_prefix} 메시지 #{message_count} 처리중: key={connection_key}"
                        )

                    if not self._process_message(message, connection_key, queue, event_loop):
                        logger.warning(
                            f"{log_prefix} ⚠️ 메시지 처리 실패로 리스너 종료: key={connection_key}"
                        )
                        break

                except redis.ConnectionError:
                    logger.warning(f"{log_prefix} Redis 연결 끊김: key={connection_key}")
                    break
                except Exception as e:
                    if not stop_event.is_set():
                        logger.error(f"{log_prefix} 메시지 처리 중 오류: {e}")

            if stop_event.is_set():
                logger.info(f"{log_prefix} 🛑 중단 요청으로 정상 종료: key={connection_key}")

        except Exception as e:
            logger.error(
                f"{log_prefix} ❌ 리스너 오류: key={connection_key}, error={e}",
                exc_info=True,
            )
        finally:
            if pubsub:
                try:
                    pubsub.unsubscribe()
                    pubsub.close()
                except Exception as e:
                    logger.debug(f"{log_prefix} pubsub 정리 중 오류 (무시): {e}")
            logger.info(
                f"{log_prefix} 🔚 리스너 종료: key={connection_key}, 총 {message_count}개 메시지 처리"
            )

    def _redis_listener(
        self,
        task_id: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
        stop_event: threading.Event,
    ) -> None:
        """Redis 메시지 수신 스레드 (task 기반)"""
        broker = get_redis_sse_broker()
        self._redis_listener_generic(
            connection_key=task_id,
            queue=queue,
            event_loop=event_loop,
            stop_event=stop_event,
            subscribe_fn=lambda: broker.subscribe_task(task_id) if broker else None,
            log_prefix="[SSE-REDIS]",
        )

    def _process_message(
        self,
        message,
        task_id: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
    ) -> bool:
        """Redis 메시지 처리"""
        if message["type"] != "message":
            return True

        # 연결이 아직 활성인지 확인
        with self._lock:
            if task_id not in self.active_connections:
                logger.info(f"[SSE-REDIS] 연결 종료됨: task={task_id}")
                return False

        # 메시지 파싱 및 전송
        event_data = self._parse_message(message["data"])
        if event_data is None:
            return True

        # 이벤트 큐에 전송
        if not self._send_to_queue(event_data, queue, event_loop, task_id):
            return False

        return True

    def _parse_message(self, data) -> Optional[dict]:
        """메시지 파싱"""
        try:
            return orjson.loads(data)
        except (orjson.JSONDecodeError, TypeError) as e:
            logger.error(f"[SSE-REDIS] JSON 파싱 오류: {e}")
            return None

    def _send_to_queue(
        self,
        event_data,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
        task_id: str,
    ) -> bool:
        """이벤트를 큐에 전송"""
        try:
            # 이벤트 루프가 유효한지 확인
            if not event_loop or event_loop.is_closed():
                logger.warning(f"[SSE-REDIS] 이벤트 루프 무효: task={task_id}")
                return False

            future = asyncio.run_coroutine_threadsafe(queue.put(event_data), event_loop)
            future.result(timeout=1.0)

            logger.info(
                f"[SSE-REDIS] 📨 이벤트 수신: task={task_id}, "
                f"stage={event_data.get('stage')}"
            )
            return True

        except asyncio.TimeoutError:
            logger.warning(f"[SSE-REDIS] 큐 전송 타임아웃: task={task_id}")
            return True  # 타임아웃은 연결을 끊지 않음
        except Exception as e:
            logger.error(f"[SSE-REDIS] 큐 전송 오류: {e}")
            return False

    def _check_connection_exists(self, connection_key: str) -> bool:
        """
        연결 키가 이미 존재하는지 확인 (Thread-Safe)

        Args:
            connection_key: 연결 키 (예: "user:123", "task:abc")

        Returns:
            연결 존재 여부
        """
        with self._lock:
            return connection_key in self.active_connections

    def disconnect(self, task_id: str) -> None:
        """SSE 연결 종료 - 스레드 안전하게 정리"""
        connection_data = None
        with self._lock:
            connection_data = self.active_connections.pop(task_id, None)

        if connection_data:
            queue, listener_thread, stop_event = connection_data

            # 스레드 중단 신호 전송
            stop_event.set()

            # 스레드가 종료될 때까지 대기 (최대 5초)
            listener_thread.join(timeout=5.0)

            if listener_thread.is_alive():
                logger.warning(f"[SSE] ⚠️ 스레드가 5초 내 종료되지 않음: task={task_id}")
            else:
                logger.info(f"[SSE] 🔌 연결 및 스레드 정상 종료: task={task_id}")

    async def connect_user(
        self, user_id: str, group_id: int
    ) -> AsyncGenerator[str, None]:
        """
        사용자 레벨 알림 채널 연결 (스케줄 실행 알림 등)

        Args:
            user_id: 사용자 ID
            group_id: 그룹 ID

        Yields:
            SSE 포맷 메시지 (data: {...})
        """
        connection_key = f"user:{user_id}"

        # 현재 이벤트 루프 가져오기
        current_loop = asyncio.get_running_loop()

        # 중복 연결 방지: 락 체크를 asyncio.to_thread로 래핑 (Event Loop 블로킹 방지)
        is_duplicate = await asyncio.to_thread(
            self._check_connection_exists, connection_key
        )
        if is_duplicate:
            logger.warning(
                f"[SSE-USER] ❌ 중복 연결 거부: user={user_id} "
                f"(이미 활성 연결 존재, 기존 브라우저 탭을 닫아주세요)"
            )
            # 에러 메시지 전송 후 종료 (락 밖에서 yield)
            error_msg = {
                "error": "duplicate_connection",
                "message": "Only one connection per user allowed. Please close other tabs/windows."
            }
            yield f"data: {orjson.dumps(error_msg).decode()}\n\n"
            return
        
        # 새 연결 등록 - asyncio.to_thread로 래핑
        queue = asyncio.Queue()
        await asyncio.to_thread(
            self._register_connection_user,
            user_id, connection_key, queue, current_loop
        )

        try:
            # 초기 상태 전송: 실행 중인 문서 조회
            running_docs = await select_documents_by_status(
                group_id=group_id,
                status=DocumentStatus.RUNNING,
                limit=1000,
            )

            # 초기 메시지 구성
            running_documents = [
                {"hash_sha256": doc.get("hash_sha256")}
                for doc in running_docs
                if doc.get("hash_sha256")
            ]

            initial_state = {
                "type": "connected",
                "current_running_tasks": len(running_documents),
                "running_documents": running_documents,
            }

            logger.info(
                f"[SSE-USER] 📤 초기 상태 전송: user_id={user_id}, running={len(running_documents)}"
            )
            yield f"data: {orjson.dumps(initial_state).decode()}\n\n"

            # 이벤트 스트리밍
            logger.info(f"[SSE-USER] 🔔 스트리밍 시작: user_id={user_id}")
            heartbeat_interval = 30.0  # 30초마다 heartbeat

            while True:
                try:
                    # 30초 타임아웃으로 이벤트 대기
                    data = await asyncio.wait_for(
                        queue.get(), timeout=heartbeat_interval
                    )

                    if data is None:
                        logger.info(
                            f"[SSE-USER] None 데이터 수신 - 정상 종료 신호: user_id={user_id}"
                        )
                        break

                    logger.info(
                        f"[SSE-USER] 📤 알림 전송: user_id={user_id}, type={data.get('type')}"
                    )
                    yield f"data: {orjson.dumps(data).decode()}\n\n"

                except asyncio.TimeoutError:
                    # Heartbeat 전송
                    yield ": heartbeat\n\n"

        except asyncio.CancelledError:
            logger.info(
                f"[SSE-USER] 📱 클라이언트 연결 종료 (CancelledError): user_id={user_id}"
            )
        except GeneratorExit:
            logger.info(
                f"[SSE-USER] 📤 Generator 정상 종료 (GeneratorExit): user_id={user_id}"
            )
        except Exception as e:
            logger.error(
                f"[SSE-USER] ❌ SSE 오류: user_id={user_id}, error={e}",
                exc_info=True,
            )
        finally:
            self.disconnect(connection_key)

    def _register_connection_user(
        self,
        user_id: str,
        connection_key: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
    ) -> threading.Thread:
        """사용자 알림 채널 연결 등록 및 리스너 시작"""

        # 스레드 중단용 이벤트
        stop_event = threading.Event()

        # Redis 리스너 스레드 시작
        listener_thread = threading.Thread(
            target=self._redis_listener_user,
            args=(user_id, connection_key, queue, event_loop, stop_event),
            daemon=True,
            name=f"redis-user-{user_id}",
        )
        listener_thread.start()

        # 연결 정보 저장 (stop_event 포함)
        with self._lock:
            self.active_connections[connection_key] = (
                queue,
                listener_thread,
                stop_event,
            )

        logger.info(f"[SSE-USER] 🔌 연결 생성: key={connection_key}")
        return listener_thread

    def _redis_listener_user(
        self,
        user_id: str,
        connection_key: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
        stop_event: threading.Event,
    ) -> None:
        """Redis 메시지 수신 스레드 (사용자 알림 채널)"""
        broker = get_redis_sse_broker()
        self._redis_listener_generic(
            connection_key=connection_key,
            queue=queue,
            event_loop=event_loop,
            stop_event=stop_event,
            subscribe_fn=lambda: broker.subscribe_user(user_id) if broker else None,
            log_prefix="[SSE-REDIS-USER]",
        )

    async def connect_batch(
        self, user_id: str, group_id: int
    ) -> AsyncGenerator[str, None]:
        """
        사용자의 모든 task 이벤트를 단일 채널로 스트리밍 (배치 SSE)

        HTTP/1.1 SSE 연결 제한(6개) 문제를 해결하기 위한 멀티플렉싱 채널입니다.
        모든 task 이벤트에 task_id가 포함되어 클라이언트에서 구분할 수 있습니다.

        새로고침 시 실행 중인 task들의 현재 상태를 자동으로 조회하여 초기 상태로 전송합니다.

        Args:
            user_id: 사용자 ID
            group_id: 그룹 ID

        Yields:
            SSE 포맷 메시지 (data: {...})
        """
        connection_key = f"batch:{user_id}"

        current_loop = asyncio.get_running_loop()

        # 중복 연결 방지
        is_duplicate = await asyncio.to_thread(
            self._check_connection_exists, connection_key
        )
        if is_duplicate:
            logger.warning(
                f"[SSE-BATCH] ❌ 중복 연결 거부: user={user_id} "
                f"(이미 활성 연결 존재)"
            )
            error_msg = {
                "error": "duplicate_connection",
                "message": "Only one batch connection per user allowed.",
            }
            yield f"data: {orjson.dumps(error_msg).decode()}\n\n"
            return

        # 새 연결 등록
        queue = asyncio.Queue()
        await asyncio.to_thread(
            self._register_connection_batch,
            user_id,
            connection_key,
            queue,
            current_loop,
        )

        try:
            # 초기 상태 전송: 실행 중인 task 목록
            running_task_ids = await async_get_user_running_tasks(user_id)
            running_tasks = list(running_task_ids)

            # 실행 중인 task들의 현재 상태를 자동 조회 (새로고침 대응)
            task_states = {}
            if running_tasks:
                task_states = await async_get_multiple_task_states(running_tasks)
                logger.info(
                    f"[SSE-BATCH] 📊 task 상태 자동 조회: running={len(running_tasks)}개, 조회됨={len(task_states)}개"
                )

            initial_state = {
                "type": "connected",
                "running_tasks": running_tasks,
                "running_count": len(running_tasks),
            }

            logger.info(
                f"[SSE-BATCH] 📤 초기 상태 전송: user_id={user_id}, running={len(running_tasks)}, "
                f"task_states={len(task_states)}개"
            )
            yield f"data: {orjson.dumps(initial_state).decode()}\n\n"

            # 각 task의 마지막 상태를 개별 이벤트로 전송 (일반 이벤트와 동일한 형태)
            for task_id, state in task_states.items():
                yield f"data: {orjson.dumps(state).decode()}\n\n"

            # 진행 중인 task가 없으면 즉시 종료
            # task_states가 비어있어도 running_tasks가 있으면 연결 유지
            # (State Key가 만료되었지만 Running Set에는 남아있는 경우 대응)
            if not running_tasks:
                logger.info(
                    f"[SSE-BATCH] 진행 중인 task 없음 - 연결 종료: user_id={user_id}"
                )
                return

            if task_states:
                has_in_progress = any(
                    state["status"] not in ("completed", "failed")
                    for state in task_states.values()
                )
                if not has_in_progress:
                    logger.info(
                        f"[SSE-BATCH] 모든 task 완료 - 연결 종료: user_id={user_id}"
                    )
                    return

            # 이벤트 스트리밍
            logger.info(f"[SSE-BATCH] 📦 스트리밍 시작: user_id={user_id}")
            heartbeat_interval = 3.0

            while True:
                try:
                    data = await asyncio.wait_for(
                        queue.get(), timeout=heartbeat_interval
                    )

                    if data is None:
                        logger.info(
                            f"[SSE-BATCH] None 데이터 수신 - 정상 종료: user_id={user_id}"
                        )
                        break

                    logger.info(
                        f"[SSE-BATCH] 📤 이벤트 전송: user_id={user_id}, "
                        f"task_id={data['task_id']}, stage={data['stage']}"
                    )
                    yield f"data: {orjson.dumps(data).decode()}\n\n"

                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"

        except asyncio.CancelledError:
            logger.info(
                f"[SSE-BATCH] 📱 클라이언트 연결 종료 (CancelledError): user_id={user_id}"
            )
        except GeneratorExit:
            logger.info(
                f"[SSE-BATCH] 📤 Generator 정상 종료 (GeneratorExit): user_id={user_id}"
            )
        except Exception as e:
            logger.error(
                f"[SSE-BATCH] ❌ SSE 오류: user_id={user_id}, error={e}",
                exc_info=True,
            )
        finally:
            self.disconnect(connection_key)

    def _register_connection_batch(
        self,
        user_id: str,
        connection_key: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
    ) -> threading.Thread:
        """배치 채널 연결 등록 및 리스너 시작"""

        stop_event = threading.Event()

        listener_thread = threading.Thread(
            target=self._redis_listener_batch,
            args=(user_id, connection_key, queue, event_loop, stop_event),
            daemon=True,
            name=f"redis-batch-{user_id}",
        )
        listener_thread.start()

        with self._lock:
            self.active_connections[connection_key] = (
                queue,
                listener_thread,
                stop_event,
            )

        logger.info(f"[SSE-BATCH] 🔌 연결 생성: key={connection_key}")
        return listener_thread

    def _redis_listener_batch(
        self,
        user_id: str,
        connection_key: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
        stop_event: threading.Event,
    ) -> None:
        """Redis 메시지 수신 스레드 (배치 채널)"""
        broker = get_redis_sse_broker()
        self._redis_listener_generic(
            connection_key=connection_key,
            queue=queue,
            event_loop=event_loop,
            stop_event=stop_event,
            subscribe_fn=lambda: broker.subscribe_user_tasks(user_id) if broker else None,
            log_prefix="[SSE-REDIS-BATCH]",
        )

    async def connect_category(
        self, user_id: str, category: str
    ) -> AsyncGenerator[str, None]:
        """
        카테고리별 task 이벤트를 스트리밍하는 SSE 연결

        특정 카테고리의 task 이벤트만 필터링하여 전달합니다.
        connect_batch()와 동일한 패턴을 따릅니다.

        Args:
            user_id: 사용자 ID
            category: 문서 카테고리

        Yields:
            SSE 포맷 메시지 (data: {...})
        """
        connection_key = f"category:{user_id}:{category}"

        current_loop = asyncio.get_running_loop()

        # 중복 연결 방지
        is_duplicate = await asyncio.to_thread(
            self._check_connection_exists, connection_key
        )
        if is_duplicate:
            logger.warning(
                f"[SSE-CATEGORY] ❌ 중복 연결 거부: user={user_id}, category={category} "
                f"(이미 활성 연결 존재)"
            )
            error_msg = {
                "error": "duplicate_connection",
                "message": "Only one category connection per user per category allowed.",
            }
            yield f"data: {orjson.dumps(error_msg).decode()}\n\n"
            return

        # 새 연결 등록
        queue = asyncio.Queue()
        await asyncio.to_thread(
            self._register_connection_category,
            user_id,
            category,
            connection_key,
            queue,
            current_loop,
        )

        try:
            # 초기 상태 전송: 카테고리별 실행 중인 task 목록
            running_task_ids = await async_get_category_running_tasks(user_id, category)
            running_tasks = list(running_task_ids)

            # 실행 중인 task들의 현재 상태를 자동 조회 (새로고침 대응)
            task_states = {}
            if running_tasks:
                task_states = await async_get_multiple_task_states(running_tasks)
                logger.info(
                    f"[SSE-CATEGORY] 📊 task 상태 자동 조회: category={category}, "
                    f"running={len(running_tasks)}개, 조회됨={len(task_states)}개"
                )

            initial_state = {
                "type": "connected",
                "category": category,
                "running_tasks": running_tasks,
                "running_count": len(running_tasks),
            }

            logger.info(
                f"[SSE-CATEGORY] 📤 초기 상태 전송: user_id={user_id}, category={category}, "
                f"running={len(running_tasks)}"
            )
            yield f"data: {orjson.dumps(initial_state).decode()}\n\n"

            # 각 task의 마지막 상태를 개별 이벤트로 전송
            for task_id, state in task_states.items():
                yield f"data: {orjson.dumps(state).decode()}\n\n"

            # 진행 중인 task가 없으면 즉시 종료
            # task_states가 비어있어도 running_tasks가 있으면 연결 유지
            # (State Key가 만료되었지만 Running Set에는 남아있는 경우 대응)
            if not running_tasks:
                logger.info(
                    f"[SSE-CATEGORY] 진행 중인 task 없음 - 연결 종료: "
                    f"user_id={user_id}, category={category}"
                )
                return

            if task_states:
                has_in_progress = any(
                    state["status"] not in ("completed", "failed")
                    for state in task_states.values()
                )
                if not has_in_progress:
                    logger.info(
                        f"[SSE-CATEGORY] 모든 task 완료 - 연결 종료: "
                        f"user_id={user_id}, category={category}"
                    )
                    return

            # 이벤트 스트리밍
            logger.info(
                f"[SSE-CATEGORY] 📂 스트리밍 시작: user_id={user_id}, category={category}"
            )
            heartbeat_interval = 3.0

            while True:
                try:
                    data = await asyncio.wait_for(
                        queue.get(), timeout=heartbeat_interval
                    )

                    if data is None:
                        logger.info(
                            f"[SSE-CATEGORY] None 데이터 수신 - 정상 종료: "
                            f"user_id={user_id}, category={category}"
                        )
                        break

                    logger.info(
                        f"[SSE-CATEGORY] 📤 이벤트 전송: user_id={user_id}, "
                        f"category={category}, task_id={data['task_id']}, stage={data['stage']}"
                    )
                    yield f"data: {orjson.dumps(data).decode()}\n\n"

                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"

        except asyncio.CancelledError:
            logger.info(
                f"[SSE-CATEGORY] 📱 클라이언트 연결 종료 (CancelledError): "
                f"user_id={user_id}, category={category}"
            )
        except GeneratorExit:
            logger.info(
                f"[SSE-CATEGORY] 📤 Generator 정상 종료 (GeneratorExit): "
                f"user_id={user_id}, category={category}"
            )
        except Exception as e:
            logger.error(
                f"[SSE-CATEGORY] ❌ SSE 오류: user_id={user_id}, category={category}, error={e}",
                exc_info=True,
            )
        finally:
            self.disconnect(connection_key)

    def _register_connection_category(
        self,
        user_id: str,
        category: str,
        connection_key: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
    ) -> threading.Thread:
        """카테고리 채널 연결 등록 및 리스너 시작"""

        stop_event = threading.Event()

        listener_thread = threading.Thread(
            target=self._redis_listener_category,
            args=(user_id, category, connection_key, queue, event_loop, stop_event),
            daemon=True,
            name=f"redis-category-{user_id}-{category}",
        )
        listener_thread.start()

        with self._lock:
            self.active_connections[connection_key] = (
                queue,
                listener_thread,
                stop_event,
            )

        logger.info(f"[SSE-CATEGORY] 🔌 연결 생성: key={connection_key}")
        return listener_thread

    def _redis_listener_category(
        self,
        user_id: str,
        category: str,
        connection_key: str,
        queue: asyncio.Queue,
        event_loop: asyncio.AbstractEventLoop,
        stop_event: threading.Event,
    ) -> None:
        """Redis 메시지 수신 스레드 (카테고리 채널)"""
        broker = get_redis_sse_broker()
        self._redis_listener_generic(
            connection_key=connection_key,
            queue=queue,
            event_loop=event_loop,
            stop_event=stop_event,
            subscribe_fn=lambda: broker.subscribe_category(user_id, category) if broker else None,
            log_prefix="[SSE-REDIS-CATEGORY]",
        )


# ========================================
# Factory Functions (FastAPI 프로세스용)
# ========================================


@lru_cache(maxsize=1)
def _create_sse_manager() -> SSEManager:
    """
    SSE Manager 인스턴스 생성 (프로세스당 하나).

    Returns:
        SSEManager 인스턴스

    Note:
        lru_cache를 사용하여 프로세스당 하나의 인스턴스만 생성.
        FastAPI 프로세스에서만 사용됨 (Celery worker와 분리).
    """
    logger.info("[SSE-MANAGER] 새로운 SSE Manager 인스턴스 생성")
    return SSEManager()


def get_sse_manager() -> Optional[SSEManager]:
    """
    SSE Manager 인스턴스 반환.

    FastAPI 의존성 주입에서 사용.

    Returns:
        SSEManager 인스턴스 또는 None (실패 시)

    Example:
        >>> from fastapi import Depends
        >>>
        >>> async def my_endpoint(sse_mgr: SSEManager = Depends(get_sse_manager)):
        ...     async for event in sse_mgr.connect(task_id):
        ...         yield event
    """
    try:
        return _create_sse_manager()
    except Exception as e:
        logger.error(f"[SSE-MANAGER] SSE Manager 생성 실패: {e}")
        return None
