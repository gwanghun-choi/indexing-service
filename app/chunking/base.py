"""
Chunking 전략 추상 기본 클래스
"""
from abc import ABC, abstractmethod
from typing import Dict, List


class ChunkingStrategy(ABC):
    """
    청킹 전략 추상 기본 클래스

    모든 청킹 전략은 이 클래스를 상속받아 chunk() 메서드를 구현해야 합니다.
    """

    @abstractmethod
    def chunk(self, pages: List[Dict]) -> List[Dict]:
        """
        페이지 목록을 청크로 분할합니다.

        Args:
            pages: 파싱된 페이지 목록
                각 페이지는 {"page_number": int, "text": str} 형태

        Returns:
            청크 목록
                각 청크는 {"page_number": int, "chunk_index": int, "text": str} 형태
        """
        pass
