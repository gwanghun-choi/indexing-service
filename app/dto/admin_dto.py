"""
Admin API DTO

관리자 전용 API를 위한 Data Transfer Objects를 정의합니다.
Milvus 컬렉션 관리 기능을 위한 DTO입니다.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ========================================
# Request DTOs
# ========================================


class DataDeleteRequestDTO(BaseModel):
    """
    데이터 삭제 요청 DTO

    컬렉션 내 데이터를 필터 조건으로 삭제합니다.
    preview=True 시 삭제 대상만 확인하고 실제 삭제하지 않습니다.
    """

    collection_name: str = Field(
        ...,
        description="컬렉션 이름",
        json_schema_extra={"example": "TB_1_vector"},
    )

    filter_expr: str = Field(
        ...,
        description="Milvus 필터 표현식 (삭제 대상 조건)",
        json_schema_extra={"example": "hash_sha256 == 'abc123'"},
    )

    preview: bool = Field(
        default=True,
        description="미리보기 모드 (True: 미리보기만, False: 실제 삭제)",
        json_schema_extra={"example": True},
    )


# ========================================
# Data Item DTOs (Milvus 결과 직렬화용)
# ========================================


class AdminMetaDataItemDTO(BaseModel):
    """
    Meta 컬렉션 데이터 아이템 DTO

    Milvus meta 컬렉션의 레코드를 표현합니다.
    role_ids를 List[int]로 명시하여 RepeatedScalarContainer 자동 변환.
    embedding_value는 메모리 절약을 위해 제외.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    title: str
    filename: str
    summary: str
    file_type: str
    file_size: int
    status: str
    role_ids: List[int]
    persona_id: int
    file_path: str
    download_url: str
    chunk_count: int
    token: int
    cost: float
    summary_token: int
    summary_cost: float
    group_id: int
    user_id: int
    hash_sha256: str
    start_date: int
    end_date: int
    expiration_date: int
    ref_count: int = 0
    anonymization_strategy: Optional[str] = None
    chunk_size: int
    chunk_overlap: int
    enable_pii_anonymization: int = 0
    pii_types: Optional[str] = None
    original_chunk_count: int
    filtered_chunk_count: int
    embedding_start_date: int
    embedding_end_date: int


class AdminVectorDataItemDTO(BaseModel):
    """
    Vector 컬렉션 데이터 아이템 DTO

    Milvus vector 컬렉션의 레코드를 표현합니다.
    role_ids를 List[int]로 명시하여 RepeatedScalarContainer 자동 변환.
    embedding_value는 메모리 절약을 위해 제외.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    title: str
    filename: str
    parsed_text: str
    page_number: int
    chunk_index: int
    token: int
    cost: float
    group_id: int
    user_id: int
    role_ids: List[int]
    hash_sha256: str
    date: int


class AdminMetaSummaryItemDTO(BaseModel):
    """
    Meta 컬렉션 요약 데이터 아이템 DTO

    관리자 대시보드에서 문서 목록을 경량화하여 조회할 때 사용합니다.
    AdminMetaDataItemDTO의 30개 이상 필드 대신 핵심 7개 필드만 반환합니다.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "category": "계약서",
                "file_type": "pdf",
                "filename": "근로계약서_2024.pdf",
                "token": 3500,
                "file_size": 1048576,
                "start_date": 1704067200,
                "status": "completed",
            }
        },
    )

    category: str = Field(..., description="문서 카테고리")
    file_type: str = Field(..., description="파일 유형 (pdf, docx 등)")
    filename: str = Field(..., description="파일명")
    token: int = Field(..., description="토큰 사용량")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    start_date: int = Field(..., description="등록일 (Unix timestamp)")
    status: str = Field(..., description="처리 상태 (pending, processing, completed, failed)")


# ========================================
# Response DTOs
# ========================================


