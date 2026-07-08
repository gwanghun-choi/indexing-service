"""
임베딩 스케줄 DTO

임베딩 자동 실행 스케줄 관리를 위한 Data Transfer Objects를 정의합니다.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ========================================
# Request DTOs
# ========================================


class CreateScheduleRequestDTO(BaseModel):
    """
    스케줄 생성 요청 DTO

    사용자가 선택한 문서들을 특정 시간에 자동으로 임베딩 처리하도록 예약합니다.
    """

    name: Optional[str] = Field(
        default=None,
        description="스케줄 이름 (미입력 시 시스템 자동 생성: '날짜 시간 임베딩 예약 (문서 N개)')",
        max_length=255,
        example="주말 보고서 자동 임베딩",
    )

    description: Optional[str] = Field(
        default=None,
        description="스케줄 설명 (선택사항)",
        example="매주 일요일 저녁에 주간 보고서를 자동으로 임베딩 처리합니다.",
    )

    document_hashes: List[str] = Field(
        ...,
        description="임베딩할 문서의 hash_sha256 리스트",
        min_length=1,
        example=[
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",
        ],
    )

    scheduled_at: datetime = Field(
        ...,
        description="예약 실행 시간 (ISO 8601 형식)",
        example="2025-11-01T14:00:00",
    )

    cron_expression: Optional[str] = Field(
        default=None,
        description="반복 스케줄용 Cron 표현식 (선택사항, 예: '0 2 * * *' = 매일 새벽 2시)",
        max_length=100,
        example="0 2 * * *",
    )

    timezone: str = Field(
        default="Asia/Seoul",
        description="시간대",
        example="Asia/Seoul",
    )

    # 청킹 설정 (신규)
    chunking: Optional[Dict[str, Any]] = Field(
        default=None,
        description="청킹 설정. strategy='fixed' 또는 'semantic' 선택",
        example={
            "strategy": "semantic",
            "similarity_threshold": 0.5,
            "max_chunk_size": 1500,
        },
    )

    # 하위 호환성을 위한 기존 필드 (Optional로 변경)
    chunk_size: Optional[int] = Field(
        default=None,
        description="[하위 호환] 청크 크기 (chunking 미사용 시)",
        ge=100,
        le=2000,
        example=500,
    )

    chunk_overlap: Optional[int] = Field(
        default=None,
        description="[하위 호환] 청크 오버랩 크기 (chunking 미사용 시)",
        ge=0,
        le=500,
        example=50,
    )

    enable_pii_anonymization: bool = Field(
        default=False,
        description="개인정보 비식별화 활성화 여부",
        example=False,
    )

    pii_strategy: Optional[str] = Field(
        default=None,
        description="개인정보 비식별화 전략 (masking, pseudonymization, generalization)",
        example="masking",
    )

    pii_types: Optional[List[str]] = Field(
        default=None,
        description="비식별화할 개인정보 유형 리스트",
        example=["이름", "전화번호", "주민등록번호"],
    )

    persona_id: int = Field(
        default=0,
        description="페르소나 ID (0이면 필터링 안함)",
        ge=0,
        example=0,
    )

    filter_score: Optional[float] = Field(
        default=None,
        description="필터링 점수 (0.0 ~ 1.0)",
        ge=0.0,
        le=1.0,
        example=0.7,
    )

    @field_validator("document_hashes")
    @classmethod
    def validate_document_hashes(cls, v):
        """문서 해시 리스트 검증"""
        if not v:
            raise ValueError("document_hashes는 최소 1개 이상이어야 합니다.")

        # 중복 제거
        unique_hashes = list(set(v))
        if len(unique_hashes) != len(v):
            raise ValueError("document_hashes에 중복된 값이 있습니다.")

        # 각 해시값 길이 검증
        for hash_value in v:
            if not hash_value or not isinstance(hash_value, str):
                raise ValueError("hash_sha256 값은 빈 문자열이 아니어야 합니다.")
            if len(hash_value) != 64:
                raise ValueError(
                    f"hash_sha256 값은 64자여야 합니다. (입력값: {len(hash_value)}자)"
                )

        return v

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, v):
        """예약 시간 검증"""
        if v <= datetime.now():
            raise ValueError("예약 시간은 현재 시간보다 미래여야 합니다.")
        return v

    @model_validator(mode="after")
    def validate_chunking_config(self):
        """chunking 또는 chunk_size/chunk_overlap 중 하나는 필수"""
        if self.chunking is None:
            # chunking이 없으면 기본값 적용
            if self.chunk_size is None:
                self.chunk_size = 500
            if self.chunk_overlap is None:
                self.chunk_overlap = 50
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "name": "주말 보고서 자동 임베딩",
                "description": "매주 일요일 저녁에 주간 보고서를 자동으로 임베딩 처리",
                "document_hashes": [
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",
                ],
                "scheduled_at": "2025-11-03T20:00:00",
                "cron_expression": "0 20 * * 0",
                "timezone": "Asia/Seoul",
                "chunking": {
                    "strategy": "semantic",
                    "similarity_threshold": 0.5,
                    "max_chunk_size": 1500,
                },
                "enable_pii_anonymization": False,
            }
        }


class UpdateScheduleRequestDTO(BaseModel):
    """
    스케줄 수정 요청 DTO

    기존 스케줄의 예약 시간, 임베딩 옵션, 문서 목록 등을 수정합니다.
    """

    name: Optional[str] = Field(
        default=None,
        description="스케줄 이름",
        max_length=255,
        example="수정된 스케줄 이름",
    )

    description: Optional[str] = Field(
        default=None,
        description="스케줄 설명",
        example="수정된 설명",
    )

    document_hashes: Optional[List[str]] = Field(
        default=None,
        description="임베딩할 문서의 hash_sha256 리스트",
        min_length=1,
    )

    scheduled_at: Optional[datetime] = Field(
        default=None,
        description="예약 실행 시간",
        example="2025-11-01T15:00:00",
    )

    cron_expression: Optional[str] = Field(
        default=None,
        description="반복 스케줄용 Cron 표현식",
    )

    timezone: Optional[str] = Field(
        default=None,
        description="시간대",
    )

    # 청킹 설정 (신규)
    chunking: Optional[Dict[str, Any]] = Field(
        default=None,
        description="청킹 설정. strategy='fixed' 또는 'semantic' 선택",
    )

    # 하위 호환성을 위한 기존 필드
    chunk_size: Optional[int] = Field(
        default=None,
        description="[하위 호환] 청크 크기",
        ge=100,
        le=2000,
    )

    chunk_overlap: Optional[int] = Field(
        default=None,
        description="[하위 호환] 청크 오버랩 크기",
        ge=0,
        le=500,
    )

    enable_pii_anonymization: Optional[bool] = Field(
        default=None,
        description="개인정보 비식별화 활성화 여부",
    )

    is_active: Optional[bool] = Field(
        default=None,
        description="활성화 여부",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scheduled_at": "2025-11-01T15:00:00",
                "chunking": {
                    "strategy": "fixed",
                    "chunk_size": 600,
                    "chunk_overlap": 60,
                },
                "is_active": True,
            }
        }


# ========================================
# Response DTOs
# ========================================


class ScheduleResponseDTO(BaseModel):
    """
    스케줄 응답 DTO

    스케줄 정보를 반환합니다.
    """

    id: int = Field(..., description="스케줄 ID", example=1)

    name: Optional[str] = Field(
        None,
        description="스케줄 이름",
        example="2025-10-31 14:00 임베딩 예약 (문서 5개)",
    )

    description: Optional[str] = Field(
        None,
        description="스케줄 설명",
    )

    user_id: int = Field(..., description="생성자 사용자 ID", example=1)

    group_id: int = Field(..., description="그룹 ID", example=1)

    role_ids: List[int] = Field(
        ...,
        description="역할 ID 리스트 (스케줄 생성자의 권한)",
        example=[1, 2, 3],
    )

    document_hashes: List[str] = Field(
        ...,
        description="임베딩할 문서 해시 리스트",
        example=["abc123...", "def456..."],
    )

    document_count: int = Field(
        ...,
        description="문서 개수",
        example=5,
    )

    scheduled_at: datetime = Field(
        ...,
        description="예약 실행 시간",
        example="2025-11-01T14:00:00+09:00",
    )

    cron_expression: Optional[str] = Field(
        None,
        description="반복 스케줄용 Cron 표현식",
        example="0 2 * * *",
    )

    timezone: str = Field(
        ...,
        description="시간대",
        example="Asia/Seoul",
    )

    is_active: bool = Field(
        ...,
        description="활성화 여부",
        example=True,
    )

    embedding_config: Dict[str, Any] = Field(
        ...,
        description="임베딩 설정 (chunking 객체 또는 chunk_size/chunk_overlap)",
        example={
            "chunking": {
                "strategy": "semantic",
                "similarity_threshold": 0.5,
                "max_chunk_size": 1500,
            },
            "enable_pii_anonymization": False,
        },
    )

    # 실행 통계
    last_executed_at: Optional[datetime] = Field(
        None,
        description="마지막 실행 시간",
    )

    total_executions: int = Field(
        default=0,
        description="총 실행 횟수",
        example=10,
    )

    successful_executions: int = Field(
        default=0,
        description="성공한 실행 횟수",
        example=9,
    )

    failed_executions: int = Field(
        default=0,
        description="실패한 실행 횟수",
        example=1,
    )

    created_at: datetime = Field(
        ...,
        description="생성 시간",
        example="2025-10-30T10:00:00+09:00",
    )

    updated_at: datetime = Field(
        ...,
        description="수정 시간",
        example="2025-10-30T10:00:00+09:00",
    )

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "2025-10-31 14:00 임베딩 예약 (문서 5개)",
                "description": "주간 보고서 자동 임베딩",
                "user_id": 1,
                "group_id": 1,
                "document_hashes": [
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                ],
                "document_count": 5,
                "scheduled_at": "2025-11-01T14:00:00+09:00",
                "cron_expression": None,
                "timezone": "Asia/Seoul",
                "is_active": True,
                "embedding_config": {
                    "chunking": {
                        "strategy": "semantic",
                        "similarity_threshold": 0.5,
                        "max_chunk_size": 1500,
                    },
                    "enable_pii_anonymization": False,
                },
                "last_executed_at": None,
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "created_at": "2025-10-30T10:00:00+09:00",
                "updated_at": "2025-10-30T10:00:00+09:00",
            }
        }


class ScheduleListResponseDTO(BaseModel):
    """
    스케줄 목록 응답 DTO

    스케줄 목록을 페이지네이션과 함께 반환합니다.
    """

    total: int = Field(..., description="전체 스케줄 개수", example=25)

    page: int = Field(..., description="현재 페이지", example=1)

    per_page: int = Field(..., description="페이지당 항목 수", example=20)

    items: List[ScheduleResponseDTO] = Field(
        ...,
        description="스케줄 목록",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total": 25,
                "page": 1,
                "per_page": 20,
                "items": [
                    {
                        "id": 1,
                        "name": "2025-10-31 14:00 임베딩 예약 (문서 5개)",
                        "scheduled_at": "2025-11-01T14:00:00+09:00",
                        "is_active": True,
                        "total_executions": 10,
                    }
                ],
            }
        }


class ExecutionHistoryResponseDTO(BaseModel):
    """
    실행 이력 응답 DTO

    스케줄 실행 이력을 반환합니다.
    """

    id: int = Field(..., description="실행 이력 ID", example=123)

    schedule_id: int = Field(..., description="스케줄 ID", example=1)

    execution_time: datetime = Field(
        ...,
        description="실행 시간",
        example="2025-10-30T14:00:00+09:00",
    )

    status: str = Field(
        ...,
        description="실행 상태 (running, success, failed, cancelled)",
        example="success",
    )

    documents_processed: int = Field(
        ...,
        description="처리된 문서 수",
        example=25,
    )

    documents_success: int = Field(
        ...,
        description="성공한 문서 수",
        example=24,
    )

    documents_failed: int = Field(
        ...,
        description="실패한 문서 수",
        example=1,
    )

    task_ids: Optional[List[str]] = Field(
        None,
        description="Celery 태스크 ID 목록",
        example=["uuid1", "uuid2"],
    )

    started_at: Optional[datetime] = Field(
        None,
        description="시작 시간",
    )

    completed_at: Optional[datetime] = Field(
        None,
        description="완료 시간",
    )

    duration_seconds: Optional[int] = Field(
        None,
        description="실행 소요 시간(초)",
        example=42,
    )

    error_message: Optional[str] = Field(
        None,
        description="에러 메시지",
    )

    created_at: datetime = Field(
        ...,
        description="레코드 생성 시간",
    )

    class Config:
        from_attributes = True


class ExecuteScheduleResponseDTO(BaseModel):
    """
    스케줄 즉시 실행 응답 DTO

    스케줄을 즉시 실행한 결과를 반환합니다.
    """

    execution_id: int = Field(
        ...,
        description="실행 이력 ID",
        example=123,
    )

    status: str = Field(
        ...,
        description="실행 상태",
        example="running",
    )

    message: str = Field(
        ...,
        description="결과 메시지",
        example="스케줄이 실행 중입니다.",
    )

    task_ids: List[str] = Field(
        ...,
        description="Celery 태스크 ID 목록",
        example=["uuid1", "uuid2"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "execution_id": 123,
                "status": "running",
                "message": "5개 문서에 대한 임베딩이 시작되었습니다.",
                "task_ids": [
                    "550e8400-e29b-41d4-a716-446655440000",
                    "550e8400-e29b-41d4-a716-446655440001",
                ],
            }
        }


class DeleteScheduleRequestDTO(BaseModel):
    """
    스케줄 삭제 요청 DTO

    단일 또는 다중 스케줄을 삭제합니다.
    """

    schedule_ids: List[int] = Field(
        ...,
        description="삭제할 스케줄 ID 리스트 (단일 또는 다중)",
        min_length=1,
        example=[1, 2, 3],
    )

    @field_validator("schedule_ids")
    @classmethod
    def validate_schedule_ids(cls, v):
        """스케줄 ID 리스트 검증"""
        if not v:
            raise ValueError("schedule_ids는 최소 1개 이상이어야 합니다.")

        # 중복 제거
        unique_ids = list(set(v))
        if len(unique_ids) != len(v):
            raise ValueError("schedule_ids에 중복된 값이 있습니다.")

        # 각 ID 검증
        for schedule_id in v:
            if schedule_id <= 0:
                raise ValueError(f"유효하지 않은 스케줄 ID입니다: {schedule_id}")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "schedule_ids": [1, 2, 3],
            }
        }


class DeleteScheduleResponseDTO(BaseModel):
    """
    스케줄 삭제 응답 DTO

    삭제 결과를 반환합니다.
    """

    total_requested: int = Field(
        ...,
        description="요청된 전체 스케줄 수",
        example=3,
    )

    deleted_count: int = Field(
        ...,
        description="성공적으로 삭제된 스케줄 수",
        example=3,
    )

    failed_count: int = Field(
        ...,
        description="삭제 실패한 스케줄 수",
        example=0,
    )

    deleted_ids: List[int] = Field(
        ...,
        description="삭제된 스케줄 ID 리스트",
        example=[1, 2, 3],
    )

    failed_ids: List[int] = Field(
        default_factory=list,
        description="삭제 실패한 스케줄 ID 리스트 (권한 없음 또는 존재하지 않음)",
        example=[],
    )

    message: str = Field(
        ...,
        description="결과 메시지",
        example="3개의 스케줄이 성공적으로 삭제되었습니다.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_requested": 3,
                "deleted_count": 3,
                "failed_count": 0,
                "deleted_ids": [1, 2, 3],
                "failed_ids": [],
                "message": "3개의 스케줄이 성공적으로 삭제되었습니다.",
            }
        }


class MessageResponseDTO(BaseModel):
    """
    일반 메시지 응답 DTO

    단순 성공/실패 메시지를 반환합니다.
    """

    message: str = Field(
        ...,
        description="응답 메시지",
        example="스케줄이 성공적으로 삭제되었습니다.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "스케줄이 성공적으로 삭제되었습니다.",
            }
        }
