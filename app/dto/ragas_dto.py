"""RAGAS 평가 요청/응답 DTO"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class RagasDatasetItem(BaseModel):
    """골든 데이터셋 개별 항목"""

    id: int
    user_input: str
    category: str
    reference_contexts: List[str]
    reference_pages: List[int]
    source_document: str
    response: Optional[str] = None

    @model_validator(mode="after")
    def _validate_contexts_pages_length(self) -> "RagasDatasetItem":
        if len(self.reference_contexts) != len(self.reference_pages):
            raise ValueError(
                f"reference_contexts({len(self.reference_contexts)})와 "
                f"reference_pages({len(self.reference_pages)})의 길이가 다릅니다"
            )
        return self

    @classmethod
    def from_excel_row(
        cls,
        id: int,
        user_input: str,
        category: str,
        reference_context_1: Optional[str],
        reference_page_1: Optional[int] = None,
        reference_context_2: Optional[str] = None,
        reference_page_2: Optional[int] = None,
        reference_context_3: Optional[str] = None,
        reference_page_3: Optional[int] = None,
        source_document: str = "",
        response: Optional[str] = None,
    ) -> "RagasDatasetItem":
        """Excel 행에서 context/page 쌍을 리스트로 병합하여 생성"""
        pairs = [
            (reference_context_1, reference_page_1),
            (reference_context_2, reference_page_2),
            (reference_context_3, reference_page_3),
        ]
        contexts = []
        pages = []
        for ctx, page in pairs:
            if ctx is not None:
                contexts.append(ctx)
                pages.append(page)
        return cls(
            id=id,
            user_input=user_input,
            category=category,
            reference_contexts=contexts,
            reference_pages=pages,
            source_document=source_document,
            response=response,
        )


class RagasEvalRequestParams(BaseModel):
    """RAGAS 평가 요청 시 검색 설정 파라미터"""

    search_mode: Literal["hybrid", "dense"] = Field(default="hybrid", description="검색 모드")
    limit: int = Field(default=10, ge=1, le=100, description="검색 결과 수")
    dense_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Dense 가중치")
    sparse_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Sparse 가중치")
    reranker: Optional[str] = Field(default=None, description="flashrank / cohere")
    rerank_top_n: int = Field(default=10, ge=1, le=50, description="Reranker 최종 반환 수")
    use_multi_query: bool = Field(default=False, description="LLM 쿼리 확장")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="유사도 커트라인 (0.0~1.0, 미만 결과 제외)")


class RagasItemResult(BaseModel):
    """개별 질문 평가 결과"""

    id: int
    user_input: str
    category: str
    source_document: str
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    response: Optional[str] = None
    retrieved_contexts: List[str] = Field(default_factory=list)
    num_results: int = 0


class RagasEvalStartResponseDTO(BaseModel):
    """RAGAS 평가 시작 응답 DTO (비동기)"""

    evaluation_id: int = Field(description="평가 ID")
    status: str = Field(default="pending", description="평가 상태")


class RagasEvalDeleteResponseDTO(BaseModel):
    """RAGAS 평가 삭제 응답 DTO"""

    id: int = Field(description="삭제된 평가 ID")
    deleted: bool = Field(default=True, description="삭제 여부")


class RagasEvaluationListItemDTO(BaseModel):
    """RAGAS 평가 목록 항목 DTO"""

    id: int
    status: str
    eval_mode: str
    llm_model: str
    summary: Optional[Dict[str, Any]] = None
    search_config: Dict[str, Any]
    total_items: Optional[int] = None
    duration_seconds: Optional[int] = None
    dataset_filename: Optional[str] = None
    created_at: Any
    completed_at: Optional[Any] = None


class RagasEvaluationListResponseDTO(BaseModel):
    """RAGAS 평가 목록 응답 DTO"""

    evaluations: List[RagasEvaluationListItemDTO]
    pagination: Dict[str, Any]


class RagasEvaluationDetailItemDTO(BaseModel):
    """RAGAS 평가 상세 개별 질문 결과 DTO"""

    item_id: int
    user_input: str
    category: str
    source_document: str
    source_document_hash: Optional[str] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    response: Optional[str] = None
    reference_contexts: Optional[List[Dict[str, Any]]] = None
    retrieved_contexts: Optional[List[str]] = None
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    num_results: Optional[int] = None


class RagasEvaluationDetailResponseDTO(BaseModel):
    """RAGAS 평가 상세 응답 DTO"""

    id: int
    status: str
    eval_mode: str
    llm_model: str
    summary: Optional[Dict[str, Any]] = None
    by_document: Optional[Dict[str, Any]] = None
    by_category: Optional[Dict[str, Any]] = None
    search_config: Optional[Dict[str, Any]] = None
    total_items: Optional[int] = None
    duration_seconds: Optional[int] = None
    dataset_filename: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    created_at: Any
    details: Optional[List[RagasEvaluationDetailItemDTO]] = None