class CollectionInfoDTO(BaseModel):
    """
    컬렉션 정보 DTO

    컬렉션 목록 조회 시 각 컬렉션의 기본 정보입니다.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "collection_name": "TB_1_meta",
                "db_type": "meta",
                "row_count": 150,
                "group_id": 1,
            }
        },
    )

    collection_name: str = Field(
        ...,
        description="컬렉션 이름",
        json_schema_extra={"example": "TB_1_meta"},
    )

    db_type: str = Field(
        ...,
        description="컬렉션 타입 (meta/vector)",
        json_schema_extra={"example": "meta"},
    )

    row_count: int = Field(
        ...,
        description="레코드 수",
        json_schema_extra={"example": 100},
    )

    group_id: Optional[int] = Field(
        default=None,
        description="그룹 ID (컬렉션 이름에서 추출)",
        json_schema_extra={"example": 1},
    )


class CollectionListResponseDTO(BaseModel):
    """
    컬렉션 목록 응답 DTO

    페이지네이션 정보와 함께 컬렉션 목록을 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "collection_name": "TB_1_meta",
                        "db_type": "meta",
                        "row_count": 150,
                        "group_id": 1,
                    },
                    {
                        "collection_name": "TB_1_vector",
                        "db_type": "vector",
                        "row_count": 1200,
                        "group_id": 1,
                    },
                ],
                "total": 2,
                "page": 1,
                "page_size": 50,
            }
        },
    )

    items: List[CollectionInfoDTO] = Field(
        ...,
        description="컬렉션 목록",
    )

    total: int = Field(
        ...,
        description="전체 컬렉션 수",
        json_schema_extra={"example": 10},
    )

    page: int = Field(
        ...,
        description="현재 페이지",
        json_schema_extra={"example": 1},
    )

    page_size: int = Field(
        ...,
        description="페이지 크기",
        json_schema_extra={"example": 50},
    )


class CollectionDetailResponseDTO(BaseModel):
    """
    컬렉션 상세 응답 DTO

    컬렉션의 스키마, 인덱스, 통계 정보를 포함합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection_name": "TB_1_meta",
                "db_type": "meta",
                "row_count": 150,
                "schema_fields": [
                    "id",
                    "category",
                    "title",
                    "filename",
                    "summary",
                    "file_type",
                    "file_size",
                    "status",
                    "role_ids",
                    "persona_id",
                    "file_path",
                    "download_url",
                    "chunk_count",
                    "token",
                    "cost",
                    "summary_token",
                    "summary_cost",
                    "group_id",
                    "user_id",
                    "hash_sha256",
                    "start_date",
                    "end_date",
                    "expiration_date",
                    "embedding_value",
                    "ref_count",
                    "anonymization_strategy",
                    "chunk_size",
                    "chunk_overlap",
                    "enable_pii_anonymization",
                    "pii_types",
                    "original_chunk_count",
                    "filtered_chunk_count",
                    "embedding_start_date",
                    "embedding_end_date",
                ],
                "indexes": [{"field": "embedding_value", "index_type": "FLAT"}],
            }
        },
    )

    collection_name: str = Field(
        ...,
        description="컬렉션 이름",
        json_schema_extra={"example": "TB_1_meta"},
    )

    db_type: str = Field(
        ...,
        description="컬렉션 타입",
        json_schema_extra={"example": "meta"},
    )

    row_count: int = Field(
        ...,
        description="레코드 수",
        json_schema_extra={"example": 100},
    )

    schema_fields: List[str] = Field(
        ...,
        description="스키마 필드 목록",
        json_schema_extra={"example": ["id", "title", "hash_sha256"]},
    )

    indexes: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="인덱스 정보",
    )


class MetaCollectionDataResponseDTO(BaseModel):
    """
    Meta 컬렉션 데이터 응답 DTO

    Meta 컬렉션의 페이지네이션된 데이터를 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "summary": "본 계약서는 2024년도 정규직 근로자의 고용 조건을 명시합니다.",
                        "file_type": "pdf",
                        "file_size": 1048576,
                        "status": "completed",
                        "role_ids": [1, 2, 3],
                        "persona_id": 0,
                        "file_path": "contracts/2024/employment.pdf",
                        "download_url": "https://storage.example.com/contracts/2024/employment.pdf",
                        "chunk_count": 15,
                        "token": 3500,
                        "cost": 0.035,
                        "summary_token": 500,
                        "summary_cost": 0.005,
                        "group_id": 1,
                        "user_id": 1,
                        "hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "start_date": 1704067200,
                        "end_date": 1735689600,
                        "expiration_date": 1767225600,
                        "ref_count": 0,
                        "anonymization_strategy": None,
                        "chunk_size": 500,
                        "chunk_overlap": 50,
                        "enable_pii_anonymization": 0,
                        "pii_types": None,
                        "original_chunk_count": 15,
                        "filtered_chunk_count": 15,
                        "embedding_start_date": 1704067200,
                        "embedding_end_date": 1704067500,
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 50,
            }
        },
    )

    items: List[AdminMetaDataItemDTO] = Field(
        ...,
        description="Meta 컬렉션 데이터 목록",
    )

    total: int = Field(
        ...,
        description="전체 레코드 수",
        json_schema_extra={"example": 100},
    )

    page: int = Field(
        ...,
        description="현재 페이지",
        json_schema_extra={"example": 1},
    )

    page_size: int = Field(
        ...,
        description="페이지 크기",
        json_schema_extra={"example": 50},
    )


