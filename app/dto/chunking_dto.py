"""
Chunking 설정 DTO 모듈

Discriminated Union 패턴을 사용하여 strategy 필드에 따라 다른 파라미터를 갖는
청킹 설정을 정의합니다.
"""
from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class FixedChunkingConfig(BaseModel):
    """
    고정 크기 청킹 설정

    텍스트를 고정된 크기로 분할하는 전략입니다.

    Attributes:
        strategy: 전략 식별자 ("fixed")
        chunk_size: 청크 크기 (문자 수)
        chunk_overlap: 청크 오버랩 (문자 수)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"strategy": "fixed", "chunk_size": 500, "chunk_overlap": 50}
        }
    )

    strategy: Literal["fixed"] = Field(default="fixed", description="전략 식별자")
    chunk_size: int = Field(default=500, ge=1, description="청크 크기 (문자 수)")
    chunk_overlap: int = Field(default=50, ge=0, description="청크 오버랩 (문자 수)")


class SemanticChunkingConfig(BaseModel):
    """
    시맨틱 청킹 설정

    문장 간 의미적 유사도를 기반으로 텍스트를 분할하는 전략입니다.

    Attributes:
        strategy: 전략 식별자 ("semantic")
        similarity_threshold: 분할 임계값 (0.0~1.0, 낮을수록 세밀)
        min_chunk_size: 최소 청크 크기
        max_chunk_size: 최대 청크 크기
        buffer_size: 유사도 비교 시 인접 문장 수
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy": "semantic",
                "similarity_threshold": 0.5,
                "min_chunk_size": 100,
                "max_chunk_size": 1500,
                "buffer_size": 1,
            }
        }
    )

    strategy: Literal["semantic"] = Field(
        default="semantic", description="전략 식별자"
    )
    similarity_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="분할 임계값 (0.0~1.0)"
    )
    min_chunk_size: int = Field(default=100, ge=1, description="최소 청크 크기")
    max_chunk_size: int = Field(default=1500, ge=1, description="최대 청크 크기")
    buffer_size: int = Field(
        default=1, ge=1, description="유사도 비교 시 인접 문장 수"
    )


# Discriminated Union 타입
ChunkingConfig = Union[FixedChunkingConfig, SemanticChunkingConfig]


def parse_chunking_config(data: dict) -> ChunkingConfig:
    """
    딕셔너리에서 청킹 설정을 파싱합니다.

    strategy 필드에 따라 적절한 Config 타입을 반환합니다.

    Args:
        data: 청킹 설정 딕셔너리

    Returns:
        ChunkingConfig (FixedChunkingConfig 또는 SemanticChunkingConfig)

    Raises:
        ValueError: 지원하지 않는 전략인 경우
    """
    strategy = data.get("strategy", "fixed")

    if strategy == "fixed":
        return FixedChunkingConfig(**data)
    elif strategy == "semantic":
        return SemanticChunkingConfig(**data)
    else:
        raise ValueError(f"지원하지 않는 청킹 전략입니다: {strategy}")
