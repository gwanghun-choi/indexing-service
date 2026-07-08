"""
고정 크기 청킹 전략 구현
"""
from typing import Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.chunking.base import ChunkingStrategy


class FixedChunker(ChunkingStrategy):
    """
    고정 크기 청킹 전략

    RecursiveCharacterTextSplitter를 사용하여 텍스트를 고정된 크기로 분할합니다.

    Attributes:
        chunk_size: 청크 크기 (문자 수)
        chunk_overlap: 청크 오버랩 (문자 수)
    """

    __slots__ = ["chunk_size", "chunk_overlap", "_splitter"]

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        """
        FixedChunker를 초기화합니다.

        Args:
            chunk_size: 청크 크기 (문자 수)
            chunk_overlap: 청크 오버랩 (문자 수)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk(self, pages: List[Dict]) -> List[Dict]:
        """
        페이지 목록을 고정 크기 청크로 분할합니다.

        Args:
            pages: 파싱된 페이지 목록
                각 페이지는 {"page_number": int, "text": str} 형태

        Returns:
            청크 목록
                각 청크는 {"page_number": int, "chunk_index": int, "text": str} 형태
        """
        text_chunks = []
        chunk_idx = 0

        for page in pages:
            # page가 정상적인 페이지 데이터인지 확인
            if "text" in page and "page_number" in page:
                for chunk_text in self._splitter.split_text(page["text"]):
                    text_chunks.append(
                        {
                            "page_number": page["page_number"],
                            "chunk_index": chunk_idx,
                            "text": chunk_text,
                        }
                    )
                    chunk_idx += 1

        return text_chunks
