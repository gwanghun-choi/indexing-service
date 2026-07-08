import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.service.redis_sse_broker import async_debug_redis_keys, async_task_exists
from app.service.sse_manager import SSEManager, get_sse_manager
from app.utils.auth_utils import get_parsed_jwt_data

logger = logging.getLogger(__name__)

router = APIRouter()


# NOTE: 라우팅 순서: batch/{category} → batch → {task_id}
# FastAPI는 라우트를 정의 순서대로 매칭하므로, 구체적인 경로가 먼저 와야 함
@router.get(
    "/pipeline/batch/{category}",
    responses={
        200: {
            "description": "카테고리별 task 진행상황 스트리밍",
        }
    },
)
async def stream_category_progress(
    category: str,
    sse_mgr: SSEManager = Depends(get_sse_manager),
    jwt_data: dict = Depends(get_parsed_jwt_data),
):
    """
    특정 카테고리의 임베딩 작업 진행상황을 SSE로 스트리밍

    카테고리별 서버 사이드 필터링을 통해 해당 카테고리의 task 이벤트만 전달합니다.

    Args:
        category: 문서 카테고리
        sse_mgr: SSE Manager (자동 주입)
        jwt_data: JWT 인증 정보 (자동 주입)

    Returns:
        StreamingResponse: 카테고리별 task 이벤트를 포함한 SSE 스트림

    Example:
        GET /sse/pipeline/batch/계약서
    """
    user_id = str(jwt_data["user_id"])

    logger.info(
        f"[SSE-API-CATEGORY] ✅ 카테고리 SSE 요청: user_id={user_id}, category={category}"
    )

    async def event_generator():
        """SSE 이벤트 generator - 카테고리별 task 스트림"""
        event_count = 0
        try:
            logger.info(
                f"[SSE-API-CATEGORY] 🔌 SSE generator 시작: "
                f"user_id={user_id}, category={category}"
            )

            yield f": SSE category connection established for user {user_id}, category {category}\n\n"

            logger.info("[SSE-API-CATEGORY] 📂 SSE Manager 카테고리 연결 시작")

            async for event in sse_mgr.connect_category(user_id, category):
                event_count += 1
                if event_count % 10 == 0:
                    logger.info(
                        f"[SSE-API-CATEGORY] 이벤트 #{event_count} 전송 중: "
                        f"user_id={user_id}, category={category}"
                    )
                yield event

            logger.info(
                f"[SSE-API-CATEGORY] ✅ SSE 스트림 정상 완료: user_id={user_id}, "
                f"category={category}, 총 {event_count}개 이벤트 전송"
            )

        except asyncio.CancelledError:
            logger.info(
                f"[SSE-API-CATEGORY] 📤 클라이언트 연결 종료: user_id={user_id}, "
                f"category={category}, 전송된 이벤트: {event_count}개"
            )
        except GeneratorExit:
            logger.info(
                f"[SSE-API-CATEGORY] 📤 Generator 정상 종료: user_id={user_id}, "
                f"category={category}"
            )
        except Exception as e:
            logger.error(
                f"[SSE-API-CATEGORY] ❌ SSE 스트림 오류: user_id={user_id}, "
                f"category={category}, error={e}"
            )
        finally:
            logger.info(
                f"[SSE-API-CATEGORY] 🔚 SSE generator 종료: user_id={user_id}, "
                f"category={category}"
            )

    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "X-Content-Type-Options": "nosniff",
            "Transfer-Encoding": "chunked",
        },
    )

    return response


