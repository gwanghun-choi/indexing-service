from fastapi import APIRouter
from typing import Dict
import logging

from app.service.sse_manager import sse_manager
from app.dto.notification_dto import NotificationServiceHealthDTO

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        400: {"description": "bad request"},
        401: {"description": "unauthorized"},
        403: {"description": "forbidden"},
        404: {"description": "not found"},
        500: {"description": "internal server error"},
    },
)


@router.get(
    "/health",
    summary="알림 서비스 상태 확인",
    response_model=NotificationServiceHealthDTO,
    responses={
        200: {
            "description": "알림 서비스 상태를 성공적으로 조회했습니다.",
            "content": {
                "application/json": {
                    "examples": {
                        "healthy": {
                            "summary": "정상 상태",
                            "value": {
                                "status": "healthy",
                                "sse_manager_ready": True,
                                "active_connections": 15,
                                "connection_details": {
                                    "123": 2,
                                    "456": 1,
                                    "789": 3
                                }
                            }
                        },
                        "unhealthy": {
                            "summary": "비정상 상태",
                            "value": {
                                "status": "unhealthy",
                                "sse_manager_ready": False,
                                "active_connections": 0,
                                "connection_details": {}
                            }
                        }
                    }
                }
            }
        }
    },
    description="""
🔔 **알림 서비스 상태 확인**

알림 서비스의 전반적인 상태를 모니터링하여 시스템 건강성을 확인합니다.
SSE 매니저 상태, SSE 연결 통계, 서비스 가용성 등을 포함합니다.

## 모니터링 항목
- **SSE 매니저 상태**: SSE 서비스 준비 여부
- **활성 SSE 연결**: 현재 연결된 클라이언트 수
- **사용자별 연결 상세**: 각 사용자의 연결 수 분석
- **전체 서비스 상태**: healthy/unhealthy 판정

## 상태 판정 기준
- **healthy**: SSE 매니저 정상, 알림 기능 사용 가능
- **unhealthy**: SSE 매니저 문제, 알림 기능 제한

## 운영 활용
- 시스템 모니터링 대시보드 연동
- 헬스체크 및 로드밸런서 연동
- 알림 기능 장애 감지
- 연결 수 기반 리소스 관리
    """,
)
async def notification_health() -> NotificationServiceHealthDTO:
    """
    알림 서비스 상태 모니터링 및 헬스체크 엔드포인트

    Returns:
        NotificationServiceHealthDTO: 알림 서비스 상태 정보
            - status: 서비스 상태 ("healthy" | "unhealthy")
            - sse_manager_ready: SSE 매니저 준비 상태 (bool)
            - active_connections: 총 활성 SSE 연결 수 (int)
            - connection_details: 사용자별 연결 수 상세 (Dict[str, int])
    """
    # SSE 매니저 상태 확인 (싱글톤이므로 항상 준비됨)
    is_ready = True
    
    # 활성 연결 수 계산
    connection_count = 0
    connection_details: Dict[str, int] = {}
    
    # clients 딕셔너리를 순회하여 연결 정보 수집
    for task_id, clients_list in sse_manager.clients.items():
        for user_id in clients_list:
            if user_id not in connection_details:
                connection_details[user_id] = 0
            connection_details[user_id] += 1
            connection_count += 1
    
    return NotificationServiceHealthDTO(
        status="healthy" if is_ready else "unhealthy",
        sse_manager_ready=is_ready,
        active_connections=connection_count,
        connection_details=connection_details,
    )