from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ActionLogFilterRequestDTO(BaseModel):
    """액션 로그 필터링 요청 DTO"""

    user_id: Optional[int] = Field(None, description="사용자 ID 필터")
    action_type: Optional[str] = Field(
        None,
        description="액션 타입 필터 (READ, CREATE, UPDATE, DELETE, SEARCH, UPLOAD, DOWNLOAD)",
    )
    start_date: Optional[datetime] = Field(None, description="시작 날짜")
    end_date: Optional[datetime] = Field(None, description="종료 날짜")
    success_only: Optional[bool] = Field(
        None, description="성공한 요청만 조회할지 여부"
    )
    page: int = Field(1, ge=1, description="페이지 번호 (1부터 시작)")
    page_size: int = Field(50, ge=1, le=1000, description="페이지 크기 (1-1000)")

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, v):
        if v is not None:
            valid_types = [
                "READ",
                "CREATE",
                "UPDATE",
                "DELETE",
                "SEARCH",
                "UPLOAD",
                "DOWNLOAD",
                "WEBSOCKET",
            ]
            if v not in valid_types:
                raise ValueError(
                    f"유효하지 않은 액션 타입입니다. 사용 가능한 값: {valid_types}"
                )
        return v

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        if v is not None and info.data.get("start_date") is not None:
            if v < info.data["start_date"]:
                raise ValueError("종료 날짜는 시작 날짜보다 이후여야 합니다.")
        return v


class ActionLogResponseDTO(BaseModel):
    """액션 로그 응답 DTO"""

    id: int = Field(..., description="로그 ID")
    user_id: Optional[int] = Field(None, description="사용자 ID")
    group_id: Optional[int] = Field(None, description="그룹 ID")
    role_id: Optional[int] = Field(None, description="사용자 역할 ID (1: admin, 2: manager, 3: user)")
    action_type: str = Field(..., description="액션 타입")
    endpoint: str = Field(..., description="API 엔드포인트")
    http_method: str = Field(..., description="HTTP 메서드")

    # 문서 관련 정보
    document_id: Optional[str] = Field(None, description="문서 ID")
    document_title: Optional[str] = Field(None, description="문서 제목")
    document_category: Optional[str] = Field(None, description="문서 카테고리")
    file_name: Optional[str] = Field(None, description="파일명")
    file_type: Optional[str] = Field(None, description="파일 타입")
    file_size: Optional[int] = Field(None, description="파일 크기")

    # 요청/응답 정보
    action_details: Optional[Dict[str, Any]] = Field(None, description="액션 세부사항")
    request_params: Optional[Dict[str, Any]] = Field(None, description="요청 파라미터")
    changes_made: Optional[Dict[str, Any]] = Field(None, description="변경 사항")

    # 검색 관련 정보
    search_query: Optional[str] = Field(None, description="검색 쿼리")
    search_results_count: Optional[int] = Field(None, description="검색 결과 개수")
    use_reranker: Optional[bool] = Field(None, description="리랭커 사용 여부")

    # 결과 정보
    status_code: int = Field(..., description="HTTP 상태 코드")
    success: str = Field(..., description="성공 여부 (SUCCESS, FAILED, ERROR)")
    error_message: Optional[str] = Field(None, description="오류 메시지")
    error_type: Optional[str] = Field(None, description="오류 타입")

    # 비용 및 성능 정보
    tokens_used: Optional[int] = Field(None, description="사용된 토큰 수")
    cost_incurred: Optional[float] = Field(None, description="발생 비용")
    processing_time_ms: Optional[int] = Field(None, description="처리 시간 (밀리초)")

    # 메타데이터
    ip_address: Optional[str] = Field(None, description="IP 주소")
    user_agent: Optional[str] = Field(None, description="User Agent")
    session_id: Optional[str] = Field(None, description="세션 ID")
    task_id: Optional[str] = Field(None, description="작업 ID")
    request_id: Optional[str] = Field(None, description="요청 ID")

    # 시간 정보
    created_at: datetime = Field(..., description="생성 시간")
    request_start_time: Optional[datetime] = Field(None, description="요청 시작 시간")
    request_end_time: Optional[datetime] = Field(None, description="요청 종료 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 12345,
                "user_id": 1,
                "group_id": 1,
                "role_id": 2,
                "action_type": "SEARCH",
                "endpoint": "/api/v1/embeddings/retrieval",
                "http_method": "POST",
                "document_id": None,
                "document_title": None,
                "document_category": None,
                "file_name": None,
                "file_type": None,
                "file_size": None,
                "action_details": {
                    "query_length": 45,
                    "filters_applied": False
                },
                "request_params": {
                    "use_reranker": True,
                    "rerank_top_k": 5
                },
                "changes_made": None,
                "search_query": "디딤365에서 야근으로 인정받는 시간은?",
                "search_results_count": 5,
                "use_reranker": True,
                "status_code": 200,
                "success": "SUCCESS",
                "error_message": None,
                "error_type": None,
                "tokens_used": 150,
                "cost_incurred": 0.002,
                "processing_time_ms": 235,
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "session_id": "sess_abc123",
                "task_id": None,
                "request_id": "req_xyz789",
                "created_at": "2024-01-15T10:30:00Z",
                "request_start_time": "2024-01-15T10:29:59.765Z",
                "request_end_time": "2024-01-15T10:30:00.000Z"
            }
        }


