"""
MCP 배포 관련 DTO

Retrieval MCP 개인 인스턴스 배포를 위한 요청/응답 DTO를 정의합니다.
"""

from typing import Optional, List, Literal

from pydantic import BaseModel, Field


class RetrievalSecretsDTO(BaseModel):
    """유사도 검색 옵션 DTO (secrets 필드)"""

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="반환 결과 수 (1~100)",
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="유사도 threshold (0.0~1.0)",
    )
    search_mode: Literal["hybrid", "dense"] = Field(
        default="hybrid",
        description="검색 모드 (hybrid | dense)",
    )
    dense_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Dense 가중치 (0.0~1.0)",
    )
    sparse_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Sparse 가중치 (0.0~1.0)",
    )
    use_multi_query: bool = Field(
        default=False,
        description="MultiQuery 사용 여부",
    )
    reranker: Optional[Literal["cohere", "flashrank"]] = Field(
        default=None,
        description="Reranker 선택 (null | cohere | flashrank)",
    )
    rerank_top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Reranker 반환 개수 (1~50)",
    )
    cohere_api_key: Optional[str] = Field(
        default=None,
        description="Cohere API 키 (선택)",
    )
    graph_search_enabled: bool = Field(
        default=False,
        description="Graph RAG 활성화",
    )
    max_hops: int = Field(
        default=1,
        ge=0,
        le=2,
        description="그래프 홉 수 (0~2)",
    )
    category_filter: Optional[List[str]] = Field(
        default=None,
        description="카테고리 필터 (선택)",
    )
    hash_sha256_filter: Optional[List[str]] = Field(
        default=None,
        description="해시값 필터 (선택)",
    )


class RetrievalDeployRequestDTO(BaseModel):
    """Retrieval MCP 배포 요청 DTO"""

    secrets: RetrievalSecretsDTO = Field(
        ...,
        description="유사도 검색 옵션",
    )
    config_id: Optional[int] = Field(
        default=None,
        description="설정 ID (업데이트시 필수, 신규 배포시 생략)",
    )
    config_name: str = Field(
        default="retrieval-config",
        min_length=1,
        max_length=255,
        description="설정 이름",
    )


class RetrievalDeployResponseDTO(BaseModel):
    """Retrieval MCP 배포 응답 DTO"""

    success: bool = Field(
        ...,
        description="배포 성공 여부",
    )
    message: str = Field(
        ...,
        description="결과 메시지",
    )
    config_id: Optional[int] = Field(
        default=None,
        description="생성/업데이트된 설정 ID",
    )
    tool_id: Optional[int] = Field(
        default=None,
        description="도구 ID",
    )

