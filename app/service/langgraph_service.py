"""
LangGraph 워크플로우 서비스
질문 분석 및 Graph RAG 검색
"""

import gc
import json
import logging
import re
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from app.config.settings import get_settings
from app.crud.milvus.search_crud import HybridSearchService

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """워크플로우 상태 타입"""

    query: str
    query_analysis: Optional[Dict[str, Any]]
    final_results: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    group_id: int
    total_role: List[int]
    limit: int
    search_mode: str
    dense_weight: float
    sparse_weight: float
    rerank_top_n: int
    use_multi_query: bool
    threshold: float
    user_passport: str
    category_filter: Optional[List[str]]
    hash_sha256_filter: Optional[List[str]]
    reranker: Optional[str]
    cohere_api_key: Optional[str]
    max_hops: int


QUERY_ANALYSIS_PROMPT = """Analyze user query using Dual-Level Keyword Extraction and return JSON with:

1. query_type (simple/ambiguous/relational/complex):
   - simple: Clear keyword-based ("2024 vacation policy")
   - ambiguous: Vague/abstract ("recommend good docs")
   - relational: Relationship-focused ("docs related to A", "other docs by B")
   - complex: Multiple conditions or complex reasoning

2. reasoning: Brief explanation (one sentence)

3. low_level_keywords: Specific, factual keywords (WHO, WHAT, WHEN, WHERE)
   - Entity names (people, organizations, products)
   - Specific dates, numbers, locations
   - Concrete facts and data points
   Example: ["김철수", "마케팅팀", "2024년 1분기"]

4. high_level_keywords: Abstract, conceptual keywords (WHY, HOW, THEMES)
   - Themes and topics
   - Abstract concepts and relationships
   - Processes and methodologies
   Example: ["매출 성장 전략", "팀 협업 프로세스"]

5. extracted_entities: List of entities with type and name
   Supported types: person, organization, project, location, event, concept, document, date
   Format: [{"type": "person", "name": "김철수"}, {"type": "organization", "name": "개발팀"}]

Response format:
```json
{
  "query_type": "...",
  "reasoning": "...",
  "low_level_keywords": ["...", ...],
  "high_level_keywords": ["...", ...],
  "extracted_entities": [{"type": "...", "name": "..."}, ...]
}
```"""


