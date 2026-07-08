"""
LightRAG 서비스

엔티티/관계 추출 + Dual-Level 키워드 추출 (Low-level, High-level)
Admin이 관리하는 엔티티 타입을 실시간으로 DB에서 조회하여 프롬프트에 적용
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config.settings import get_settings
from app.crud.postgres.entity_type_crud import select_entity_types_for_prompt

logger = logging.getLogger(__name__)


def _get_entity_extraction_prompt(entity_types_str: str) -> str:
    """
    엔티티/관계 추출 시스템 프롬프트 생성

    Args:
        entity_types_str: DB에서 조회한 엔티티 타입 문자열 (예: "person(인물), organization(조직), ...")

    Returns:
        str: 시스템 프롬프트
    """
    return f"""You are an expert entity and relationship extractor. Analyze the given text and extract:

1. **Entities**: Named entities with their types
   Supported entity types: {entity_types_str}

2. **Relations**: Relationships between extracted entities
   Relationship format: (source_entity, relation_type, target_entity)
   Common relation types: works_at, belongs_to, manages, participates_in, located_in, related_to, authored_by, mentions

IMPORTANT RULES:
- Extract only explicitly mentioned entities
- Entity names should be normalized (remove unnecessary prefixes/suffixes)
- Relations must reference entities that exist in the extracted list
- Use Korean entity names when the source text is in Korean

Response format (JSON):
```json
{{
  "entities": [
    {{"type": "person", "name": "홍길동", "context": "프로젝트 리더"}},
    {{"type": "organization", "name": "개발팀", "context": "소속 부서"}}
  ],
  "relations": [
    {{"source": "홍길동", "relation": "belongs_to", "target": "개발팀"}}
  ]
}}
```"""


def _get_dual_level_keyword_prompt() -> str:
    """
    Dual-Level 키워드 추출 시스템 프롬프트

    LightRAG 논문 기반:
    - Low-level: 구체적인 엔티티, 사실 정보 (who, what, when, where)
    - High-level: 추상적인 주제, 관계, 개념 (why, how, themes)

    Returns:
        str: 시스템 프롬프트
    """
    return """You are an expert keyword extractor using Dual-Level extraction strategy.

Extract TWO types of keywords from the query:

1. **Low-level Keywords** (Specific, Factual):
   - Specific entity names (people, organizations, products)
   - Concrete facts and data points
   - Specific dates, numbers, locations
   - Direct answers to: WHO, WHAT, WHEN, WHERE

2. **High-level Keywords** (Abstract, Conceptual):
   - Themes and topics
   - Abstract concepts and relationships
   - Processes and methodologies
   - Answers to: WHY, HOW, THEMES, PATTERNS

RULES:
- Each level should have 1-5 keywords
- Keywords should be in the same language as the query
- Low-level keywords are for precise entity matching
- High-level keywords are for semantic/relationship exploration