@router.get(
    "/pipeline/batch",
    responses={
        200: {
            "description": "사용자의 모든 task 진행상황 스트리밍",
        }
    },
)
async def stream_batch_progress(
    sse_mgr: SSEManager = Depends(get_sse_manager),
    jwt_data: dict = Depends(get_parsed_jwt_data),
):
    """
    사용자의 모든 임베딩 작업 진행상황을 단일 SSE로 스트리밍

    HTTP/1.1 SSE 연결 제한(6개) 문제를 해결하기 위한 멀티플렉싱 채널입니다.
    모든 task 이벤트에 task_id가 포함되어 클라이언트에서 구분할 수 있습니다.

    **새로고침 시 상태 동기화**:
    - 서버에서 실행 중인 task 목록을 자동으로 조회하여 초기 상태에 포함합니다.
    - 클라이언트가 별도로 task_ids를 전달할 필요가 없습니다.

    Args:
        sse_mgr: SSE Manager (자동 주입)
        jwt_data: JWT 인증 정보 (자동 주입)

    Returns:
        StreamingResponse: 모든 task 이벤트를 포함한 SSE 스트림

    Example:
        GET /sse/pipeline/batch
    """
    user_id = str(jwt_data["user_id"])
    group_id = jwt_data["group_id"]

    logger.info(f"[SSE-API-BATCH] ✅ 배치 SSE 요청: user_id={user_id}")

    async def event_generator():
        """SSE 이벤트 generator - 사용자의 모든 task 스트림"""
        event_count = 0
        try:
            logger.info(
                f"[SSE-API-BATCH] 🔌 SSE generator 시작: user_id={user_id}"
            )

            yield f": SSE batch connection established for user {user_id}\n\n"

            logger.info("[SSE-API-BATCH] 📦 SSE Manager 배치 연결 시작")

            async for event in sse_mgr.connect_batch(user_id, group_id):
                event_count += 1
                if event_count % 10 == 0:
                    logger.info(
                        f"[SSE-API-BATCH] 이벤트 #{event_count} 전송 중: user_id={user_id}"
                    )
                yield event

            logger.info(
                f"[SSE-API-BATCH] ✅ SSE 스트림 정상 완료: user_id={user_id}, "
                f"총 {event_count}개 이벤트 전송"
            )

        except asyncio.CancelledError:
            logger.info(
                f"[SSE-API-BATCH] 📤 클라이언트 연결 종료: user_id={user_id}, "
                f"전송된 이벤트: {event_count}개"
            )
        except GeneratorExit:
            logger.info(
                f"[SSE-API-BATCH] 📤 Generator 정상 종료: user_id={user_id}"
            )
        except Exception as e:
            logger.error(
                f"[SSE-API-BATCH] ❌ SSE 스트림 오류: user_id={user_id}, error={e}"
            )
        finally:
            logger.info(
                f"[SSE-API-BATCH] 🔚 SSE generator 종료: user_id={user_id}"
            )

    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "X-Content-Type-Options": "nosniff",
            "Transfer-Encoding": "chunked",
        },
    )

    return response


@router.get(
    "/pipeline/{task_id}",
    responses={
        404: {
            "description": "유효하지 않은 task_id",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Task not found: 550e8400-e29b-41d4-a716-446655440000. Please check if the task_id is correct and the task has been started."
                    }
                }
            },
        }
    },
)
async def stream_pipeline_progress(
    task_id: str, sse_mgr: SSEManager = Depends(get_sse_manager)
):
    """
    임베딩 파이프라인 진행 상태를 SSE로 스트리밍.

    Args:
        task_id: 작업 ID (UUID)
        sse_mgr: SSE Manager (자동 주입)

    Returns:
        StreamingResponse: SSE 스트림

    Raises:
        HTTPException: 404 - 유효하지 않은 task_id
    """
    logger.info(f"[SSE-API] ✅ SSE stream requested: task={task_id}")

    # task_id 유효성 검증 (비동기 래퍼 사용 - Event Loop 블로킹 방지)
    logger.info(f"[SSE-API-VALIDATION] task_exists 호출 전: task_id={task_id}")

    task_exists_result = await async_task_exists(task_id)
    logger.info(f"[SSE-API-VALIDATION] task_exists 결과: {task_exists_result}")

    if not task_exists_result:
        logger.warning(
            f"[SSE-API-VALIDATION] ⚠️ 유효하지 않은 task_id로 SSE 요청: {task_id}"
        )
        # Redis 키 디버깅 정보 조회
        try:
            state_exists, owner_exists, state_ttl = await async_debug_redis_keys(task_id)
            logger.warning(
                f"[SSE-API-VALIDATION] Redis 키 확인: "
                f"state_exists={state_exists}, owner_exists={owner_exists}, ttl={state_ttl}"
            )
        except Exception as e:
            logger.error(f"[SSE-API-VALIDATION] Redis 디버깅 실패: {e}")

        logger.warning(f"⚠️ 유효하지 않은 task_id로 SSE 요청: {task_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Task not found: {task_id}. Please check if the task_id is correct and the task has been started.",
        )

    logger.info(f"[SSE-API] ✅ 유효한 task_id 확인됨: {task_id}")

    async def event_generator():
        """SSE 이벤트 generator - task_id별 독립 실행"""
        try:
            logger.info(f"[SSE-API] 🔌 SSE generator 시작: task={task_id}")

            # 초기 연결 확인 메시지
            yield f": SSE connection established for task {task_id}\n\n"

            logger.info(f"[SSE-API] 📊 SSE Manager 연결 시작: task={task_id}")
            event_count = 0

            # SSE Manager에서 이벤트 스트림 수신
            async for event in sse_mgr.connect(task_id):
                # 이벤트 전송
                event_count += 1
                if event_count % 10 == 0:  # 매 10번째 이벤트마다 로그
                    logger.info(
                        f"[SSE-API] 이벤트 #{event_count} 전송 중: task={task_id}"
                    )
                yield event

            logger.info(
                f"[SSE-API] ✅ SSE 스트림 정상 완료: task={task_id}, 총 {event_count}개 이벤트 전송"
            )

        except asyncio.CancelledError:
            # 클라이언트가 연결을 끊은 경우 (정상 종료)
            logger.info(
                f"[SSE-API] 📤 클라이언트 연결 종료: task={task_id}, 전송된 이벤트: {event_count}개"
            )
        except GeneratorExit:
            # Generator가 정상 종료된 경우
            logger.info(f"[SSE-API] 📤 Generator 정상 종료: task={task_id}")
        except Exception as e:
            logger.error(f"[SSE-API] ❌ SSE 스트림 오류: task={task_id}, error={e}")
        finally:
            logger.info(f"[SSE-API] 🔚 SSE generator 종료: task={task_id}")

    # SSE 스트림 반환
    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
            "Access-Control-Allow-Origin": "*",  # CORS 허용
            "Access-Control-Allow-Credentials": "true",
            "X-Content-Type-Options": "nosniff",
            "Transfer-Encoding": "chunked",
        },
    )

    return response


