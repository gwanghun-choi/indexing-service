"""
Graph RAG 관련 DTO
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class GraphSearchRequestDTO(BaseModel):
    """그래프 검색 요청 DTO"""

    query: str = Field(..., description="검색 쿼리")
    group_id: int = Field(..., description="그룹 ID")
    total_role: List[int] = Field(..., description="역할 ID 목록")
    max_hops: int = Field(
        default=1,
        ge=0,
        le=2,
        description="관계 추적 최대 홉 수 (0: 엔티티만, 1: 1홉, 2: 2홉)",
    )
    entity_types: Optional[List[str]] = Field(
        default=None, description="필터링할 엔티티 타입 (None이면 전체)"
    )


class GraphNodeDTO(BaseModel):
    """그래프 노드 정보"""

    hash_sha256: str = Field(..., description="문서 해시")
    distance: int = Field(..., description="원본 노드로부터의 거리 (홉 수)")
    relation_type: Optional[str] = Field(
        default=None,
        description="관계 유형 (authored_by, same_category, same_project, entity)",
    )
    source_hash: Optional[str] = Field(
        default=None, description="이 노드로 연결된 출발지 해시"
    )


class GraphSearchResultDTO(BaseModel):
    """그래프 검색 결과"""

    nodes: List[GraphNodeDTO] = Field(
        default_factory=list, description="발견된 노드 목록"
    )
    total_nodes: int = Field(default=0, description="총 노드 수")
    entity_matches: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="매칭된 엔티티 (entity_name -> [hash1, hash2, ...])",
    )


class QueryAnalysisDTO(BaseModel):
    """질문 분석 결과"""

    query_type: Literal["simple", "ambiguous", "relational", "complex"] = Field(
        ...,
        description="질문 유형 - simple: 단순 검색, ambiguous: 모호한 질문, relational: 관계 기반, complex: 복합 질문",
    )
    reasoning: str = Field(..., description="판단 이유")
    extracted_entities: List[str] = Field(
        default_factory=list, description="추출된 엔티티 목록"
    )
    recommended_strategy: Literal["hybrid_only", "hybrid_with_graph", "graph_only"] = (
        Field(..., description="추천 검색 전략")
    )


class LangGraphStateDTO(BaseModel):
    """LangGraph 워크플로우 상태"""

    query: str = Field(..., description="원본 쿼리")
    query_analysis: Optional[QueryAnalysisDTO] = Field(
        default=None, description="질문 분석 결과"
    )
    hybrid_results: List[Dict[str, Any]] = Field(
        default_factory=list, description="하이브리드 검색 결과"
    )
    graph_results: List[Dict[str, Any]] = Field(
        default_factory=list, description="그래프 검색 결과"
    )
    final_results: List[Dict[str, Any]] = Field(
        default_factory=list, description="최종 통합 결과"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="메타데이터 (실행 통계 등)"
    )


# ============================================================
# Entity Type DTOs (Admin 관리용)
# ============================================================


class EntityTypeDTO(BaseModel):
    """엔티티 타입 DTO"""

    id: Optional[int] = None
    type_key: str = Field(..., description="타입 키 (person, organization, ...)")
    type_name: str = Field(..., description="타입 이름 (인물, 조직, ...)")
    description: Optional[str] = Field(None, description="타입 설명")


class EntityTypeCreateRequestDTO(BaseModel):
    """엔티티 타입 생성 요청"""

    type_key: str = Field(..., description="타입 키")
    type_name: str = Field(..., description="타입 이름")
    description: Optional[str] = Field(None, description="타입 설명")


class EntityTypeUpdateRequestDTO(BaseModel):
    """엔티티 타입 수정 요청"""

    type_name: Optional[str] = Field(None, description="타입 이름")
    description: Optional[str] = Field(None, description="타입 설명")


# ============================================================
# Dual-Level Search DTOs (LightRAG 기반)
# ============================================================


class DualLevelSearchRequestDTO(BaseModel):
    """Dual-Level 그래프 검색 요청"""

    query: str = Field(..., description="검색 쿼리")
    max_hops: int = Field(
        default=1, ge=0, le=3, description="최대 탐색 홉 수 (0-3)"
    )
    relation_types: Optional[List[str]] = Field(
        None, description="필터링할 관계 타입"
    )


class DualLevelSearchResponseDTO(BaseModel):
    """Dual-Level 그래프 검색 응답"""

    keywords: Dict[str, List[str]] = Field(
        ..., description="추출된 키워드 (low_level, high_level)"
    )
    entity_matches: List[Dict[str, Any]] = Field(
        default_factory=list, description="매칭된 엔티티 목록"
    )
    graph_results: List[Dict[str, Any]] = Field(
        default_factory=list, description="그래프 탐색 결과"
    )
    total_results: int = Field(default=0, description="총 결과 수")


class EntitySearchRequestDTO(BaseModel):
    """엔티티 검색 요청"""

    query: str = Field(..., description="검색 쿼리")
    entity_type: Optional[str] = Field(None, description="엔티티 타입 필터")
    limit: int = Field(default=20, ge=1, le=100, description="결과 수 제한")


class GraphVisualizationRequestDTO(BaseModel):
    """그래프 시각화 데이터 요청"""

    entity_name: Optional[str] = Field(None, description="중심 엔티티 이름")
    hash_sha256: Optional[str] = Field(None, description="문서 해시")
    max_nodes: int = Field(default=50, ge=10, le=200, description="최대 노드 수")
    max_hops: int = Field(default=2, ge=1, le=3, description="최대 홉 수")
