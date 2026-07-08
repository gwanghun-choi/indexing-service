import asyncio
import datetime as _dt
import json
import logging
from pathlib import PurePosixPath
from typing import Any, Optional

import aio_pika
from aio_pika.exceptions import ChannelClosed, ConnectionClosed

from app.config.settings import settings
from app.service.document_registration_pipeline import (
    run_document_registration_pipeline,
)
from app.service.integrated_pipeline import run_integrated_pipeline

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# cloud-storage publish body → indexing request_payload 변환 helper
#
# cloud-storage 의 `notify_upload_complete` (presigned_url_api.py) 가
# `StorageTaskMessage` 형식으로 publish — `user_info.passport_data` 에 사용자 정보,
# `metadata.routing_analysis.routing_key` 에 category 추론 정보. `urls` / `title` /
# `category` / `expiration_date` 는 publish 시 미포함 → indexing 측에서 default 보강.
# ─────────────────────────────────────────────────────────────────

_DEFAULT_DOWNLOAD_URL_BASE = "http://cloud-storage:8006/v1/local/download"
_DEFAULT_EXPIRATION_DAYS = 365


def _extract_passport_from_body(body: dict) -> dict[str, Any]:
    """cloud-storage publish body 의 `user_info.passport_data` 에서 indexing schema 추출.

    cloud-storage `_serialize_passport_data` 로 직렬화된 형식:
    - `user_id`: str (예: "1")
    - `groups`: list[str] (예: ["1"])
    - `total_roles`: list[int] (예: [1])

    indexing 측 `request_payload` 가 기대하는 형식:
    - `user_id`: int
    - `group_id`: int (첫 번째 그룹)
    - `total_role`: list[int]
    """
    passport_data = body.get("user_info", {}).get("passport_data", {})
    return {
        "user_id": int(passport_data["user_id"]),
        "group_id": int(passport_data["groups"][0]),
        "total_role": passport_data["total_roles"],
    }


def _default_download_url(file_path: str) -> str:
    """`urls.stream_url` 부재 시 internal cluster DNS 기반 default 생성."""
    return f"{_DEFAULT_DOWNLOAD_URL_BASE}/{file_path}"


def _default_title(file_path: str) -> str:
    """`title` 부재 시 file_path 의 basename (확장자 포함) 추출."""
    return PurePosixPath(file_path).name


def _extract_category_from_routing_key(routing_analysis: Optional[dict]) -> str:
    """`file.uploaded.<category>.<ext>.<size>.<priority>` 의 `<category>` 추출.

    cloud-storage `SmartRoutingManager.generate_routing_key` 의 형식 박제.
    부재 / 비표준 routing_key 면 "general" fallback.
    """
    routing_key = (routing_analysis or {}).get("routing_key", "")
    parts = routing_key.split(".")
    if len(parts) >= 3 and parts[0] == "file" and parts[1] == "uploaded":
        return parts[2]
    return "general"


def _default_expiration_date() -> str:
    """`expiration_date` 부재 시 now + 365일 ISO 8601 string.

    indexing `insert_initial_metadata` 가 `.replace("Z", "+00:00")` + `fromisoformat()`
    로 파싱 → string 형식 필수 (int unix timestamp 는 AttributeError).
    """
    return (
        _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=_DEFAULT_EXPIRATION_DAYS)
    ).isoformat()


def _default_filename(file_path: str) -> str:
    """`filename` 부재 시 file_path 의 basename — `_default_title` 와 동일."""
    return _default_title(file_path)


def _default_file_type(file_path: str) -> str:
    """`file_type` 부재 시 file_path 의 확장자 (소문자, dot 제외). 부재 시 'unknown'."""
    suffix = PurePosixPath(file_path).suffix
    return suffix[1:].lower() if suffix else "unknown"