@router.get(
    "/notifications",
    responses={
        200: {
            "description": "사용자 알림 스트리밍",
        }
    },
)
async def stream_user_notifications(
    sse_mgr: SSEManager = Depends(get_sse_manager),
    jwt_data: dict = Depends(get_parsed_jwt_data),
):
    """
    사용자 레벨 알림 스트리밍 (스케줄 실행 알림 등)

    Args:
        sse_mgr: SSE Manager (자동 주입)
        jwt_data: JWT 인증 정보 (자동 주입)

    Returns:
        StreamingResponse: SSE 스트림
    """
    # JWT에서 user_id, group_id 추출
    user_id = str(jwt_data["user_id"])
    group_id = jwt_data["group_id"]

    logger.info(f"[SSE-API-NOTIFICATIONS] ✅ 사용자 알림 채널 요청: user_id={user_id}")

    async def event_generator():
        """SSE 이벤트 generator - 사용자별 알림 스트림"""
        try:
            logger.info(
                f"[SSE-API-NOTIFICATIONS] 🔌 SSE generator 시작: user_id={user_id}"
            )

            # 초기 연결 확인 메시지
            yield f": SSE connection established for user {user_id}\n\n"

            logger.info("[SSE-API-NOTIFICATIONS] 📊 SSE Manager 연결 시작")
            event_count = 0

            # SSE Manager에서 이벤트 스트림 수신
            async for event in sse_mgr.connect_user(user_id, group_id):
                # 이벤트 전송
                event_count += 1
                if event_count % 10 == 0:  # 매 10번째 이벤트마다 로그
                    logger.info(
                        f"[SSE-API-NOTIFICATIONS] 이벤트 #{event_count} 전송 중: user_id={user_id}"
                    )
                yield event

            logger.info(
                f"[SSE-API-NOTIFICATIONS] ✅ SSE 스트림 정상 완료: user_id={user_id}, "
                f"총 {event_count}개 이벤트 전송"
            )

        except asyncio.CancelledError:
            # 클라이언트가 연결을 끊은 경우 (정상 종료)
            logger.info(
                f"[SSE-API-NOTIFICATIONS] 📤 클라이언트 연결 종료: user_id={user_id}, "
                f"전송된 이벤트: {event_count}개"
            )
        except GeneratorExit:
            # Generator가 정상 종료된 경우
            logger.info(
                f"[SSE-API-NOTIFICATIONS] 📤 Generator 정상 종료: user_id={user_id}"
            )
        except Exception as e:
            logger.error(
                f"[SSE-API-NOTIFICATIONS] ❌ SSE 스트림 오류: user_id={user_id}, error={e}"
            )
        finally:
            logger.info(
                f"[SSE-API-NOTIFICATIONS] 🔚 SSE generator 종료: user_id={user_id}"
            )

    # SSE 스트림 반환
    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "X-Content-Type-Options": "nosniff",
            "Transfer-Encoding": "chunked",
        },
    )

    return response


@router.get("/health")
async def sse_health_check(sse_mgr: SSEManager = Depends(get_sse_manager)):
    """
    SSE 서비스 상태 확인.

    Args:
        sse_mgr: SSE Manager (자동 주입)

    Returns:
        dict: 서비스 상태 정보
    """
    if sse_mgr:
        active_connections = len(sse_mgr.active_connections)
        return {"status": "healthy", "active_connections": active_connections}
    else:
        return {"status": "unhealthy", "active_connections": 0}
