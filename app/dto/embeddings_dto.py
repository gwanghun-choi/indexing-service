from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.dto.chunking_dto import (
    ChunkingConfig,
    FixedChunkingConfig,
    parse_chunking_config,
)


class GenerateEmbeddingRequestDTO(BaseModel):
    """
    임베딩 생성 요청 DTO

    등록된 문서(status=registered)에 대해 임베딩을 생성하는 요청 정보입니다.

    청킹 설정 방법:
    1. chunking 객체 사용 (권장): strategy에 따라 fixed/semantic 청킹 선택
    2. chunk_size/chunk_overlap 사용 (하위 호환): 기존 방식, fixed 청킹만 지원
    """

    hash_sha256_list: List[str] = Field(
        ...,
        description="임베딩을 생성할 문서의 SHA256 해시값 리스트 (개수 제한 없음)",
        min_length=1,
    )

    # 새로운 chunking 설정 (Discriminated Union)
    chunking: Optional[Dict[str, Any]] = Field(
        default=None,
        description="청킹 설정. strategy='fixed' 또는 'semantic' 선택",
    )

    # 하위 호환성을 위한 기존 필드 (Optional로 변경)
    chunk_size: Optional[int] = Field(
        default=None,
        description="[하위 호환] 청크 크기 (chunking 미사용 시)",
    )

    chunk_overlap: Optional[int] = Field(
        default=None,
        description="[하위 호환] 청크 오버랩 크기 (chunking 미사용 시)",
    )

    @model_validator(mode="after")
    def validate_chunking_config(self):
        """chunking 또는 chunk_size/chunk_overlap 중 하나는 필수"""
        if self.chunking is None:
            if self.chunk_size is None or self.chunk_overlap is None:
                raise ValueError(
                    "chunking 설정 또는 chunk_size/chunk_overlap을 제공해야 합니다."
                )
        return self

    def get_chunking_config(self) -> ChunkingConfig:
        """
        청킹 설정을 반환합니다.

        Returns:
            ChunkingConfig (FixedChunkingConfig 또는 SemanticChunkingConfig)
        """
        if self.chunking is not None:
            return parse_chunking_config(self.chunking)

        # 하위 호환: 기존 필드로 FixedChunkingConfig 생성
        return FixedChunkingConfig(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

    enable_pii_anonymization: bool = Field(
        ..., description="개인정보 비식별화 활성화 여부"
    )

    pii_strategy: Optional[str] = Field(
        default=None, description="개인정보 비식별화 전략"
    )

    pii_types: Optional[List[str]] = Field(
        default=None, description="비식별화할 개인정보 유형 리스트"
    )

    persona_id: int = Field(default=0, description="페르소나 ID")

    filter_score: Optional[float] = Field(default=None, description="필터링 점수")

    document_parser: Optional[str] = Field(
        default=None,
        description="사용할 문서 파서. None: 기본 파서, 'ktc_parser': KT Cloud Document Parse API",
    )

    @field_validator("hash_sha256_list")
    @classmethod
    def validate_hash_list(cls, v):
        """해시값 리스트 검증"""
        if not v:
            raise ValueError("hash_sha256_list는 최소 1개 이상의 값을 포함해야 합니다.")

        # 중복 제거
        unique_hashes = list(set(v))
        if len(unique_hashes) != len(v):
            raise ValueError("hash_sha256_list에 중복된 값이 있습니다.")

        # 각 해시값 길이 검증 (SHA256은 64자)
        for hash_value in v:
            if not hash_value or not isinstance(hash_value, str):
                raise ValueError("hash_sha256 값은 빈 문자열이 아니어야 합니다.")
            if len(hash_value) != 64:
                raise ValueError(
                    f"hash_sha256 값은 64자여야 합니다. (입력값: {len(hash_value)}자)"
                )

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "hash_sha256_list": [
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",
                ],
                "chunk_size": 500,
                "chunk_overlap": 50,
                "enable_pii_anonymization": False,
            }
        }