class MetaSummaryResponseDTO(BaseModel):
    """
    Meta 컬렉션 요약 응답 DTO

    Meta 컬렉션의 경량화된 요약 데이터를 페이지네이션하여 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "category": "계약서",
                        "file_type": "pdf",
                        "filename": "근로계약서_2024.pdf",
                        "token": 3500,
                        "file_size": 1048576,
                        "start_date": 1704067200,
                        "status": "completed",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 50,
            }
        },
    )

    items: List[AdminMetaSummaryItemDTO] = Field(
        ...,
        description="Meta 컬렉션 요약 데이터 목록",
    )

    total: int = Field(
        ...,
        description="전체 레코드 수",
        json_schema_extra={"example": 100},
    )

    page: int = Field(
        ...,
        description="현재 페이지",
        json_schema_extra={"example": 1},
    )

    page_size: int = Field(
        ...,
        description="페이지 크기",
        json_schema_extra={"example": 50},
    )


class VectorCollectionDataResponseDTO(BaseModel):
    """
    Vector 컬렉션 데이터 응답 DTO

    Vector 컬렉션의 페이지네이션된 데이터를 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "parsed_text": "제1조 (목적) 본 계약은 근로자의 고용 조건을...",
                        "page_number": 1,
                        "chunk_index": 0,
                        "token": 250,
                        "cost": 0.0025,
                        "group_id": 1,
                        "user_id": 1,
                        "role_ids": [1, 2, 3],
                        "hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "date": 1704067200,
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 50,
            }
        },
    )

    items: List[AdminVectorDataItemDTO] = Field(
        ...,
        description="Vector 컬렉션 데이터 목록",
    )

    total: int = Field(
        ...,
        description="전체 레코드 수",
        json_schema_extra={"example": 100},
    )

    page: int = Field(
        ...,
        description="현재 페이지",
        json_schema_extra={"example": 1},
    )

    page_size: int = Field(
        ...,
        description="페이지 크기",
        json_schema_extra={"example": 50},
    )


class DeletePreviewResponseDTO(BaseModel):
    """
    삭제 미리보기 응답 DTO

    삭제 대상 데이터의 수와 샘플을 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection_name": "TB_1_vector",
                "affected_count": 25,
                "sample_records": [
                    {
                        "id": 101,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "parsed_text": "본 계약서는 2024년도 정규직 근로자의 고용 조건을...",
                        "page_number": 1,
                        "chunk_index": 0,
                        "token": 350,
                        "cost": 0.0035,
                        "group_id": 1,
                        "user_id": 1,
                        "role_ids": [1, 2, 3],
                        "hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "date": 1704067200,
                    }
                ],
            }
        },
    )

    collection_name: str = Field(
        ...,
        description="컬렉션 이름",
        json_schema_extra={"example": "TB_1_vector"},
    )

    affected_count: int = Field(
        ...,
        description="영향받는 레코드 수",
        json_schema_extra={"example": 25},
    )

    sample_records: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="삭제될 샘플 레코드 (최대 10개)",
    )


class DataDeleteResponseDTO(BaseModel):
    """
    데이터 삭제 응답 DTO

    실제 삭제 결과를 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection_name": "TB_1_vector",
                "deleted_count": 25,
                "message": "25개 레코드가 삭제되었습니다.",
            }
        },
    )

    collection_name: str = Field(
        ...,
        description="컬렉션 이름",
        json_schema_extra={"example": "TB_1_vector"},
    )

    deleted_count: int = Field(
        ...,
        description="삭제된 레코드 수",
        json_schema_extra={"example": 25},
    )

    message: str = Field(
        ...,
        description="처리 결과 메시지",
        json_schema_extra={"example": "25개 레코드가 삭제되었습니다."},
    )


