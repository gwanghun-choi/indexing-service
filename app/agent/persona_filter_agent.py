"""
페르소나 기반 Pre-Filter Agent
문서 청크를 페르소나의 역할과 의도에 맞춰 선별하는 에이전트
"""

# 표준 라이브러리
import asyncio
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class ChunkFilterResult:
    """청크 필터링 결과"""

    chunk_text: str
    is_relevant: bool
    relevance_score: float
    reasoning: str
    chunk_index: int
    page_number: int


class PersonaFilterAgent:
    """
    페르소나 기반 청크 필터링 에이전트
    LLM을 활용하여 페르소나의 역할과 의도에 맞는 청크만 선별
    """

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 클라이언트 (OpenAI, Claude 등)
        """
        self.llm_client = llm_client
        self.filter_cache = {}  # 필터링 결과 캐시

    async def filter_chunks_for_persona(
        self,
        chunks: List[Dict[str, Any]],
        persona: Dict[str, Any],
        batch_size: int = 10,
    ) -> List[ChunkFilterResult]:
        """
        페르소나에 맞춰 청크들을 필터링

        Args:
            chunks: 필터링할 청크 리스트
            persona: 페르소나 정보 (role, system_prompt, intent_template 등)
            batch_size: 배치 처리 크기

        Returns:
            필터링된 청크 결과 리스트
        """
        threshold = persona.get("filter_score", 0.7)  # filter_score 사용, 기본값 0.7
        logger.info(
            f"🎯 페르소나 '{persona.get('name')}'에 대한 청크 필터링 시작: {len(chunks)}개 청크 (필터 점수: {threshold})"
        )

        # 배치 처리를 위한 청크 분할
        batches = [
            chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)
        ]
        all_results = []

        for batch_idx, batch in enumerate(batches):
            logger.debug(f"배치 {batch_idx + 1}/{len(batches)} 처리 중...")

            # 배치 단위로 필터링 수행
            batch_results = await self._filter_batch(batch, persona)
            all_results.extend(batch_results)

            # API 제한을 위한 짧은 대기
            if batch_idx < len(batches) - 1:
                await asyncio.sleep(0.5)

        # 관련성 있는 청크만 선별
        relevant_chunks = [result for result in all_results if result.is_relevant]
        reduction_rate = (1 - len(relevant_chunks) / len(chunks)) * 100 if chunks else 0

        logger.info(
            f"✅ 필터링 완료: {len(relevant_chunks)}/{len(chunks)}개 선별 "
            f"(절감률: {reduction_rate:.1f}%)"
        )

        return all_results

    async def _filter_batch(
        self, batch: List[Dict[str, Any]], persona: Dict[str, Any]
    ) -> List[ChunkFilterResult]:
        """
        배치 단위로 청크 필터링 수행

        Args:
            batch: 청크 배치
            persona: 페르소나 정보

        Returns:
            배치 필터링 결과
        """
        # 프롬프트 구성
        prompt = self._build_filter_prompt(batch, persona)

        # 캐시 키 생성
        cache_key = self._generate_cache_key(batch, persona)

        # 캐시 확인
        if cache_key in self.filter_cache:
            logger.debug(f"캐시에서 결과 반환: {cache_key[:20]}...")
            return self.filter_cache[cache_key]

        try:
            # LLM 호출 (LLM-only)
            if not self.llm_client:
                logger.error(
                    "LLM 클라이언트가 설정되지 않았습니다. LLM 기반 필터링을 수행할 수 없습니다."
                )
                raise RuntimeError("LLM client is required for persona filtering")
            response = await self.llm_client.generate(prompt)
            results = self._parse_llm_response(response, batch)

            # 페르소나 필터링 결과를 사용자 친화적 요약으로 로깅
            try:
                parsed = json.loads(response)
                llm_results = parsed.get("results", [])
                relevant_count = sum(
                    1 for result in llm_results if result.get("is_relevant", False)
                )
                total_count = len(llm_results)

                # 필터링 결정사항의 간결한 요약 생성
                if relevant_count > 0:
                    # 첫 번째 관련성 있는 판단 근거를 예시로 사용
                    first_reasoning = next(
                        (
                            result.get("reasoning", "")
                            for result in llm_results
                            if result.get("is_relevant")
                        ),
                        "",
                    )
                    summary = f"{relevant_count}/{total_count}개 청크 관련성 있음. {first_reasoning}"
                else:
                    summary = f"{total_count}개 청크 중 관련성 있는 항목 없음"

                # 공백 정리 및 200자로 제한
                summary = " ".join(summary.replace("\n", " ").split())[:200]
                logger.info("persona_llm_summary: %s", summary)
            except Exception:
                # 로깅 실패는 메인 플로우에 영향 없이 무시
                pass

            # 캐시 저장
            self.filter_cache[cache_key] = results

            return results

        except Exception as e:
            logger.error(f"배치 필터링 중 오류 발생: {e}")
            # 오류 발생 시 모든 청크를 관련성 있다고 가정 (안전한 폴백)
            return [
                ChunkFilterResult(
                    chunk_text=chunk.get("text", ""),
                    is_relevant=True,
                    relevance_score=0.5,
                    reasoning="필터링 오류로 인한 기본 포함",
                    chunk_index=chunk.get("chunk_index", 0),
                    page_number=chunk.get("page_number", 0),
                )
                for chunk in batch
            ]

    def _build_filter_prompt(
        self, batch: List[Dict[str, Any]], persona: Dict[str, Any]
    ) -> str:
        """
        LLM에 전달할 필터링 프롬프트 구성

        Args:
            batch: 청크 배치
            persona: 페르소나 정보

        Returns:
            구성된 프롬프트
        """
        chunks_text = "\n\n---\n\n".join(
            [f"청크 {i+1}:\n{chunk.get('text', '')}" for i, chunk in enumerate(batch)]
        )

        system_prompt = str(persona.get("system_prompt") or "").strip()

        # DB 값 강제: 비어있으면 오류
        if not system_prompt:
            raise RuntimeError(
                "system_prompt is required from DB; found empty or missing"
            )

        # 최종 프롬프트 구조: 고정 텍스트 + 사용자 system_prompt + 평가 기준
        full_prompt = f"""You are an expert in document chunk filtering.  
