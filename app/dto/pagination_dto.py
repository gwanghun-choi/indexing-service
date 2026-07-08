"""
페이징 관련 DTO 정의

Milvus 제약사항: offset + limit < 16,384
page_size=50 기준 최대 327페이지, 16,350개 문서까지 조회 가능
"""

from typing import List

from pydantic import BaseModel, Field

from app.dto.table_dto import DocumentMetaResponseDTO, DocumentVectorResponseDTO


class PaginationMetaDTO(BaseModel):
    """페이징 메타데이터 DTO"""

    total_count: int = Field(..., description="전체 항목 수")
    total_pages: int = Field(..., description="전체 페이지 수")
    current_page: int = Field(..., description="현재 페이지 번호")
    page_size: int = Field(..., description="페이지당 항목 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")
    has_previous: bool = Field(..., description="이전 페이지 존재 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "total_count": 150,
                "total_pages": 8,
                "current_page": 1,
                "page_size": 20,
                "has_next": True,
                "has_previous": False,
            }
        }


class PaginatedDocumentMetaResponseDTO(BaseModel):
    """페이징된 문서 메타데이터 응답 DTO"""

    items: List[DocumentMetaResponseDTO] = Field(..., description="문서 메타데이터 목록")
    pagination: PaginationMetaDTO = Field(..., description="페이징 메타데이터")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": 123,
                        "category": "계약서",
                        "title": "2024년 근로계약서",
                        "filename": "근로계약서_2024.pdf",
                        "summary": "본 계약서는...",
                        "file_type": "pdf",
                        "file_size": 1048576,
                        "status": "completed",
                        "role_ids": [3],
                        "persona_id": 1,
                        "file_path": "contracts/2024/employment.pdf",
                        "download_url": "https://example.com/contracts/2024.pdf",
                        "chunk_count": 15,
                        "token": 3500,
                        "cost": 0.035,
                        "summary_token": 500,
                        "summary_cost": 0.005,
                        "group_id": 101,
                        "user_id": 2001,
                        "user_full_name": "홍길동",
                        "hash_sha256": "abc123def456789...",
                        "start_date": 1705276200,
                        "end_date": 1705276800,
                        "expiration_date": 1736812800,
                        "ref_count": 0,
                        "chunk_size": 500,
                        "chunk_overlap": 50,
                        "enable_pii_anonymization": 0,
                        "original_chunk_count": 15,
                        "filtered_chunk_count": 15,
                        "embedding_start_date": 1705276300,
                        "embedding_end_date": 1705276700,
                    }
                ],
                "pagination": {
                    "total_count": 150,
                    "total_pages": 8,
                    "current_page": 1,
                    "page_size": 20,
                    "has_next": True,
                    "has_previous": False,
                },
            }
        }


class PaginatedDocumentVectorResponseDTO(BaseModel):
    """페이징된 문서 벡터 데이터 응답 DTO"""

    items: List[DocumentVectorResponseDTO] = Field(..., description="벡터 데이터 목록")
    pagination: PaginationMetaDTO = Field(..., description="페이징 메타데이터")
