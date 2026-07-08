"""
사용자 정의 카테고리 DTO

카테고리 CRUD 작업을 위한 요청/응답 데이터 전송 객체를 정의합니다.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# -- Request DTOs --


class UserCategoryCreateDTO(BaseModel):
    """카테고리 생성 요청 DTO"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "NDA",
                "description": "비밀유지계약서",
                "default_retention_period": 10,
                "parent_id": 101,
            }
        }
    )

    name: str = Field(
        ...,
        max_length=100,
        description="카테고리 이름 (최대 100자)",
        examples=["NDA"],
    )
    description: Optional[str] = Field(
        None,
        description="카테고리 설명",
        examples=["비밀유지계약서"],
    )
    default_retention_period: int = Field(
        3,
        ge=1,
        le=100,
        description="만료기간 추천값 (년 단위, 1-100)",
        examples=[10],
    )
    parent_id: Optional[int] = Field(
        None,
        description="부모 카테고리 ID (NULL이면 루트 카테고리)",
        examples=[101],
    )


class UserCategoryUpdateDTO(BaseModel):
    """카테고리 수정 요청 DTO"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "라이선스 계약서",
                "description": "소프트웨어 라이선스 관련 계약서",
                "default_retention_period": 5,
            }
        }
    )

    name: Optional[str] = Field(
        None,
        max_length=100,
        description="카테고리 이름 (최대 100자)",
    )
    description: Optional[str] = Field(
        None,
        description="카테고리 설명",
    )
    default_retention_period: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="만료기간 추천값 (년 단위, 1-100)",
    )


# -- Response DTOs --


class RecentDocumentDTO(BaseModel):
    """최근 등록 문서 요약 DTO"""

    id: int = Field(..., description="문서 ID")
    title: str = Field(..., description="문서 제목")
    filename: str = Field(..., description="파일명")
    file_type: str = Field(..., description="파일 타입")
    status: str = Field(..., description="문서 상태")
    created_at: int = Field(..., description="등록일 (Unix timestamp, seconds / Milvus start_date 매핑)")


class AllDocumentsSummaryDTO(BaseModel):
    """전체 문서 통합 요약 DTO (카테고리 리스트와 별개의 root level 요약 객체)"""

    name: str = Field(default="전체", description="전체 문서 카테고리 명칭")
    document_count: int = Field(0, description="전체 문서 수")
    total_size: int = Field(0, description="총 용량 (바이트)")
    status_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="상태별 문서 개수",
    )
    recent_documents: List[RecentDocumentDTO] = Field(
        default_factory=list,
        description="최근 등록 문서 (최대 3건, created_at 내림차순)",
    )


class UserCategoryResponseDTO(BaseModel):
    """카테고리 응답 DTO"""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 103,
                "user_id": 100,
                "group_id": 1,
                "name": "NDA",
                "description": "비밀유지계약서",
                "default_retention_period": 10,
                "parent_id": 101,
                "depth": 2,
                "path": "101/103",
                "created_at": "2026-01-13T09:00:00Z",
                "updated_at": "2026-01-13T09:00:00Z",
                "document_count": 5,
                "status_counts": {
                    "uploading": 0,
                    "registered": 1,
                    "running": 0,
                    "uploaded": 4,
                    "failed": 0,
                    "skipped": 0,
                    "ocr_required": 0,
                },
            }
        }
    )

    id: int = Field(..., description="카테고리 ID")
    user_id: int = Field(..., description="소유자 사용자 ID")
    group_id: int = Field(..., description="소속 그룹 ID")
    name: str = Field(..., description="카테고리 이름")
    description: Optional[str] = Field(None, description="카테고리 설명")
    default_retention_period: int = Field(..., description="만료기간 추천값 (년)")
    parent_id: Optional[int] = Field(None, description="부모 카테고리 ID")
    depth: int = Field(..., description="계층 깊이")
    path: Optional[str] = Field(None, description="경로 문자열")
    created_at: datetime = Field(..., description="생성 시각")
    updated_at: datetime = Field(..., description="수정 시각")
    document_count: int = Field(0, description="해당 카테고리의 문서 수")
    total_size: int = Field(0, description="총 용량 (바이트)")
    status_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="상태별 문서 개수 (uploading, registered, running, uploaded, failed, skipped, ocr_required)",
    )
    recent_documents: List[RecentDocumentDTO] = Field(
        default_factory=list,
        description="최근 등록 문서 (최대 3건, created_at 내림차순)",
    )


class UserCategoryTreeNodeDTO(BaseModel):
    """카테고리 트리 노드 DTO (재귀 구조)"""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 101,
                "name": "계약서",
                "description": "각종 계약 관련 문서",
                "depth": 1,
                "default_retention_period": 10,
                "document_count": 10,
                "status_counts": {
                    "uploading": 0,
                    "registered": 2,
                    "running": 1,
                    "uploaded": 7,
                    "failed": 0,
                    "skipped": 0,
                    "ocr_required": 0,
                },
                "children": [
                    {
                        "id": 102,
                        "name": "NDA",
                        "description": "비밀유지계약서",
                        "depth": 2,
                        "default_retention_period": 10,
                        "document_count": 3,
                        "status_counts": {
                            "uploading": 0,
                            "registered": 1,
                            "running": 0,
                            "uploaded": 2,
                            "failed": 0,
                            "skipped": 0,
                            "ocr_required": 0,
                        },
                        "children": [],
                    },
                    {
                        "id": 103,
                        "name": "라이선스",
                        "description": "라이선스 계약서",
                        "depth": 2,
                        "default_retention_period": 5,
                        "document_count": 2,
                        "status_counts": {
                            "uploading": 0,
                            "registered": 0,
                            "running": 0,
                            "uploaded": 2,
                            "failed": 0,
                            "skipped": 0,
                            "ocr_required": 0,
                        },
                        "children": [],
                    },
                ],
            }
        }
    )

    id: int = Field(..., description="카테고리 ID")
    name: str = Field(..., description="카테고리 이름")
    description: Optional[str] = Field(None, description="카테고리 설명")
    depth: int = Field(..., description="계층 깊이")
    default_retention_period: int = Field(..., description="만료기간 추천값 (년)")
    document_count: int = Field(0, description="해당 카테고리의 문서 수")
    status_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="상태별 문서 개수 (uploading, registered, running, uploaded, failed, skipped, ocr_required)",
    )
    children: List["UserCategoryTreeNodeDTO"] = Field(
        default_factory=list,
        description="하위 카테고리 목록",
    )


# Forward reference 해결
UserCategoryTreeNodeDTO.model_rebuild()


class SystemCategoryResponseDTO(BaseModel):
    """시스템 템플릿 카테고리 응답 DTO"""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "계약서",
                "retention_period": 10,
                "description": "각종 계약 관련 문서",
                "total_size": 52428800,
                "document_count": 15,
                "status_counts": {
                    "uploading": 0,
                    "registered": 2,
                    "running": 1,
                    "uploaded": 12,
                    "failed": 0,
                    "skipped": 0,
                    "ocr_required": 0,
                },
            }
        }
    )

    id: int = Field(..., description="카테고리 ID")
    name: str = Field(..., description="카테고리 이름")
    retention_period: int = Field(..., description="권장 보관 기간 (년)")
    description: Optional[str] = Field(None, description="카테고리 설명")
    total_size: int = Field(0, description="총 용량 (바이트)")
    document_count: int = Field(0, description="해당 카테고리의 문서 수")
    status_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="상태별 문서 개수 (uploading, registered, running, uploaded, failed, skipped, ocr_required)",
    )
    recent_documents: List[RecentDocumentDTO] = Field(
        default_factory=list,
        description="최근 등록 문서 (최대 3건, created_at 내림차순)",
    )


class CombinedCategoryResponseDTO(BaseModel):
    """통합 카테고리 응답 DTO (시스템 + 사용자 카테고리)"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "system_categories": [
                    {
                        "id": 1,
                        "name": "계약서",
                        "retention_period": 10,
                        "description": "각종 계약 관련 문서",
                    }
                ],
                "user_categories": [
                    {
                        "id": 103,
                        "user_id": 100,
                        "group_id": 1,
                        "name": "NDA",
                        "description": "비밀유지계약서",
                        "default_retention_period": 10,
                        "parent_id": None,
                        "depth": 1,
                        "path": "103",
                        "created_at": "2026-01-13T09:00:00Z",
                        "updated_at": "2026-01-13T09:00:00Z",
                        "document_count": 5,
                    }
                ],
            }
        }
    )

    all_documents: AllDocumentsSummaryDTO = Field(
        ...,
        description="전체 문서 통합 요약 (카테고리 목록과 병렬 배치되는 root level 요약 객체)",
    )
    system_categories: List[SystemCategoryResponseDTO] = Field(
        ...,
        description="시스템 기본 카테고리 목록",
    )
    user_categories: List[UserCategoryResponseDTO] = Field(
        ...,
        description="사용자 정의 카테고리 목록",
    )


class CategoryDeleteResponseDTO(BaseModel):
    """카테고리 삭제 응답 DTO"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "카테고리가 성공적으로 삭제되었습니다.",
                "deleted_id": 103,
            }
        }
    )

    message: str = Field(..., description="처리 결과 메시지")
    deleted_id: int = Field(..., description="삭제된 카테고리 ID")