# ========================================
# PUT Request DTOs (전체 교체)
# ========================================


class MetaPutItemDTO(BaseModel):
    """
    Meta 컬렉션 PUT 아이템 DTO

    수정 가능한 필드를 전체 교체합니다. 모든 필드가 필수입니다.
    임베딩 재계산이 필요한 필드(summary, embedding_value)와
    시스템 산출 필드(token, cost 등)는 제외됩니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "category": "계약서",
                "title": "2024년 근로계약서",
                "filename": "근로계약서_2024.pdf",
                "status": "completed",
                "role_ids": [1, 2, 3],
                "persona_id": 0,
                "group_id": 1,
                "user_id": 1,
                "file_path": "contracts/2024/employment.pdf",
                "download_url": "https://storage.example.com/contracts/2024/employment.pdf",
                "start_date": 1704067200,
                "end_date": 1735689600,
                "expiration_date": 1767225600,
                "anonymization_strategy": None,
                "enable_pii_anonymization": 0,
                "pii_types": None,
            }
        },
    )

    id: int = Field(..., description="레코드 ID (Primary Key)")
    category: str = Field(..., description="문서 카테고리")
    title: str = Field(..., description="제목")
    filename: str = Field(..., description="파일 이름")
    status: str = Field(..., description="처리 상태")
    role_ids: List[int] = Field(..., description="접근 가능한 역할 ID 리스트")
    persona_id: int = Field(..., description="페르소나 ID")
    group_id: int = Field(..., description="그룹 ID")
    user_id: int = Field(..., description="사용자 ID")
    file_path: str = Field(..., description="파일 경로")
    download_url: str = Field(..., description="다운로드 URL")
    start_date: int = Field(..., description="작업 시작일 (Unix timestamp)")
    end_date: int = Field(..., description="작업 종료일 (Unix timestamp)")
    expiration_date: int = Field(..., description="문서 만료일 (Unix timestamp)")
    anonymization_strategy: Optional[str] = Field(..., description="PII 비식별화 전략")
    enable_pii_anonymization: int = Field(..., description="PII 비식별화 활성화 여부 (0/1)")
    pii_types: Optional[str] = Field(..., description="비식별화 대상 PII 유형")


class MetaPutRequestDTO(BaseModel):
    """
    Meta 컬렉션 PUT 요청 DTO

    Meta 컬렉션의 수정 가능한 필드를 전체 교체합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": 1,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "status": "completed",
                        "role_ids": [1, 2, 3],
                        "persona_id": 0,
                        "group_id": 1,
                        "user_id": 1,
                        "file_path": "contracts/2024/employment.pdf",
                        "download_url": "https://storage.example.com/file.pdf",
                        "start_date": 1704067200,
                        "end_date": 1735689600,
                        "expiration_date": 1767225600,
                        "anonymization_strategy": None,
                        "enable_pii_anonymization": 0,
                        "pii_types": None,
                    }
                ]
            }
        },
    )

    data: List[MetaPutItemDTO] = Field(
        ...,
        description="전체 교체할 데이터 목록",
    )