class ActionLogListResponseDTO(BaseModel):
    """액션 로그 목록 응답 DTO"""

    logs: List[ActionLogResponseDTO] = Field(..., description="액션 로그 목록")
    pagination: Dict[str, Any] = Field(..., description="페이징 정보")
    filters: Dict[str, Any] = Field(..., description="적용된 필터")
    
    class Config:
        json_schema_extra = {
            "example": {
                "logs": [
                    {
                        "id": 12345,
                        "user_id": 1,
                        "action_type": "SEARCH",
                        "endpoint": "/api/v1/embeddings/retrieval",
                        "http_method": "POST",
                        "status_code": 200,
                        "success": "SUCCESS",
                        "processing_time_ms": 235,
                        "created_at": "2024-01-15T10:30:00Z"
                    },
                    {
                        "id": 12344,
                        "user_id": 1,
                        "action_type": "UPLOAD",
                        "endpoint": "/api/v1/embeddings/upload",
                        "http_method": "POST",
                        "status_code": 200,
                        "success": "SUCCESS",
                        "processing_time_ms": 1523,
                        "created_at": "2024-01-15T10:25:00Z"
                    }
                ],
                "pagination": {
                    "page": 1,
                    "page_size": 50,
                    "total_count": 125,
                    "total_pages": 3
                },
                "filters": {
                    "user_id": 1,
                    "action_type": None,
                    "start_date": "2024-01-15T00:00:00Z",
                    "end_date": "2024-01-15T23:59:59Z",
                    "success_only": True
                }
            }
        }


class ActionLogStatisticsRequestDTO(BaseModel):
    """액션 로그 통계 요청 DTO"""

    user_id: Optional[int] = Field(None, description="사용자 ID 필터")
    start_date: Optional[datetime] = Field(None, description="시작 날짜")
    end_date: Optional[datetime] = Field(None, description="종료 날짜")
    group_by: str = Field("action_type", description="그룹화 기준")

    @field_validator("group_by")
    @classmethod
    def validate_group_by(cls, v):
        valid_options = ["action_type", "endpoint", "status_code", "date", "role_id"]
        if v not in valid_options:
            raise ValueError(
                f"유효하지 않은 그룹화 기준입니다. 사용 가능한 값: {valid_options}"
            )
        return v

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        if (
            v is not None
            and "start_date" in info.data
            and info.data["start_date"] is not None
        ):
            if v < info.data["start_date"]:
                raise ValueError("종료 날짜는 시작 날짜보다 이후여야 합니다.")
        return v


class ActionLogStatisticsItemDTO(BaseModel):
    """액션 로그 통계 항목 DTO"""

    group_key: str = Field(..., description="그룹 키")
    total_count: int = Field(..., description="총 요청 수")
    success_count: int = Field(..., description="성공 요청 수")
    error_count: int = Field(..., description="오류 요청 수")
    success_rate: float = Field(..., description="성공률 (%)")
    avg_processing_time: float = Field(..., description="평균 처리 시간 (ms)")
    total_tokens: int = Field(..., description="총 토큰 사용량")


