from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class TaskNotificationDTO(BaseModel):
    """
    작업 알림에 대한 DTO. SSE 메시지 구조를 정의합니다.
    """

    task_id: str = Field(..., description="Celery 작업 ID")
    user_id: str = Field(..., description="사용자 ID (문자열)")
    status: str = Field(..., description="작업 상태 (SUCCESS, FAILED, PROCESSING 등)")
    message: str = Field(..., description="상태 메시지")
    completed_at: str = Field(..., description="ISO8601 형식의 완료 시간")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="추가 메타데이터"
    )


class NotificationServiceHealthDTO(BaseModel):
    """
    알림 서비스 상태 응답 DTO
    """

    status: str = Field(..., description="서비스 상태 (healthy, unhealthy)")
    sse_manager_ready: bool = Field(..., description="SSE 매니저 준비 상태")
    active_connections: int = Field(..., description="활성화된 SSE 연결 수")
    connection_details: Optional[Dict[str, int]] = Field(
        None, description="사용자별 연결 상세 정보"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "sse_manager_ready": True,
                "active_connections": 15,
                "connection_details": {
                    "123": 2,
                    "456": 1,
                    "789": 3
                }
            }
        }


class SearchRequestStatusDTO(BaseModel):
    """
    검색 요청의 상태를 추적하기 위한 DTO
    """

    request_id: str = Field(..., description="고유 검색 요청 ID")
    user_id: str = Field(..., description="사용자 ID")
    query: str = Field(..., description="검색 쿼리")
    status: str = Field(
        ..., description="요청 상태 (STARTED, PROCESSING, COMPLETED, FAILED)"
    )
    start_time: str = Field(..., description="요청 시작 시간 (ISO8601 형식)")
    end_time: Optional[str] = Field(None, description="요청 종료 시간 (ISO8601 형식)")
    error_message: Optional[str] = Field(None, description="오류 메시지 (실패 시)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="추가 메타데이터 (검색 매개변수, 결과 요약 등)",
    )