def _serialize_passport_for_header(body: dict) -> str:
    """cloud-storage publish body 의 `user_info.passport_data` → indexing/auth 측이
    인식하는 `x-user-passport` 헤더 형식 JSON string.

    cloud-storage 의 serialize schema:
        `user_id` (str) / `global_role` / `groups` (list[str]) / `total_roles` (list[int])

    auth/indexing 측이 인식하는 형식:
        `user_id` / `global_role` / `group_passport.group_list` / `total_role`

    `download_document` 등 후속 worker 가 cloud-storage 의 인증 endpoint 호출 시 사용.
    """
    passport_data = body.get("user_info", {}).get("passport_data", {})
    return json.dumps(
        {
            "user_id": passport_data.get("user_id"),
            "global_role": passport_data.get("global_role", {}),
            "group_passport": {
                "group_list": passport_data.get("groups", []),
                "group_roles": {},
                "in_group_role": {},
            },
            "total_role": passport_data.get("total_roles", []),
            "role_permission": passport_data.get("permissions") or {},
            "role": passport_data.get("global_role", {}).get("name", "USER"),
        }
    )


class RabbitMQConsumer:
    def __init__(self):
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queue: Optional[aio_pika.Queue] = None
        self._consumer_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None  # 재연결 태스크 추적
        self._is_connected = False
        self._is_reconnecting = False
        self._reconnect_interval = 5
        self._health_check_interval = 60  # 30초 -> 60초로 증가 (불필요한 체크 감소)
        self._shutdown = False

    async def connect(self):
        try:
            # aio_pika.connect_robust 사용 - 자동 재연결 기능 포함
            self.connection = await aio_pika.connect_robust(
                self.rabbitmq_url,
                reconnect_interval=self._reconnect_interval,
                fail_fast=True,
            )

            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)  # 메시지 처리 공정성 보장

            # Exchange 선언
            exchange = await self.channel.declare_exchange(
                settings.RABBITMQ_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
            )

            # 큐 선언 및 바인딩
            queue = await self.channel.declare_queue(
                settings.RABBITMQ_QUEUE, durable=True
            )
            await queue.bind(exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)
            logger.info(f"✅ Queue 바인딩: {settings.RABBITMQ_ROUTING_KEY}")

            self.queue = queue
            self._is_connected = True
            logger.info("✅ RabbitMQ 연결 완료")
        except Exception as e:
            self._is_connected = False
            logger.error(f"❌ RabbitMQ 연결 실패: {e}")
            raise

    async def consume_message(self, message):
        async with message.process():
            try:
                body = json.loads(message.body.decode("utf-8"))

                # 필수 필드 직접 접근 (없으면 KeyError 발생)
                task_id = body["task_id"]
                file_path = body["file_path"]
                file_size = body["file_size"]
                metadata = body["metadata"]

                logger.info(f"📨 메시지 수신: task_id={task_id}, file_path={file_path}")

                # 옵션 확인 (기본값: true - 분리 모드가 기본)
                # pipeline_separation만 기본값 허용
                pipeline_separation = metadata.get("pipeline_separation", True)

                # cloud-storage publish body schema → indexing request_payload 변환
                # passport_data 는 `body.user_info.passport_data` 위치 (StorageTaskMessage 형식).
                # urls/title/category/expiration_date 는 publish 시 미포함이라 default 보강.
                passport = _extract_passport_from_body(body)
                routing_analysis = metadata.get("routing_analysis", {})

                request_payload = {
                    "task_id": task_id,
                    "user_id": passport["user_id"],
                    "group_id": passport["group_id"],
                    "total_role": passport["total_role"],
                    "file_path": file_path,
                    "file_size": file_size,
                    # passport JSON — download_document 등 후속 worker 가
                    # cloud-storage 인증 endpoint 호출 시 `x-user-passport` 헤더로 사용.
                    "passport_json": _serialize_passport_for_header(body),
                    "download_url": (
                        metadata.get("urls", {}).get("stream_url")
                        or _default_download_url(file_path)
                    ),
                    "title": metadata.get("title") or _default_title(file_path),
                    "filename": metadata.get("filename") or _default_filename(file_path),
                    "file_type": metadata.get("file_type") or _default_file_type(file_path),
                    "category": (
                        metadata.get("category")
                        or _extract_category_from_routing_key(routing_analysis)
                    ),
                    "expiration_date": (
                        metadata.get("expiration_date") or _default_expiration_date()
                    ),
                    # 임베딩 관련 파라미터 기본값 설정 (모든 모드에서 필수)
                    "chunk_size": 0,
                    "chunk_overlap": 0,
                    "enable_pii_anonymization": False,
                    "pii_strategy": "",  # Milvus varchar 필드는 None 불가, 빈 문자열 사용
                    "pii_types": [],
                    "persona_id": 0,
                    "filter_score": 0.0,
                }

                # 분리 모드: 기본값 유지 (임베딩 파라미터 사용 안 함)
                # 통합 모드: 실제 값으로 업데이트 (임베딩 파라미터 사용)
                if not pipeline_separation:
                    request_payload.update(
                        {
                            "chunk_size": metadata.get("chunk_size", 0),
                            "chunk_overlap": metadata.get("chunk_overlap", 0),
                            "enable_pii_anonymization": metadata.get(
                                "enable_pii_anonymization", False
                            ),
                            "pii_strategy": metadata.get("pii_strategy", ""),
                            "pii_types": metadata.get("pii_types", []),
                            "persona_id": metadata.get("persona_id", 0),
                            "filter_score": metadata.get("filter_score", 0.0),
                        }
                    )

                # 모드에 따라 다른 파이프라인을 직접 실행
                if pipeline_separation:
                    # 📋 분리 모드 (기본): 메타데이터 등록만
                    logger.info(f"📋 분리 모드 - task_id={task_id}")

                    run_document_registration_pipeline.apply_async(
                        args=[request_payload], task_id=task_id
                    )

                    logger.info("✅ 등록 파이프라인 큐 등록 완료")

                else:
                    # 🚀 통합 모드: 전체 파이프라인 한번에
                    logger.info(f"🚀 통합 모드 - task_id={task_id}")

                    run_integrated_pipeline.apply_async(
                        args=[request_payload], task_id=task_id
                    )

                    logger.info("✅ 통합 파이프라인 큐 등록 완료")

            except KeyError as e:
                # 필수 필드 누락
                logger.error(f"❌ 필수 필드 누락: {e}")
                logger.error(
                    f"❌ 메시지 본문: {json.dumps(body, indent=2, ensure_ascii=False)}"
                )
                # 메시지 ACK 처리하여 재시도 방지
                await message.ack()

            except Exception as e:
                # 기타 예외 처리
                logger.error(f"❌ 메시지 처리 중 오류: {e}")
                logger.error(
                    f"❌ 메시지 본문: {json.dumps(body, indent=2, ensure_ascii=False)}"
                )
                # 메시지 ACK 처리하여 재시도 방지
                await message.ack()

    async def _handle_reconnect(self):
        """재연결 처리 로직"""
        if self._is_reconnecting:
            return  # 이미 재연결 중이면 중복 실행 방지

        self._is_reconnecting = True
        logger.info("🔄 재연결 시도 중...")

        try:
            # 기존 컨슈머 태스크 확실히 정리
            if self._consumer_task:
                self._consumer_task.cancel()
                try:
                    await asyncio.wait_for(self._consumer_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                finally:
                    self._consumer_task = None

            # 재연결
            await self.connect()

            # 새 컨슈머 태스크 시작
            self._consumer_task = asyncio.create_task(self.consume_messages())
            logger.info("✅ 컨슈머 재시작 완료")
        except Exception as e:
            logger.error(f"❌ 재연결 실패: {e}")
            # 재연결 실패 시 일정 시간 후 다시 시도
            await asyncio.sleep(self._reconnect_interval)
        finally:
            self._is_reconnecting = False

    async def health_check(self):
        """주기적인 헬스체크 수행"""
        while not self._shutdown:
            try:
                needs_reconnect = False

                # 1. 연결 상태 확인
                if not self.connection or self.connection.is_closed:
                    logger.info("⚠️ 헬스체크: 연결 닫힘 감지")
                    needs_reconnect = True
                elif not self.channel or self.channel.is_closed:
                    logger.info("⚠️ 헬스체크: 채널 닫힘 감지")
                    needs_reconnect = True
                # 2. Consumer Task 상태 확인 (핵심!)
                elif not self._consumer_task or self._consumer_task.done():
                    logger.info("⚠️ 헬스체크: 컨슈머 태스크 종료 감지")

                    # 예외 발생으로 종료됐는지 확인
                    if self._consumer_task and self._consumer_task.done():
                        try:
                            exc = self._consumer_task.exception()
                            if exc:
                                logger.info(f"❌ 컨슈머 태스크 예외로 종료: {exc}")
                        except asyncio.CancelledError:
                            logger.info("ℹ️ 컨슈머 태스크가 취소됨")
                        except Exception as e:
                            logger.info(f"❌ 컨슈머 태스크 상태 확인 중 오류: {e}")

                    needs_reconnect = True
                else:
                    logger.debug("💚 헬스체크: 정상 (연결, 채널, 컨슈머 모두 활성)")

                # 재연결이 필요하면 처리
                if needs_reconnect:
                    self._is_connected = False
                    # 기존 재연결 태스크가 없거나 완료되었을 때만 새로 생성
                    if not self._reconnect_task or self._reconnect_task.done():
                        self._reconnect_task = asyncio.create_task(
                            self._handle_reconnect()
                        )

            except Exception as e:
                logger.info(f"❌ 헬스체크 중 오류: {e}")
                self._is_connected = False
                # 기존 재연결 태스크가 없거나 완료되었을 때만 새로 생성
                if not self._reconnect_task or self._reconnect_task.done():
                    self._reconnect_task = asyncio.create_task(self._handle_reconnect())

            # 헬스체크 주기
            await asyncio.sleep(self._health_check_interval)

    async def consume_messages(self):
        """메시지 소비 루프"""
        try:
            if not self._is_connected or not self.queue:
                logger.warning("⚠️ 큐가 준비되지 않았습니다.")
                return

            async with self.queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if self._shutdown:
                        break
                    try:
                        await self.consume_message(message)
                    except Exception as e:
                        logger.error(f"❌ 메시지 처리 중 오류: {e}")
                        # 메시지 처리 실패 시에도 ACK를 보내 무한 재시도 방지
                        await message.ack()

        except (ConnectionClosed, ChannelClosed) as e:
            logger.warning(f"⚠️ 연결/채널 오류로 인한 컨슈머 중단: {e}")
            self._is_connected = False
        except Exception as e:
            logger.error(f"❌ 컨슈머 오류: {e}")
            self._is_connected = False

    async def start(self):
        """컨슈머 시작"""
        try:
            await self.connect()
            self._consumer_task = asyncio.create_task(self.consume_messages())
            self._health_check_task = asyncio.create_task(self.health_check())
            logger.info("✅ RabbitMQ Consumer 및 헬스체크 시작됨")
        except Exception as e:
            logger.error(f"❌ 컨슈머 시작 실패: {e}")
            # 헬스체크 태스크만 시작하여 자동 재연결 시도
            self._health_check_task = asyncio.create_task(self.health_check())

    async def stop(self):
        """컨슈머 종료"""
        logger.info("🛑 RabbitMQ Consumer 종료 중...")
        self._shutdown = True
        self._is_connected = False

        # 태스크 종료
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # 연결 종료
        if self.channel and not self.channel.is_closed:
            await self.channel.close()
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

        logger.info("✅ RabbitMQ Consumer 종료됨")