class ActionLogStatisticsResponseDTO(BaseModel):
    """액션 로그 통계 응답 DTO"""

    statistics: List[ActionLogStatisticsItemDTO] = Field(..., description="통계 데이터")
    summary: Dict[str, Any] = Field(..., description="전체 요약")
    
    class Config:
        json_schema_extra = {
            "example": {
                "statistics": [
                    {
                        "group_key": "SEARCH",
                        "total_count": 250,
                        "success_count": 245,
                        "error_count": 5,
                        "success_rate": 98.0,
                        "avg_processing_time": 180.5,
                        "total_tokens": 37500
                    },
                    {
                        "group_key": "UPLOAD",
                        "total_count": 50,
                        "success_count": 48,
                        "error_count": 2,
                        "success_rate": 96.0,
                        "avg_processing_time": 2500.3,
                        "total_tokens": 125000
                    }
                ],
                "summary": {
                    "total_requests": 300,
                    "total_success": 293,
                    "total_errors": 7,
                    "overall_success_rate": 97.67,
                    "period": "2024-01-01 ~ 2024-01-15"
                }
            }
        }


class UserActivitySummaryRequestDTO(BaseModel):
    """사용자 활동 요약 요청 DTO"""

    user_id: int = Field(..., ge=1, description="사용자 ID")
    days: int = Field(30, ge=1, le=365, description="조회할 일수 (1-365일)")


class UserActivityBreakdownDTO(BaseModel):
    """사용자 활동 분석 DTO"""

    action_type: str = Field(..., description="액션 타입")
    count: int = Field(..., description="횟수")


class RecentActivityDTO(BaseModel):
    """최근 활동 DTO"""

    action_type: str = Field(..., description="액션 타입")
    endpoint: str = Field(..., description="엔드포인트")
    success: str = Field(..., description="성공 여부")
    created_at: datetime = Field(..., description="생성 시간")


class UserActivitySummaryResponseDTO(BaseModel):
    """사용자 활동 요약 응답 DTO"""

    user_id: int = Field(..., description="사용자 ID")
    period_days: int = Field(..., description="조회 기간 (일)")
    total_requests: int = Field(..., description="총 요청 수")
    successful_requests: int = Field(..., description="성공 요청 수")
    success_rate: float = Field(..., description="성공률 (%)")
    total_tokens_used: int = Field(..., description="총 토큰 사용량")
    avg_response_time_ms: float = Field(..., description="평균 응답 시간 (ms)")
    unique_sessions: int = Field(..., description="고유 세션 수")
    activity_score: int = Field(..., description="활동 점수 (0-100)")
    action_breakdown: List[UserActivityBreakdownDTO] = Field(
        ..., description="액션 타입별 분석"
    )
    recent_activities: List[RecentActivityDTO] = Field(..., description="최근 활동")


class SystemHealthMetricsRequestDTO(BaseModel):
    """시스템 건강 상태 메트릭 요청 DTO"""

    hours: int = Field(24, ge=1, le=168, description="조회할 시간 (1-168시간)")


class SystemAlertDTO(BaseModel):
    """시스템 알림 DTO"""

    type: str = Field(..., description="알림 타입")
    severity: str = Field(..., description="심각도 (HIGH, MEDIUM, LOW)")
    message: str = Field(..., description="알림 메시지")
    details: Dict[str, Any] = Field(..., description="상세 정보")


class SystemHealthMetricsResponseDTO(BaseModel):
    """시스템 건강 상태 메트릭 응답 DTO"""

    period_hours: int = Field(..., description="조회 기간 (시간)")
    health_score: int = Field(..., description="건강 상태 점수 (0-100)")
    overall_statistics: List[ActionLogStatisticsItemDTO] = Field(
        ..., description="전체 통계"
    )
    endpoint_statistics: List[ActionLogStatisticsItemDTO] = Field(
        ..., description="엔드포인트별 통계"
    )
    hourly_statistics: List[ActionLogStatisticsItemDTO] = Field(
        ..., description="시간별 통계"
    )
    alerts: List[SystemAlertDTO] = Field(..., description="시스템 알림")
    generated_at: datetime = Field(..., description="생성 시간")


class LogCleanupRequestDTO(BaseModel):
    """로그 정리 요청 DTO"""

    days_to_keep: int = Field(90, ge=7, description="보관할 일수 (최소 7일)")


class LogCleanupResponseDTO(BaseModel):
    """로그 정리 응답 DTO"""

    deleted_count: int = Field(..., description="삭제된 로그 개수")
    days_kept: int = Field(..., description="보관 일수")
    cleanup_date: datetime = Field(..., description="정리 실행 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "deleted_count": 1523,
                "days_kept": 90,
                "cleanup_date": "2024-01-15T03:00:00Z"
            }
        }