class LangGraphService:
    """
    LangGraph 워크플로우 서비스

    질문 분석 → Graph RAG 검색
    """

    def __init__(self):
        """초기화"""
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,
            api_key=self.settings.OPENAI_API_KEY,
        )
        self.hybrid_service = HybridSearchService()
        self.workflow = self._create_workflow()
        logger.info("✅ LangGraphService 초기화 완료")

    def cleanup(self):
        """리소스 정리 및 가비지 컬렉션"""
        if self.hybrid_service:
            self.hybrid_service.cleanup()
        gc.collect()
        logger.info("✅ LangGraphService 리소스 정리 및 GC 완료")

    def _create_workflow(self) -> StateGraph:
        """LangGraph 워크플로우 생성"""
        workflow = StateGraph(WorkflowState)
        workflow.add_node("analyze_query", self._analyze_query_node)
        workflow.add_node("unified_search", self._unified_search_node)
        workflow.set_entry_point("analyze_query")
        workflow.add_edge("analyze_query", "unified_search")
        workflow.add_edge("unified_search", END)
        return workflow.compile()

    def _analyze_query_node(self, state: WorkflowState) -> Dict[str, Any]:
        """질문 분석 노드 - Dual-Level Keyword Extraction"""
        messages = None
        response = None

        try:
            query = state["query"]
            logger.info(f"🔍 질문 분석 시작: '{query[:50]}...'")

            messages = [
                SystemMessage(content=QUERY_ANALYSIS_PROMPT),
                HumanMessage(content=f"Query: {query}"),
            ]

            response = self.llm.invoke(messages)
            content = response.content

            # JSON 추출 (마크다운 코드 블록 제거)
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
            if json_match:
                content = json_match.group(1)

            analysis = json.loads(content)

            logger.info(
                f"✅ 질문 분석 완료 - 유형: {analysis['query_type']}, "
                f"Low: {analysis['low_level_keywords']}, "
                f"High: {analysis['high_level_keywords']}"
            )

            return {"query_analysis": analysis}

        except Exception as e:
            logger.error(f"질문 분석 중 오류 발생: {e}", exc_info=True)
            return {
                "query_analysis": {
                    "query_type": "simple",
                    "reasoning": f"분석 오류: {str(e)}",
                    "low_level_keywords": [],
                    "high_level_keywords": [],
                    "extracted_entities": [],
                }
            }

        finally:
            if messages:
                del messages
            if response:
                del response

    async def _unified_search_node(self, state: WorkflowState) -> Dict[str, Any]:
        """통합 검색 노드 - Meta + Graph 해시 병합 → Vector 청크 검색 → BM25"""
        try:
            analysis = state["query_analysis"]
            low_level_keywords = analysis["low_level_keywords"]
            high_level_keywords = analysis["high_level_keywords"]
            extracted_entities = analysis["extracted_entities"]

            # Low-level 키워드 + 엔티티 이름 결합
            graph_entity_keywords = list(low_level_keywords)
            for entity in extracted_entities:
                if isinstance(entity, dict) and "name" in entity:
                    name = entity["name"]
                    if name not in graph_entity_keywords:
                        graph_entity_keywords.append(name)

            logger.info(
                f"🕸️ Graph RAG 검색 - Low: {low_level_keywords}, "
                f"High: {high_level_keywords}, Keywords: {graph_entity_keywords}"
            )

            # HybridSearchService 호출 (Graph RAG 포함)
            results = await self.hybrid_service.search(
                query=state["query"],
                group_id=state["group_id"],
                total_role=state["total_role"],
                limit=state["limit"],
                search_mode=state["search_mode"],
                dense_weight=state["dense_weight"],
                sparse_weight=state["sparse_weight"],
                rerank_top_n=state["rerank_top_n"],
                use_multi_query=state["use_multi_query"],
                threshold=state["threshold"],
                user_passport=state["user_passport"],
                category_filter=state["category_filter"],
                hash_sha256_filter=state["hash_sha256_filter"],
                reranker=state["reranker"],
                cohere_api_key=state["cohere_api_key"],
                include_graph_search=True,
                graph_entity_keywords=graph_entity_keywords if graph_entity_keywords else None,
                graph_max_hops=state["max_hops"],
            )

            logger.info(f"✅ 통합 검색 완료: {len(results)}개 결과")

            # graph_info가 있는 결과 수 카운트
            graph_info_count = sum(1 for r in results if "graph_info" in r)

            return {
                "final_results": results,
                "metadata": {
                    "total_count": len(results),
                    "graph_info_count": graph_info_count,
                },
            }

        except Exception as e:
            logger.error(f"통합 검색 중 오류 발생: {e}", exc_info=True)
            return {
                "final_results": [],
                "metadata": {"error": str(e)},
            }

    async def run(
        self,
        query: str,
        group_id: int,
        total_role: List[int],
        limit: int,
        search_mode: str,
        dense_weight: float,
        sparse_weight: float,
        rerank_top_n: int,
        use_multi_query: bool,
        threshold: float,
        user_passport: str,
        category_filter: Optional[List[str]],
        hash_sha256_filter: Optional[List[str]],
        reranker: Optional[str],
        cohere_api_key: Optional[str],
        max_hops: int,
    ) -> Dict[str, Any]:
        """
        워크플로우 실행

        Args:
            query: 검색 쿼리
            group_id: 그룹 ID
            total_role: 역할 ID 목록
            limit: 결과 수
            search_mode: 검색 모드
            dense_weight: Dense 가중치
            sparse_weight: Sparse 가중치
            rerank_top_n: Rerank 개수
            use_multi_query: MultiQuery 사용 여부
            threshold: 점수 임계값
            category_filter: 카테고리 필터
            hash_sha256_filter: 해시 필터
            reranker: Reranker 선택
            cohere_api_key: Cohere API 키
            max_hops: 최대 홉 수

        Returns:
            최종 결과
        """
        try:
            logger.info(f"🚀 LangGraph 워크플로우 시작 - 쿼리: '{query[:50]}...'")

            initial_state: WorkflowState = {
                "query": query,
                "query_analysis": None,
                "final_results": [],
                "metadata": {},
                "group_id": group_id,
                "total_role": total_role,
                "limit": limit,
                "search_mode": search_mode,
                "dense_weight": dense_weight,
                "sparse_weight": sparse_weight,
                "rerank_top_n": rerank_top_n,
                "use_multi_query": use_multi_query,
                "threshold": threshold,
                "user_passport": user_passport,
                "category_filter": category_filter,
                "hash_sha256_filter": hash_sha256_filter,
                "reranker": reranker,
                "cohere_api_key": cohere_api_key,
                "max_hops": max_hops,
            }

            final_state = await self.workflow.ainvoke(initial_state)

            logger.info("✅ LangGraph 워크플로우 완료")

            return {
                "results": final_state["final_results"],
                "query_analysis": final_state["query_analysis"],
                "metadata": final_state["metadata"],
            }

        except Exception as e:
            logger.error(f"워크플로우 실행 중 오류 발생: {e}", exc_info=True)
            return {
                "results": [],
                "query_analysis": None,
                "metadata": {"error": str(e)},
            }
