"""
파서 설정 DTO

외부 문서 파서 설정 관리를 위한 Data Transfer Objects를 정의합니다.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ========================================
# Request DTOs
# ========================================


class CreateParserConfigRequestDTO(BaseModel):
    """
    파서 설정 생성 요청 DTO

    관리자가 새로운 외부 문서 파서 설정을 등록합니다.
    """

    parser_name: str = Field(
        ...,
        description="파서 식별자 (영문, 숫자, 언더스코어만 허용)",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_]*$",
        example="ktc_parser",
    )

    display_name: str = Field(
        ...,
        description="표시 이름",
        min_length=1,
        max_length=100,
        example="KT Cloud Document Parser",
    )

    api_endpoint: str = Field(
        ...,
        description="API 엔드포인트 URL",
        min_length=1,
        example="https://api.ktcloud.com/document-parse",
    )

    api_key: str = Field(
        ...,
        description="API 인증 키",
        min_length=1,
        example="your-api-key-here",
    )

    is_active: bool = Field(
        default=True,
        description="활성화 여부",
        example=True,
    )

    timeout_seconds: int = Field(
        default=300,
        description="API 호출 타임아웃 (초)",
        ge=10,
        le=3600,
        example=300,
    )

    max_retries: int = Field(
        default=3,
        description="실패 시 최대 재시도 횟수",
        ge=0,
        le=10,
        example=3,
    )

    extra_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="파서별 추가 설정 (JSON)",
        example={"ocr": "auto", "output_format": "html"},
    )


class UpdateParserConfigRequestDTO(BaseModel):
    """
    파서 설정 수정 요청 DTO

    수정할 필드만 포함하여 요청합니다.
    """

    display_name: Optional[str] = Field(
        default=None,
        description="표시 이름",
        max_length=100,
        example="Updated Parser Name",
    )

    api_endpoint: Optional[str] = Field(
        default=None,
        description="API 엔드포인트 URL",
        example="https://api.updated.com/parse",
    )

    api_key: Optional[str] = Field(
        default=None,
        description="API 인증 키",
        example="new-api-key",
    )

    is_active: Optional[bool] = Field(
        default=None,
        description="활성화 여부",
        example=True,
    )

    timeout_seconds: Optional[int] = Field(
        default=None,
        description="API 호출 타임아웃 (초)",
        ge=10,
        le=3600,
        example=300,
    )

    max_retries: Optional[int] = Field(
        default=None,
        description="실패 시 최대 재시도 횟수",
        ge=0,
        le=10,
        example=3,
    )

    extra_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="파서별 추가 설정 (JSON)",
        example={"ocr": "force"},
    )


# ========================================
# Response DTOs
# ========================================


class ParserConfigResponseDTO(BaseModel):
    """
    파서 설정 응답 DTO
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "parser_name": "ktc_parser",
                "display_name": "KT Cloud Document Parser",
                "api_endpoint": "https://api.ktcloud.com/v1/document-ai/document-parse",
                "is_active": True,
                "timeout_seconds": 300,
                "max_retries": 3,
                "extra_config": {
                    "ocr": "auto",
                    "coordinates": False,
                    "output_formats": ["markdown"],
                },
                "created_at": "2026-01-05T07:35:45.158651Z",
                "updated_at": "2026-01-05T07:35:45.158651Z",
            }
        },
    )

    id: int = Field(
        ...,
        description="파서 설정 ID",
        example=1,
    )

    parser_name: str = Field(
        ...,
        description="파서 식별자",
        example="ktc_parser",
    )

    display_name: str = Field(
        ...,
        description="표시 이름",
        example="KT Cloud Document Parser",
    )

    api_endpoint: str = Field(
        ...,
        description="API 엔드포인트 URL",
        example="https://api.ktcloud.com/document-parse",
    )

    is_active: bool = Field(
        ...,
        description="활성화 여부",
        example=True,
    )

    timeout_seconds: int = Field(
        ...,
        description="API 호출 타임아웃 (초)",
        example=300,
    )

    max_retries: int = Field(
        ...,
        description="실패 시 최대 재시도 횟수",
        example=3,
    )

    extra_config: Dict[str, Any] = Field(
        ...,
        description="파서별 추가 설정 (JSON)",
        example={"ocr": "auto"},
    )

    created_at: datetime = Field(
        ...,
        description="생성 시간",
    )

    updated_at: datetime = Field(
        ...,
        description="수정 시간",
    )


class ParserConfigListResponseDTO(BaseModel):
    """
    파서 설정 목록 응답 DTO
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "parser_name": "ktc_parser",
                        "display_name": "KT Cloud Document Parser",
                        "api_endpoint": "https://api.ktcloud.com/v1/document-ai/document-parse",
                        "is_active": True,
                        "timeout_seconds": 300,
                        "max_retries": 3,
                        "extra_config": {
                            "ocr": "auto",
                            "coordinates": False,
                            "output_formats": ["markdown"],
                        },
                        "created_at": "2026-01-05T07:35:45.158651Z",
                        "updated_at": "2026-01-05T07:35:45.158651Z",
                    }
                ],
                "total": 1,
            }
        },
    )

    items: List[ParserConfigResponseDTO] = Field(
        ...,
        description="파서 설정 목록",
    )

    total: int = Field(
        ...,
        description="전체 파서 설정 수",
        example=2,
    )


class MessageResponseDTO(BaseModel):
    """
    단순 메시지 응답 DTO
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "파서 설정이 성공적으로 삭제되었습니다: ktc_parser",
            }
        },
    )

    message: str = Field(
        ...,
        description="응답 메시지",
        example="파서 설정이 성공적으로 삭제되었습니다.",
    )
