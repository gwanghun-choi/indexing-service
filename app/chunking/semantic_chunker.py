"""
시맨틱 청킹 전략 구현

문장 간 의미적 유사도를 기반으로 텍스트를 분할합니다.
"""
import asyncio
import logging
from typing import Dict, List

import numpy as np
from kiwipiepy import Kiwi

from app.chunking.base import ChunkingStrategy
from app.dto.chunking_dto import SemanticChunkingConfig
from app.embedding.factory import create_embedding

logger = logging.getLogger(__name__)


class SemanticChunker(ChunkingStrategy):
    """
    시맨틱 청킹 전략

    kiwipiepy를 사용하여 문장을 분리하고,
    문장 간 의미적 유사도를 기반으로 청크를 생성합니다.

    Attributes:
        config: SemanticChunkingConfig 설정
    """

    __slots__ = ["config", "_kiwi"]

    def __init__(self, config: SemanticChunkingConfig) -> None:
        """
        SemanticChunker를 초기화합니다.

        Args:
            config: 시맨틱 청킹 설정
        """
        self.config = config
        self._kiwi = Kiwi()

    def split_sentences(self, text: str) -> List[str]:
        """
        텍스트를 문장 단위로 분리합니다.

        Args:
            text: 분리할 텍스트

        Returns:
            문장 리스트
        """
        if not text or not text.strip():
            return []

        # kiwipiepy의 split_into_sents 사용
        sentences = self._kiwi.split_into_sents(text)
        return [sent.text.strip() for sent in sentences if sent.text.strip()]

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        두 벡터 간 코사인 유사도를 계산합니다.

        Args:
            vec1: 첫 번째 벡터
            vec2: 두 번째 벡터

        Returns:
            코사인 유사도 (-1.0 ~ 1.0)
        """
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def find_breakpoints(self, similarities: List[float]) -> List[int]:
        """
        유사도 리스트에서 분할 지점을 찾습니다.

        임계값 미만인 유사도 위치를 분할 지점으로 반환합니다.

        Args:
            similarities: 인접 문장 간 유사도 리스트

        Returns:
            분할 지점 인덱스 리스트
        """
        threshold = self.config.similarity_threshold
        breakpoints = []

        for i, sim in enumerate(similarities):
            if sim < threshold:
                breakpoints.append(i)

        return breakpoints

    async def _embed_sentences(self, sentences: List[str]) -> List[np.ndarray]:
        """
        문장 리스트를 배치 임베딩합니다.

        Args:
            sentences: 임베딩할 문장 리스트

        Returns:
            임베딩 벡터 리스트
        """
        embeddings = await create_embedding("openai", sentences)
        return [np.array(emb) for emb in embeddings]

    def _calculate_similarities(self, embeddings: List[np.ndarray]) -> List[float]:
        """
        인접 문장 간 유사도를 계산합니다.

        Args:
            embeddings: 임베딩 벡터 리스트

        Returns:
            유사도 리스트 (길이: len(embeddings) - 1)
        """
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self.cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)
        return similarities

    def _group_sentences_by_breakpoints(
        self,
        sentences: List[str],
        breakpoints: List[int],
    ) -> List[List[str]]:
        """
        분할 지점을 기준으로 문장을 그룹화합니다.

        Args:
            sentences: 문장 리스트
            breakpoints: 분할 지점 인덱스 리스트

        Returns:
            그룹화된 문장 리스트
        """
        if not sentences:
            return []

        groups = []
        start = 0

        for bp in sorted(breakpoints):
            # breakpoint는 유사도 인덱스이므로, 문장 인덱스로 변환 (bp + 1)
            end = bp + 1
            if start < end <= len(sentences):
                groups.append(sentences[start:end])
                start = end

        # 마지막 그룹
        if start < len(sentences):
            groups.append(sentences[start:])

        return groups

    def _apply_size_constraints(
        self,
        groups: List[List[str]],
        page_number: int,
        chunk_index_start: int,
    ) -> List[Dict]:
        """
        그룹에 크기 제약을 적용하여 청크를 생성합니다.

        Args:
            groups: 그룹화된 문장 리스트
            page_number: 페이지 번호
            chunk_index_start: 시작 청크 인덱스

        Returns:
            청크 리스트
        """
        chunks = []
        chunk_idx = chunk_index_start
        max_size = self.config.max_chunk_size

        for group in groups:
            text = " ".join(group)

            # max_chunk_size 초과 시 분할
            if len(text) > max_size:
                # 문장 단위로 분할
                current_chunk = []
                current_length = 0

                for sentence in group:
                    sentence_len = len(sentence)

                    # 단일 문장이 max 초과 시 강제 분할
                    if sentence_len > max_size:
                        # 현재 청크 저장
                        if current_chunk:
                            chunks.append({
                                "page_number": page_number,
                                "chunk_index": chunk_idx,
                                "text": " ".join(current_chunk),
                            })
                            chunk_idx += 1
                            current_chunk = []
                            current_length = 0

                        # 긴 문장 강제 분할
                        for i in range(0, sentence_len, max_size):
                            chunks.append({
                                "page_number": page_number,
                                "chunk_index": chunk_idx,
                                "text": sentence[i:i + max_size],
                            })
                            chunk_idx += 1
                    elif current_length + sentence_len + 1 > max_size:
                        # 현재 청크 저장하고 새 청크 시작
                        if current_chunk:
                            chunks.append({
                                "page_number": page_number,
                                "chunk_index": chunk_idx,
                                "text": " ".join(current_chunk),
                            })
                            chunk_idx += 1
                        current_chunk = [sentence]
                        current_length = sentence_len
                    else:
                        current_chunk.append(sentence)
                        current_length += sentence_len + 1

                # 남은 문장 저장
                if current_chunk:
                    chunks.append({
                        "page_number": page_number,
                        "chunk_index": chunk_idx,
                        "text": " ".join(current_chunk),
                    })
                    chunk_idx += 1
            else:
                chunks.append({
                    "page_number": page_number,
                    "chunk_index": chunk_idx,
                    "text": text,
                })
                chunk_idx += 1

        return chunks

    def chunk(self, pages: List[Dict]) -> List[Dict]:
        """
        페이지 목록을 시맨틱 청크로 분할합니다.

        Args:
            pages: 파싱된 페이지 목록
                각 페이지는 {"page_number": int, "text": str} 형태

        Returns:
            청크 목록
                각 청크는 {"page_number": int, "chunk_index": int, "text": str} 형태
        """
        all_chunks = []
        chunk_idx = 0

        for page in pages:
            if "text" not in page or "page_number" not in page:
                continue

            text = page["text"]
            page_number = page["page_number"]

            # 1. 문장 분리
            sentences = self.split_sentences(text)
            if not sentences:
                continue

            # 2. 임베딩 생성 및 유사도 계산
            embeddings = asyncio.run(self._embed_sentences(sentences))

            # 3. 인접 문장 유사도 계산
            similarities = self._calculate_similarities(embeddings)

            # 4. 분할 지점 탐지
            breakpoints = self.find_breakpoints(similarities)

            # 5. 문장 그룹화
            groups = self._group_sentences_by_breakpoints(sentences, breakpoints)

            # 6. 크기 제약 적용
            page_chunks = self._apply_size_constraints(groups, page_number, chunk_idx)
            all_chunks.extend(page_chunks)
            chunk_idx += len(page_chunks)

        return all_chunks