class GenerateEmbeddingResponseDTO(BaseModel):
    """
    임베딩 생성 응답 DTO

    임베딩 생성 요청 결과를 반환합니다.
    """

    result: bool = Field(
        ...,
        description="작업 성공 여부 (True: 성공, False: 실패)",
        example=True,
    )

    message: str = Field(
        ...,
        description="처리 결과 메시지",
        example="3개 문서가 큐에 등록되었습니다. 가용한 worker가 병렬로 처리합니다.",
    )

    task_ids: List[str] = Field(
        ...,
        description="생성된 Celery 작업 ID 리스트 (WebSocket 알림 추적용)",
        example=[
            "550e8400-e29b-41d4-a716-446655440000",
            "550e8400-e29b-41d4-a716-446655440001",
        ],
    )

    success_count: int = Field(
        ...,
        description="성공적으로 큐에 등록된 문서 수",
        ge=0,
        example=3,
    )

    failed_count: int = Field(
        ...,
        description="실패한 문서 수 (권한 없음, 잘못된 상태 등)",
        ge=0,
        example=0,
    )

    failed_documents: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="실패한 문서 정보 (실패 사유 포함)",
        example=[
            {
                "hash_sha256": "abc123...",
                "reason": "권한 없음",
                "status": "uploaded",
            }
        ],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "result": True,
                "message": "5개 문서가 큐에 등록되었습니다. 가용한 worker가 병렬로 처리합니다.",
                "task_ids": [
                    "550e8400-e29b-41d4-a716-446655440000",
                    "550e8400-e29b-41d4-a716-446655440001",
                    "550e8400-e29b-41d4-a716-446655440002",
                    "550e8400-e29b-41d4-a716-446655440003",
                    "550e8400-e29b-41d4-a716-446655440004",
                ],
                "success_count": 5,
                "failed_count": 0,
                "failed_documents": None,
            }
        }


class RollbackEmbeddingRequestDTO(BaseModel):
    """
    임베딩 롤백 요청 DTO

    임베딩 파이프라인 실행 전 상태(registered)로 되돌리는 요청 정보입니다.
    """

    hash_sha256_list: List[str] = Field(
        ...,
        description="롤백할 문서의 SHA256 해시값 리스트",
        min_items=1,
        example=["abc123def456...", "xyz789uvw012..."],
    )

    @field_validator("hash_sha256_list")
    @classmethod
    def validate_hash_list(cls, v):
        """해시값 리스트 검증"""
        if not v:
            raise ValueError("hash_sha256_list는 최소 1개 이상의 값을 포함해야 합니다.")

        # 중복 제거
        unique_hashes = list(set(v))
        if len(unique_hashes) != len(v):
            raise ValueError("hash_sha256_list에 중복된 값이 있습니다.")

        # 각 해시값 길이 검증 (SHA256은 64자)
        for hash_value in v:
            if not hash_value or not isinstance(hash_value, str):
                raise ValueError("hash_sha256 값은 빈 문자열이 아니어야 합니다.")
            if len(hash_value) != 64:
                raise ValueError(
                    f"hash_sha256 값은 64자여야 합니다. (입력값: {len(hash_value)}자)"
                )

        return v


class RollbackEmbeddingResponseDTO(BaseModel):
    """
    임베딩 롤백 응답 DTO

    임베딩 롤백 결과를 반환합니다.
    """

    result: bool = Field(
        ...,
        description="작업 성공 여부 (True: 성공, False: 실패)",
        example=True,
    )

    message: str = Field(
        ...,
        description="처리 결과 메시지",
        example="2개 문서 임베딩 롤백 완료",
    )

    success_count: int = Field(
        ...,
        description="롤백 성공한 문서 수",
        ge=0,
        example=2,
    )

    failed_count: int = Field(
        ...,
        description="롤백 실패한 문서 수",
        ge=0,
        example=0,
    )

    deleted_vectors: int = Field(
        ...,
        description="삭제된 벡터(청크) 수",
        ge=0,
        example=30,
    )

    deleted_bm25_docs: int = Field(
        ...,
        description="BM25 인덱스에서 삭제된 문서 수",
        ge=0,
        example=30,
    )

    failed_documents: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="롤백 실패한 문서 정보 (실패 사유 포함)",
        example=[
            {
                "hash_sha256": "abc123...",
                "reason": "문서 상태가 롤백 가능 상태가 아닙니다 (현재: registered)",
            }
        ],
    )