Response format (JSON):
```json
{
  "low_level_keywords": ["홍길동", "마케팅팀", "2024년 1분기"],
  "high_level_keywords": ["매출 성장 전략", "팀 협업 프로세스", "분기별 성과"],
  "reasoning": "Brief explanation of keyword selection"
}
```"""


async def extract_entities_and_relations(
    text: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """
    텍스트에서 엔티티와 관계 추출

    Admin이 관리하는 엔티티 타입을 DB에서 실시간 조회하여 프롬프트에 적용

    Args:
        text: 분석할 텍스트
        model: 사용할 LLM 모델
        temperature: 생성 온도

    Returns:
        Dict: {
            "entities": [{"type": str, "name": str, "context": str}, ...],
            "relations": [{"source": str, "relation": str, "target": str}, ...],
            "raw_response": str
        }
    """
    try:
        settings = get_settings()

        # 실시간으로 DB에서 엔티티 타입 조회
        entity_types_str = await select_entity_types_for_prompt()
        logger.debug(f"조회된 엔티티 타입: {entity_types_str}")

        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
        )

        system_prompt = _get_entity_extraction_prompt(entity_types_str)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Text to analyze:\n\n{text}"),
        ]

        response = llm.invoke(messages)
        content = response.content

        # JSON 추출
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        result = json.loads(content)

        entities = result.get("entities", [])
        relations = result.get("relations", [])

        logger.info(
            f"엔티티/관계 추출 완료 - 엔티티: {len(entities)}개, 관계: {len(relations)}개"
        )

        return {
            "entities": entities,
            "relations": relations,
            "raw_response": response.content,
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}")
        return {
            "entities": [],
            "relations": [],
            "raw_response": content if "content" in dir() else "",
            "error": str(e),
        }

    except Exception as e:
        logger.error(f"엔티티/관계 추출 중 오류: {e}", exc_info=True)
        return {
            "entities": [],
            "relations": [],
            "raw_response": "",
            "error": str(e),
        }


async def extract_dual_level_keywords(
    query: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """
    쿼리에서 Dual-Level 키워드 추출 (LightRAG 방식)

    - Low-level: 구체적 엔티티 (엔티티 검색용)
    - High-level: 추상적 주제 (관계 탐색용)

    Args:
        query: 검색 쿼리
        model: 사용할 LLM 모델
        temperature: 생성 온도

    Returns:
        Dict: {
            "low_level_keywords": List[str],
            "high_level_keywords": List[str],
            "reasoning": str
        }
    """
    try:
        settings = get_settings()

        llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
        )

        system_prompt = _get_dual_level_keyword_prompt()

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Query: {query}"),
        ]

        response = llm.invoke(messages)
        content = response.content

        # JSON 추출
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        result = json.loads(content)

        low_level = result.get("low_level_keywords", [])
        high_level = result.get("high_level_keywords", [])
        reasoning = result.get("reasoning", "")

        logger.info(
            f"Dual-Level 키워드 추출 완료 - "
            f"Low-level: {low_level}, High-level: {high_level}"
        )

        return {
            "low_level_keywords": low_level,
            "high_level_keywords": high_level,
            "reasoning": reasoning,
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}")
        # 폴백: 쿼리 자체를 키워드로 사용
        return {
            "low_level_keywords": [query],
            "high_level_keywords": [],
            "reasoning": f"파싱 오류로 인해 원본 쿼리 사용: {str(e)}",
        }

    except Exception as e:
        logger.error(f"Dual-Level 키워드 추출 중 오류: {e}", exc_info=True)
        return {
            "low_level_keywords": [query],
            "high_level_keywords": [],
            "reasoning": f"오류 발생: {str(e)}",
        }


async def search_graph_with_dual_level(
    query: str,
    group_id: int,
    max_hops: int = 1,
    relation_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Dual-Level 키워드를 활용한 그래프 검색

    1. 쿼리에서 Dual-Level 키워드 추출
    2. Low-level 키워드로 엔티티 검색 (정확 매칭)
    3. High-level 키워드로 관계 탐색 (의미 기반)
    4. 결과 통합 및 Multi-hop 탐색

    Args:
        query: 검색 쿼리
        group_id: 그룹 ID
        max_hops: 최대 탐색 홉 수
        relation_types: 필터링할 관계 타입 (None이면 전체)

    Returns:
        Dict: {
            "keywords": {
                "low_level": List[str],
                "high_level": List[str]
            },
            "entity_matches": List[Dict],
            "graph_results": List[Dict],
            "total_results": int
        }
    """
    # 지연 임포트로 순환 참조 방지
    from app.crud.milvus import search_entities

    try:
        # 1. Dual-Level 키워드 추출
        keyword_result = await extract_dual_level_keywords(query)
        low_level_keywords = keyword_result.get("low_level_keywords", [])
        high_level_keywords = keyword_result.get("high_level_keywords", [])

        logger.info(
            f"Dual-Level 검색 시작 - "
            f"Low: {low_level_keywords}, High: {high_level_keywords}"
        )

        entity_matches = []
        graph_results = []

        # 2. Low-level 키워드로 엔티티 검색
        for keyword in low_level_keywords:
            entities = await search_entities(
                query=keyword,
                group_id=group_id,
                limit=10,
            )
            for entity in entities:
                if entity not in entity_matches:
                    entity_matches.append(entity)

        logger.debug(f"Low-level 엔티티 매칭: {len(entity_matches)}개")

        # 3. 관계 기반 그래프 탐색은 비활성화됨 (관계 CRUD 제거)

        # 4. High-level 키워드로 추가 의미 검색 (향후 확장용)
        # 현재는 Low-level 기반 검색 결과만 반환
        # TODO: High-level 키워드를 이용한 의미 기반 관계 탐색 구현

        logger.info(
            f"Dual-Level 검색 완료 - "
            f"엔티티 매칭: {len(entity_matches)}개, "
            f"그래프 결과: {len(graph_results)}개"
        )

        return {
            "keywords": {
                "low_level": low_level_keywords,
                "high_level": high_level_keywords,
            },
            "entity_matches": entity_matches,
            "graph_results": graph_results,
            "total_results": len(graph_results),
        }

    except Exception as e:
        logger.error(f"Dual-Level 그래프 검색 중 오류: {e}", exc_info=True)
        return {
            "keywords": {
                "low_level": [],
                "high_level": [],
            },
            "entity_matches": [],
            "graph_results": [],
            "total_results": 0,
            "error": str(e),
        }