class VectorPutItemDTO(BaseModel):
    """
    Vector 컬렉션 PUT 아이템 DTO

    수정 가능한 필드를 전체 교체합니다. 모든 필드가 필수입니다.
    임베딩 재계산이 필요한 필드(parsed_text, embedding_value)와
    시스템 산출 필드(token, cost 등)는 제외됩니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "category": "계약서",
                "title": "2024년 근로계약서",
                "filename": "근로계약서_2024.pdf",
                "role_ids": [1, 2, 3],
                "group_id": 1,
                "user_id": 1,
            }
        },
    )

    id: int = Field(..., description="레코드 ID (Primary Key)")
    category: str = Field(..., description="문서 카테고리")
    title: str = Field(..., description="제목")
    filename: str = Field(..., description="파일 이름")
    role_ids: List[int] = Field(..., description="접근 가능한 역할 ID 리스트")
    group_id: int = Field(..., description="그룹 ID")
    user_id: int = Field(..., description="사용자 ID")


class VectorPutRequestDTO(BaseModel):
    """
    Vector 컬렉션 PUT 요청 DTO

    Vector 컬렉션의 수정 가능한 필드를 전체 교체합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": 1,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "role_ids": [1, 2, 3],
                        "group_id": 1,
                        "user_id": 1,
                    }
                ]
            }
        },
    )

    data: List[VectorPutItemDTO] = Field(
        ...,
        description="전체 교체할 데이터 목록",
    )


# ========================================
# PATCH Request DTOs (부분 수정)
# ========================================


class MetaPatchItemDTO(BaseModel):
    """
    Meta 컬렉션 PATCH 아이템 DTO

    수정할 필드만 선택적으로 제공합니다. id만 필수입니다.
    임베딩 재계산이 필요한 필드(summary, embedding_value)와
    시스템 산출 필드(token, cost 등)는 제외됩니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "status": "completed",
                "expiration_date": 1767225600,
            }
        },
    )

    id: int = Field(..., description="레코드 ID (Primary Key)")
    category: Optional[str] = Field(default=None, description="문서 카테고리")
    title: Optional[str] = Field(default=None, description="제목")
    filename: Optional[str] = Field(default=None, description="파일 이름")
    status: Optional[str] = Field(default=None, description="처리 상태")
    role_ids: Optional[List[int]] = Field(default=None, description="접근 가능한 역할 ID 리스트")
    persona_id: Optional[int] = Field(default=None, description="페르소나 ID")
    group_id: Optional[int] = Field(default=None, description="그룹 ID")
    user_id: Optional[int] = Field(default=None, description="사용자 ID")
    file_path: Optional[str] = Field(default=None, description="파일 경로")
    download_url: Optional[str] = Field(default=None, description="다운로드 URL")
    start_date: Optional[int] = Field(default=None, description="작업 시작일 (Unix timestamp)")
    end_date: Optional[int] = Field(default=None, description="작업 종료일 (Unix timestamp)")
    expiration_date: Optional[int] = Field(default=None, description="문서 만료일 (Unix timestamp)")
    anonymization_strategy: Optional[str] = Field(default=None, description="PII 비식별화 전략")
    enable_pii_anonymization: Optional[int] = Field(default=None, description="PII 비식별화 활성화 여부 (0/1)")
    pii_types: Optional[str] = Field(default=None, description="비식별화 대상 PII 유형")


class MetaPatchRequestDTO(BaseModel):
    """
    Meta 컬렉션 PATCH 요청 DTO

    Meta 컬렉션의 데이터를 부분 수정합니다. 변경할 필드만 제공합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": 1,
                        "status": "completed",
                        "expiration_date": 1767225600,
                    }
                ]
            }
        },
    )

    data: List[MetaPatchItemDTO] = Field(
        ...,
        description="부분 수정할 데이터 목록 (id 필수, 나머지 선택)",
    )