Evaluate the relevance of provided chunks based on the following persona.

Persona Information:
{system_prompt}

Evaluation Criteria:
1. Is it directly related to the persona's role?
2. Is it knowledge the persona needs?
3. Is it aligned with the persona's purpose or main objectives?

Text Chunks:
"""
        # {text} 플레이스홀더와 JSON 형식은 f-string 밖에서 처리
        full_prompt += """{text}

Respond for each chunk in this format:
{
  "results": [
    {
      "chunk_index": 1,
      "is_relevant": true/false,
      "relevance_score": 0.0-1.0,
      "reasoning": "reasoning here"
    }
  ]
}"""

        # 플레이스홀더 치환 후 반환
        return full_prompt.replace("{text}", chunks_text).replace(
            "{chunks}", chunks_text
        )

    def _parse_llm_response(
        self, response: str, batch: List[Dict[str, Any]]
    ) -> List[ChunkFilterResult]:
        """
        LLM 응답을 파싱하여 결과 생성

        Args:
            response: LLM 응답
            batch: 원본 청크 배치

        Returns:
            파싱된 결과 리스트
        """
        try:
            # JSON 응답 파싱
            parsed = json.loads(response)
            results = []

            for i, chunk in enumerate(batch):
                # LLM 응답에서 해당 청크 결과 찾기
                chunk_result = next(
                    (
                        result
                        for result in parsed.get("results", [])
                        if result.get("chunk_index") == i + 1
                    ),
                    None,
                )

                if chunk_result:
                    results.append(
                        ChunkFilterResult(
                            chunk_text=chunk.get("text", ""),
                            is_relevant=chunk_result.get("is_relevant", True),
                            relevance_score=chunk_result.get("relevance_score", 0.5),
                            reasoning=chunk_result.get("reasoning", ""),
                            chunk_index=chunk.get("chunk_index", 0),
                            page_number=chunk.get("page_number", 0),
                        )
                    )
                else:
                    # 응답에 없는 경우 기본값
                    results.append(
                        ChunkFilterResult(
                            chunk_text=chunk.get("text", ""),
                            is_relevant=True,
                            relevance_score=0.5,
                            reasoning="LLM 응답 누락",
                            chunk_index=chunk.get("chunk_index", 0),
                            page_number=chunk.get("page_number", 0),
                        )
                    )

            return results

        except Exception as e:
            logger.error(f"LLM 응답 파싱 오류: {e}")
            # 파싱 실패 시 모든 청크 포함
            return [
                ChunkFilterResult(
                    chunk_text=chunk.get("text", ""),
                    is_relevant=True,
                    relevance_score=0.5,
                    reasoning="응답 파싱 실패",
                    chunk_index=chunk.get("chunk_index", 0),
                    page_number=chunk.get("page_number", 0),
                )
                for chunk in batch
            ]

    def _generate_cache_key(
        self, batch: List[Dict[str, Any]], persona: Dict[str, Any]
    ) -> str:
        """
        캐시 키 생성

        Args:
            batch: 청크 배치
            persona: 페르소나 정보

        Returns:
            캐시 키
        """
        import hashlib

        # 배치와 페르소나 정보를 조합하여 고유 키 생성
        batch_text = "".join([chunk.get("text", "")[:100] for chunk in batch])
        persona_text = f"{persona.get('name')}_{persona.get('role')}"

        combined = f"{batch_text}_{persona_text}"
        return hashlib.md5(combined.encode()).hexdigest()

    async def estimate_cost_reduction(
        self, total_chunks: int, selected_chunks: int, tokens_per_chunk: int = 256
    ) -> Dict[str, Any]:
        """
        비용 절감 효과 추정

        Args:
            total_chunks: 전체 청크 수
            selected_chunks: 선별된 청크 수
            tokens_per_chunk: 청크당 평균 토큰 수

        Returns:
            비용 절감 통계
        """
        reduction_rate = (
            (1 - selected_chunks / total_chunks) * 100 if total_chunks > 0 else 0
        )
        saved_chunks = total_chunks - selected_chunks
        saved_tokens = saved_chunks * tokens_per_chunk

        # 임베딩 모델별 비용 (예시)
        cost_per_1k_tokens = 0.0001  # OpenAI text-embedding-ada-002 기준
        saved_cost_usd = (saved_tokens / 1000) * cost_per_1k_tokens

        return {
            "total_chunks": total_chunks,
            "selected_chunks": selected_chunks,
            "saved_chunks": saved_chunks,
            "reduction_rate": round(reduction_rate, 2),
            "saved_tokens": saved_tokens,
            "saved_cost_usd": round(saved_cost_usd, 4),
            "timestamp": datetime.utcnow().isoformat(),
        }

