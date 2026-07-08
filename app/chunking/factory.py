"""
Chunker 팩토리 모듈
"""
from app.chunking.base import ChunkingStrategy
from app.chunking.fixed_chunker import FixedChunker
from app.chunking.semantic_chunker import SemanticChunker
from app.dto.chunking_dto import (
    ChunkingConfig,
    FixedChunkingConfig,
    SemanticChunkingConfig,
)


def create_chunker(config: ChunkingConfig) -> ChunkingStrategy:
    """
    청킹 설정에 따라 적절한 Chunker를 생성합니다.

    Args:
        config: 청킹 설정 (FixedChunkingConfig 또는 SemanticChunkingConfig)

    Returns:
        ChunkingStrategy 구현체

    Raises:
        ValueError: 지원하지 않는 전략인 경우
    """
    if isinstance(config, FixedChunkingConfig):
        return FixedChunker(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

    if isinstance(config, SemanticChunkingConfig):
        return SemanticChunker(config=config)

    raise ValueError(f"지원하지 않는 청킹 전략입니다: {getattr(config, 'strategy', 'unknown')}")


class ChunkerFactory:
    """
    Chunker 팩토리 클래스

    정적 메서드를 통해 Chunker를 생성합니다.
    """

    @staticmethod
    def create(config: ChunkingConfig) -> ChunkingStrategy:
        """
        청킹 설정에 따라 적절한 Chunker를 생성합니다.

        Args:
            config: 청킹 설정 (FixedChunkingConfig 또는 SemanticChunkingConfig)

        Returns:
            ChunkingStrategy 구현체

        Raises:
            ValueError: 지원하지 않는 전략인 경우
        """
        return create_chunker(config)

    @staticmethod
    def create_fixed(chunk_size: int, chunk_overlap: int) -> FixedChunker:
        """
        고정 크기 Chunker를 직접 생성합니다.

        기존 코드와의 호환성을 위해 제공됩니다.

        Args:
            chunk_size: 청크 크기 (문자 수)
            chunk_overlap: 청크 오버랩 (문자 수)

        Returns:
            FixedChunker 인스턴스
        """
        return FixedChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