class VectorPatchItemDTO(BaseModel):
    """
    Vector 컬렉션 PATCH 아이템 DTO

    수정할 필드만 선택적으로 제공합니다. id만 필수입니다.
    임베딩 재계산이 필요한 필드(parsed_text, embedding_value)와
    시스템 산출 필드(token, cost 등)는 제외됩니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "category": "보고서",
            }
        },
    )

    id: int = Field(..., description="레코드 ID (Primary Key)")
    category: Optional[str] = Field(default=None, description="문서 카테고리")
    title: Optional[str] = Field(default=None, description="제목")
    filename: Optional[str] = Field(default=None, description="파일 이름")
    role_ids: Optional[List[int]] = Field(default=None, description="접근 가능한 역할 ID 리스트")
    group_id: Optional[int] = Field(default=None, description="그룹 ID")
    user_id: Optional[int] = Field(default=None, description="사용자 ID")


class VectorPatchRequestDTO(BaseModel):
    """
    Vector 컬렉션 PATCH 요청 DTO

    Vector 컬렉션의 데이터를 부분 수정합니다. 변경할 필드만 제공합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "id": 1,
                        "category": "보고서",
                    }
                ]
            }
        },
    )

    data: List[VectorPatchItemDTO] = Field(
        ...,
        description="부분 수정할 데이터 목록 (id 필수, 나머지 선택)",
    )


# ========================================
# Modify Response DTOs (PUT/PATCH 공용)
# ========================================


class MetaModifyResponseDTO(BaseModel):
    """
    Meta 컬렉션 수정 응답 DTO (PUT/PATCH 공용)

    수정된 레코드의 전체 데이터를 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection_name": "TB_1_meta",
                "modified_count": 1,
                "items": [
                    {
                        "id": 1,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "summary": "본 계약서는 2024년도 정규직 근로자의 고용 조건을 명시합니다.",
                        "file_type": "pdf",
                        "file_size": 1048576,
                        "status": "completed",
                        "role_ids": [1, 2, 3],
                        "persona_id": 0,
                        "file_path": "contracts/2024/employment.pdf",
                        "download_url": "https://storage.example.com/contracts/2024/employment.pdf",
                        "chunk_count": 15,
                        "token": 3500,
                        "cost": 0.035,
                        "summary_token": 500,
                        "summary_cost": 0.005,
                        "group_id": 1,
                        "user_id": 1,
                        "hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "start_date": 1704067200,
                        "end_date": 1735689600,
                        "expiration_date": 1767225600,
                        "ref_count": 0,
                        "anonymization_strategy": None,
                        "chunk_size": 500,
                        "chunk_overlap": 50,
                        "enable_pii_anonymization": 0,
                        "pii_types": None,
                        "original_chunk_count": 15,
                        "filtered_chunk_count": 15,
                        "embedding_start_date": 1704067200,
                        "embedding_end_date": 1704067500,
                    }
                ],
            }
        },
    )

    collection_name: str = Field(
        ...,
        description="컬렉션 이름",
        json_schema_extra={"example": "TB_1_meta"},
    )

    modified_count: int = Field(
        ...,
        description="수정된 레코드 수",
        json_schema_extra={"example": 1},
    )

    items: List[AdminMetaDataItemDTO] = Field(
        ...,
        description="수정된 레코드 목록 (전체 필드 포함)",
    )


class VectorModifyResponseDTO(BaseModel):
    """
    Vector 컬렉션 수정 응답 DTO (PUT/PATCH 공용)

    수정된 레코드의 전체 데이터를 반환합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collection_name": "TB_1_vector",
                "modified_count": 1,
                "items": [
                    {
                        "id": 1,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "parsed_text": "제1조 (목적) 본 계약은 근로자의 고용 조건을...",
                        "page_number": 1,
                        "chunk_index": 0,
                        "token": 250,
                        "cost": 0.0025,
                        "group_id": 1,
                        "user_id": 1,
                        "role_ids": [1, 2, 3],
                        "hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                        "date": 1704067200,
                    }
                ],
            }
        },
    )

    collection_name: str = Field(
        ...,
        description="컬렉션 이름",
        json_schema_extra={"example": "TB_1_vector"},
    )

    modified_count: int = Field(
        ...,
        description="수정된 레코드 수",
        json_schema_extra={"example": 1},
    )

    items: List[AdminVectorDataItemDTO] = Field(
        ...,
        description="수정된 레코드 목록 (전체 필드 포함)",
    )
