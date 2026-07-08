"""
페르소나 기반 필터링 서비스
외부 페르소나 API와 연동하여 system_prompt 조회 및 청크 필터링
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI
from sqlalchemy import select

from app.agent.persona_filter_agent import PersonaFilterAgent
from app.config.database.session import (
    get_async_db_context,
    get_async_db_context_for_worker,
)
from app.config.settings import settings
from app.entity.postgres.agent_persona_entity import AgtPersonasDataEntity

logger = logging.getLogger(__name__)


class PersonaService:
    """
    페르소나 기반 문서 필터링 서비스
    """

    def __init__(self):
        self.filter_agent = PersonaFilterAgent(llm_client=_PersonaFilterLLMClient())
        self._is_worker_context = False

    def _get_db_context(self):
        """
        실행 컨텍스트에 따라 적절한 DB 세션 컨텍스트 반환
        Celery 워커에서는 워커 전용 세션 사용
        """
        # Celery 워커 프로세스 감지
        server_software = os.environ.get("SERVER_SOFTWARE")
        if (
            server_software and "celery" in server_software.lower()
        ) or self._is_worker_context:
            return get_async_db_context_for_worker()
        return get_async_db_context()

    def set_worker_context(self, is_worker: bool = True):
        """워커 컨텍스트 설정"""
        self._is_worker_context = is_worker

    async def resolve_persona_system_prompt(
        self, persona_id: Optional[int]
    ) -> Optional[str]:
        """
        페르소나 데이터 직접 조회를 통한 system_prompt 획득

        Args:
            persona_id: 페르소나 ID (agt_personas_data.id)

        Returns:
            system_prompt 문자열 또는 None

        Raises:
            ValueError: 페르소나를 찾을 수 없는 경우
        """
        if persona_id is None:
            return None

        async with self._get_db_context() as db:
            try:
                # agt_personas_data 직접 조회
                stmt = select(AgtPersonasDataEntity).where(
                    AgtPersonasDataEntity.id == persona_id
                )
                result = await db.execute(stmt)
                persona_data = result.scalar_one_or_none()

                if not persona_data:
                    logger.warning(
                        f"페르소나 데이터를 찾을 수 없습니다: ID {persona_id}"
                    )
                    raise ValueError(f"Persona data not found: {persona_id}")

                # system_prompt 검증
                if (
                    not persona_data.system_prompt
                    or persona_data.system_prompt.strip() == ""
                ):
                    logger.warning(f"빈 system_prompt: persona_id={persona_id}")
                    return None

                logger.info(
                    f"✅ 페르소나 조회 성공: {persona_id} -> {persona_data.name}"
                )
                return persona_data.system_prompt

            except Exception as e:
                logger.error(f"❌ 페르소나 조회 실패: {e}")
                raise

    async def filter_chunks_for_persona(
        self,
        chunks: List[Dict[str, Any]],
        persona_id: int,
        filter_score: float = 0.7,
    ) -> Dict[str, Any]:
        """
        페르소나에 맞게 청크 필터링

        Args:
            chunks: 필터링할 청크 리스트
            persona_id: 페르소나 ID
            filter_score: 필터링 임계값 (0.0~1.0, 기본값 0.7)

        Returns:
            필터링 결과
        """
        # 페르소나 데이터 직접 조회로 system_prompt 획득
        logger.info(f"🔍 페르소나 데이터 조회: persona_id={persona_id}")
        system_prompt = await self.resolve_persona_system_prompt(persona_id)

        if not system_prompt:
            logger.error("❌ system_prompt 없음: DB에 프롬프트가 비어있음")
            raise ValueError("Empty system_prompt for persona")

        # system_prompt 중심의 페르소나 컨텍스트 구성
        persona_dict = {
            "name": f"persona_{persona_id}",
            "system_prompt": system_prompt,
            "filter_score": filter_score,
        }

        logger.info(f"📊 필터링 점수: {filter_score}")
        logger.info(
            f"🧠 RAG Agent(LLM) 호출 준비: persona_id={persona_id}, chunks={len(chunks)}, filter_score={filter_score}"
        )

        # LLM 기반 필터링
        filter_results = await self.filter_agent.filter_chunks_for_persona(
            chunks=chunks, persona=persona_dict
        )
        logger.info(
            "🧠 RAG Agent(LLM) 호출 완료: 결과 %d개, is_relevant True=%d개",
            len(filter_results),
            sum(1 for r in filter_results if r.is_relevant),
        )

        # 모든 청크의 필터링 결과를 개별적으로 로깅 (첫 번째 청크뿐만 아니라 모든 청크)
        try:
            for i, result in enumerate(filter_results):
                chunk = chunks[i] if i < len(chunks) else {}
                hash_sha256 = chunk.get("hash_sha256", "unknown")[:16]  # 해시 앞 16자
                decision = "EMBED" if result.is_relevant else "SKIP"

                # 결정 사유 생성 (실제 필터링 경로 기반)
                if result.is_relevant:
                    reason = f"score={result.relevance_score:.2f} 임계값({filter_score}) 초과"
                else:
                    reason = f"score={result.relevance_score:.2f} 임계값({filter_score}) 미달"

                # LLM 응답의 reasoning이 있으면 추가 (160자 제한)
                if result.reasoning:
                    llm_reason = " ".join(result.reasoning.replace("\n", " ").split())[
                        :80
                    ]
                    reason = f"{reason}, {llm_reason}"

                # 청크별 필터링 결과 로그 (한 줄)
                logger.info(
                    "🟪 persona_filter: hash=%s decision=%s reason=%s",
                    hash_sha256,
                    decision,
                    reason[:160],
                )
        except Exception:
            # 로깅 실패는 메인 플로우에 영향 없음
            pass

        # 관련성 있는 청크만 선별
        relevant_chunks = [
            chunks[i] for i, result in enumerate(filter_results) if result.is_relevant
        ]

        # 비용 절감 효과 계산
        cost_reduction = await self.filter_agent.estimate_cost_reduction(
            total_chunks=len(chunks), selected_chunks=len(relevant_chunks)
        )

        logger.info(
            f"✅ 페르소나 필터링 완료: 총 {len(chunks)}개 중 {len(relevant_chunks)}개 선택 "
            f"(절감률: {cost_reduction['reduction_rate']}%)"
        )

        # ChunkFilterResult 형식으로 반환
        return {
            "relevant_chunks": relevant_chunks,
            "total_count": len(chunks),
            "selected_count": len(relevant_chunks),
            "reduction_rate": cost_reduction["reduction_rate"],
            "cost_reduction": cost_reduction,
        }


class _PersonaFilterLLMClient:
    """페르소나 필터용 LLM 클라이언트 어댑터.

    generate(prompt) -> str 형태의 인터페이스를 제공한다.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = model or os.getenv("PERSONA_FILTER_MODEL")

    async def generate(self, prompt: str) -> str:
        """LLM에 프롬프트를 전달하고 JSON 문자열 응답을 반환한다."""
        try:
            logger.info(
                f"🧠 LLM 호출 시작: model={self._model}, prompt_len={len(prompt)}"
            )
            # OpenAI Chat Completions를 동기 → 스레드 오프로딩하여 호출
            # OpenAI의 json_object 사용 요건 충족을 위해 messages 내에 'json' 단어를 명시
            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "응답은 json 형식의 객체만 출력하세요.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=2048,
                temperature=0.0,
            )
            content = response.choices[0].message.content
            logger.info("🧠 LLM 호출 성공: 응답 수신")
            return content
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            raise
