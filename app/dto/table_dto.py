from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# -- Document Management Response DTOs --
class DocumentCategoryResponseDTO(BaseModel):
    """문서 카테고리 응답 DTO"""

    category_id: int = Field(..., description="카테고리 ID")
    category_name: str = Field(..., description="카테고리 이름")
    retention_period: int = Field(..., description="보관 기간 (일)")
    description: str = Field(..., description="카테고리 설명")
    total_size: int = Field(..., description="총 용량 (바이트)")
    document_count: int = Field(..., description="문서 개수")

    class Config:
        json_schema_extra = {
            "example": {
                "category_id": 1,
                "category_name": "계약서",
                "retention_period": 365,
                "description": "각종 계약 관련 문서",
                "total_size": 52428800,
                "document_count": 15,
            }
        }


class DocumentMetaResponseDTO(BaseModel):
    """문서 메타데이터 응답 DTO"""

    id: int = Field(..., description="문서 ID")
    category: str = Field(..., description="문서 카테고리")
    title: str = Field(..., description="문서 제목")
    filename: str = Field(..., description="파일명")
    summary: str = Field(..., description="문서 요약")
    file_type: str = Field(..., description="파일 타입")
    file_size: int = Field(..., description="파일 크기 (바이트)")
    status: str = Field(..., description="업로드 상태")
    role_ids: List[int] = Field(..., description="역할 ID 리스트")
    persona_id: int = Field(..., description="페르소나 ID")
    file_path: str = Field(..., description="파일 경로")
    download_url: str = Field(..., description="다운로드 URL")
    chunk_count: int = Field(..., description="청크 개수")
    token: int = Field(..., description="토큰 사용량")
    cost: float = Field(..., description="비용 (달러)")
    summary_token: int = Field(..., description="요약 토큰 사용량")
    summary_cost: float = Field(..., description="요약 비용 (달러)")
    group_id: int = Field(..., description="그룹 ID")
    user_id: int = Field(..., description="사용자 ID")
    user_full_name: str = Field(..., description="사용자 이름")
    hash_sha256: str = Field(..., description="파일 해시값")
    start_date: int = Field(..., description="작업 시작일 (Unix timestamp)")
    end_date: int = Field(..., description="작업 종료일 (Unix timestamp)")
    expiration_date: int = Field(..., description="문서 만료일 (Unix timestamp)")
    anonymization_strategy: Optional[str] = Field(
        None,
        description="PII 비식별화 전략 (none, masking, pseudonymization, generalization)",
    )
    ref_count: int = Field(default=0, description="문서 참조 횟수")
    chunk_size: int = Field(..., description="청크 크기")
    chunk_overlap: int = Field(..., description="청크 오버랩 크기")
    enable_pii_anonymization: int = Field(
        ..., description="PII 비식별화 활성화 여부 (0=비활성, 1=활성)"
    )
    pii_types: Optional[str] = Field(
        None, description="비식별화 대상 PII 유형 (쉼표 구분)"
    )
    original_chunk_count: int = Field(..., description="필터링 전 청크 개수")
    filtered_chunk_count: int = Field(..., description="필터링 후 청크 개수")
    embedding_start_date: int = Field(
        ..., description="임베딩 시작 시간 (Unix timestamp)"
    )
    embedding_end_date: int = Field(
        ..., description="임베딩 종료 시간 (Unix timestamp)"
    )
    entities: List[Dict[str, str]] = Field(
        default_factory=list,
        description="추출된 엔티티 목록 (Graph RAG)",
    )
    entity_types: List[str] = Field(
        default_factory=list,
        description="엔티티 타입 목록 (Graph RAG)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "category": "계약서",
                "title": "2024년 근로계약서",
                "filename": "근로계약서_2024_김철수.pdf",
                "summary": "본 계약서는 2024년도 정규직 근로자의 고용 조건을 명시합니다...",
                "file_type": "pdf",
                "file_size": 1048576,
                "status": "completed",
                "role_ids": [3],
                "persona_id": 1,
                "file_path": "contracts/2024/employment/kim_chulsoo.pdf",
                "download_url": "https://storage.example.com/contracts/2024/kim_chulsoo.pdf",
                "chunk_count": 15,
                "token": 3500,
                "cost": 0.035,
                "summary_token": 500,
                "summary_cost": 0.005,
                "group_id": 101,
                "user_id": 2001,
                "user_full_name": "김철수",
                "hash_sha256": "abc123def456789...",
                "start_date": 1705276200,
                "end_date": 1705276800,
                "expiration_date": 1736812800,
                "anonymization_strategy": "none",
            }
        }


class DocumentExpiringResponseDTO(BaseModel):
    """만료 임박 문서 응답 DTO"""

    id: int = Field(..., description="문서 ID")
    category: str = Field(..., description="문서 카테고리")
    title: str = Field(..., description="문서 제목")
    filename: str = Field(..., description="파일명")
    summary: str = Field(..., description="문서 요약")
    file_type: str = Field(..., description="파일 타입")
    file_size: int = Field(..., description="파일 크기 (바이트)")
    status: str = Field(..., description="업로드 상태")
    role_ids: List[int] = Field(..., description="역할 ID 리스트")
    persona_id: int = Field(..., description="페르소나 ID")
    file_path: str = Field(..., description="파일 경로")
    download_url: str = Field(..., description="다운로드 URL")
    chunk_count: int = Field(..., description="청크 개수")
    token: int = Field(..., description="토큰 사용량")
    cost: float = Field(..., description="비용 (달러)")
    summary_token: int = Field(..., description="요약 토큰 사용량")
    summary_cost: float = Field(..., description="요약 비용 (달러)")
    group_id: int = Field(..., description="그룹 ID")
    user_id: int = Field(..., description="사용자 ID")
    hash_sha256: str = Field(..., description="파일 해시값")
    start_date: int = Field(..., description="작업 시작일 (Unix timestamp)")
    end_date: int = Field(..., description="작업 종료일 (Unix timestamp)")
    expiration_date: int = Field(..., description="문서 만료일 (Unix timestamp)")
    anonymization_strategy: str = Field(
        ...,
        description="PII 비식별화 전략 (none, masking, pseudonymization, generalization)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "category": "계약서",
                "title": "2024년 임시 계약서",
                "filename": "임시계약서_2024.pdf",
                "summary": "2024년도 임시직 계약 조건을 명시한 문서입니다...",
                "file_type": "pdf",
                "file_size": 524288,
                "status": "completed",
                "role_ids": [3],
                "persona_id": 1,
                "file_path": "contracts/2024/temporary/temp_contract.pdf",
                "download_url": "https://storage.example.com/contracts/2024/temp_contract.pdf",
                "chunk_count": 8,
                "token": 1800,
                "cost": 0.018,
                "summary_token": 300,
                "summary_cost": 0.003,
                "group_id": 101,
                "user_id": 2001,
                "hash_sha256": "def456abc789...",
                "start_date": 1705276200,
                "end_date": 1705276800,
                "expiration_date": 1735689600,
                "anonymization_strategy": "none",
            }
        }


class DocumentVectorResponseDTO(BaseModel):
    """문서 벡터 데이터 응답 DTO"""

    id: int = Field(..., description="벡터 ID")
    parsed_text: str = Field(..., description="파싱된 텍스트")
    chunk_index: int = Field(..., description="청크 인덱스")
    title: str = Field(..., description="문서 제목")
    filename: str = Field(..., description="파일명")
    page_number: int = Field(..., description="페이지 번호")
    token: int = Field(..., description="토큰 수")
    cost: float = Field(..., description="비용")
    group_id: int = Field(..., description="그룹 ID")
    user_id: int = Field(..., description="사용자 ID")
    category: str = Field(..., description="카테고리")
    hash_sha256: str = Field(..., description="파일 해시값")
    date: int = Field(..., description="날짜 (Unix timestamp)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 459761794349220801,
                "parsed_text": "SaaS 기업들이 기다려온 맞춤 서비스!\\n샘플 제품 소개...",
                "chunk_index": 0,
                "title": "샘플 제품 소개자료",
                "filename": "sample_product_intro.pdf",
                "page_number": 1,
                "token": 618,
                "cost": 0.0000618,
                "group_id": 1,
                "user_id": 1,
                "category": "참조 자료",
                "hash_sha256": "f81ab298d5cb5b30cb7d584c4875f466d83e36b9f28c175578bb403fcab6165f",
                "date": 1753852125,
            }
        }


# -- CRUD DTOs --
class UpdateItemsRequestDTO(BaseModel):
    """항목 업데이트 DTO"""

    db_type: str = Field(default="meta", description="데이터베이스 타입 (meta, vector)")
    hash_sha256_option: str = Field(
        default="abc123", description="문서 해시값 (정확히 일치)"
    )
    update_data: Dict[str, Any] = Field(
        default={"title": "업데이트된 제목"},
        description="업데이트할 데이터 (key-value 쌍)",
    )


class DeleteItemsRequestDTO(BaseModel):
    group_id: int = Field(default=1, description="그룹 ID")
    user_id: str = Field(default="1", description="사용자 ID")
    role_id: int = Field(
        default=1, description="역할 ID (1: admin, 2: manager, 3: user)"
    )
    collection: str = Field(default="TB_1_vector", description="컬렉션 이름")
    id: int = Field(default=None, description="삭제할 항목 ID")


class DeleteDocumentsDTO(BaseModel):
    group_id: int = Field(default=1, description="그룹 ID")
    user_id: str = Field(default="1", description="사용자 ID")
    role_id: int = Field(
        default=1, description="역할 ID (1: admin, 2: manager, 3: user)"
    )
    hash_sha256_options: Dict[str, str] = Field(
        default={"hash_sha256": "abcdef1234567890"}, description="삭제할 문서의 해시값"
    )


class DeleteDocumentsRequestDTO(BaseModel):
    """여러 문서 삭제 요청 DTO"""

    hash_sha256_list: List[str] = Field(..., description="삭제할 문서들의 해시값 목록")


class DocumentMetaSearchRequestDTO(BaseModel):
    """문서 메타데이터 검색 요청 DTO (POST body)"""

    page: int = Field(default=1, ge=1, description="페이지 번호 (1부터 시작)")
    page_size: int = Field(
        default=10, ge=1, le=50, description="페이지당 항목 수 (최대 50)"
    )
    sort_by: str = Field(
        default="created_at",
        description="정렬 기준 필드 (created_at, updated_at, title, id)",
    )
    sort_order: str = Field(
        default="desc", description="정렬 방향 (asc, desc)"
    )
    category_option: Optional[str] = Field(
        default=None, description="카테고리 필터링"
    )
    title_option: Optional[str] = Field(
        default=None, description="제목 필터링 (부분 일치)"
    )
    hash_sha256_option: Optional[List[str]] = Field(
        default=None,
        description="해시값 필터링 (복수 지정 가능)",
    )
    persona_id_option: Optional[int] = Field(
        default=None, description="페르소나 ID 필터링"
    )
    filename_option: Optional[str] = Field(
        default=None, description="파일명 필터링 (부분 일치)"
    )
    status_option: Optional[str] = Field(
        default=None,
        description="문서 상태 필터링 (uploading, registered, running, uploaded, failed, skipped, ocr_required)",
    )

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        allowed = {"created_at", "updated_at", "title", "id"}
        if v not in allowed:
            raise ValueError(
                f"허용되지 않은 정렬 필드: '{v}'. 가능한 값: {', '.join(sorted(allowed))}"
            )
        return v

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        v_lower = v.lower()
        if v_lower not in ("asc", "desc"):
            raise ValueError(
                f"허용되지 않은 정렬 방향: '{v}'. 가능한 값: asc, desc"
            )
        return v_lower

    @field_validator("status_option")
    @classmethod
    def validate_status_option(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from app.dto.document_status import DocumentStatus

        valid_statuses = DocumentStatus.get_all_values()
        if v not in valid_statuses:
            raise ValueError(
                f"유효하지 않은 문서 상태: '{v}'. 가능한 값: {', '.join(valid_statuses)}"
            )
        return v


class DocumentResponseDTO(BaseModel):
    """문서 응답 DTO"""

    message: str = Field(..., description="처리 결과 메시지")
    code: int = Field(..., description="응답 코드")

    class Config:
        json_schema_extra = {
            "example": {"message": "Documents updated successfully.", "code": 200}
        }


# -- Vector Chunk Delete DTOs --
class DeletedChunkInfoDTO(BaseModel):
    """삭제된 청크 정보 DTO"""

    id: int = Field(..., description="삭제된 Milvus PK ID")
    hash_sha256: str = Field(..., description="문서 해시")
    title: str = Field(..., description="문서 제목")
    chunk_index: int = Field(..., description="청크 인덱스")
    bm25_deleted: bool = Field(..., description="BM25 인덱스 삭제 여부")


class VectorChunkDeleteResponseDTO(BaseModel):
    """벡터 청크 삭제 응답 DTO"""

    message: str = Field(..., description="처리 결과 메시지")
    code: int = Field(..., description="응답 코드")
    deleted_chunk: Optional[DeletedChunkInfoDTO] = Field(
        None, description="삭제된 청크 정보"
    )


# -- Retrieval DTOs --
class RetrievalRequestDTO(BaseModel):
    """쿼리 DTO"""

    query: str = Field(
        default="디딤365에서 야근으로 인정 받는 시간은 몇시부터인가요?",
        description="검색 쿼리",
    )
    category_filter: Optional[List[str]] = Field(
        default=None, description="카테고리 필터 (None인 경우 모든 카테고리 검색)"
    )
    hash_sha256_filter: Optional[List[str]] = Field(
        default=None, description="해시값 필터 (None인 경우 모든 해시값 검색)"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="반환할 최대 결과 수 (1~100, 작을수록 정확도 높음)",
    )
    reranker: Union[Literal["cohere", "flashrank"], bool, None] = Field(
        default=None,
        description=(
            "Reranker 선택:\n"
            "- None 또는 false: Reranker 사용 안 함 (하이브리드 검색만) - 기본값\n"
            "- 'cohere': CohereRerank (한국어 성능 우수, API 비용 발생, 권장)\n"
            "- 'flashrank': FlashrankRerank (로컬 실행, 무료, CPU 최적화)"
        ),
    )

    @field_validator("reranker", mode="before")
    @classmethod
    def normalize_reranker(cls, v: Any) -> Optional[str]:
        """false/False를 None으로 정규화"""
        if v is False:
            return None
        return v

    rerank_top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Reranker 최종 반환 개수 (1~50, Reranker 사용 시에만 적용)",
    )
    use_multi_query: bool = Field(
        default=False,
        description=(
            "MultiQueryRetriever 사용 여부 (LLM으로 쿼리 확장, API 비용 발생):\n"
            "- False: 원본 쿼리로만 검색 (무료) - 기본값\n"
            "- True: LLM이 쿼리를 3~5개로 확장하여 검색 (OpenAI API 비용 발생)"
        ),
    )
    cohere_api_key: Optional[str] = Field(
        default=None,
        description=(
            "Cohere API 키 (reranker='cohere' 사용 시 필수):\n"
            "- reranker='cohere' 선택 시 반드시 제공해야 합니다\n"
            "- 환경 변수를 사용하지 않고 직접 API 키를 전달합니다"
        ),
    )
    search_mode: Literal["hybrid", "dense"] = Field(
        default="hybrid",
        description=(
            "검색 모드 선택:\n"
            "- 'hybrid': 하이브리드 검색 (Dense + Sparse, RRF 통합) - 기본값, 권장\n"
            "- 'dense': Dense 검색만 (벡터 유사도만 사용, BM25 미사용)"
        ),
    )
    dense_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "Dense 검색 가중치 (0.0~1.0, search_mode='hybrid'인 경우에만 적용):\n"
            "- 벡터 유사도 검색의 가중치\n"
            "- 기본값: 0.7 (70%)"
        ),
    )
    sparse_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description=(
            "Sparse 검색 가중치 (0.0~1.0, search_mode='hybrid'인 경우에만 적용):\n"
            "- BM25 키워드 검색의 가중치\n"
            "- 기본값: 0.3 (30%)\n"
            "- 참고: dense_weight + sparse_weight = 1.0이 권장됨"
        ),
    )
    graph_search_enabled: bool = Field(
        default=False,
        description=(
            "그래프 검색 활성화 여부 (Graph RAG):\n"
            "- False: 그래프 검색 미사용 (하이브리드/Dense 검색만) - 기본값\n"
            "- True: 그래프 검색 활성화 (엔티티 및 관계 기반 검색 추가)"
        ),
    )
    max_hops: int = Field(
        default=1,
        ge=0,
        le=2,
        description=(
            "그래프 관계 추적 최대 홉 수 (0~2, graph_search_enabled=True일 때만 적용):\n"
            "- 0: 엔티티 매칭만 (관계 확장 없음)\n"
            "- 1: 1홉 확장 (직접 연결된 문서) - 기본값\n"
            "- 2: 2홉 확장 (2단계 떨어진 문서까지, 결과 많을 수 있음)"
        ),
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "최종 결과 필터링 threshold (0.0~1.0):\n"
            "- 0.0: 필터링 없음 (모든 결과 반환) - 기본값\n"
            "- 0.5: 50% 이상 유사도만 반환\n"
            "- 0.7: 70% 이상 유사도만 반환 (권장)\n"
            "- threshold 미만 점수의 문서는 결과에서 제외됨"
        ),
    )


class RetrievalReponseDTO(BaseModel):
    """결과 DTO"""

    score: Optional[float] = Field(
        None, description="유사도 점수 (그래프 검색만 사용 시 None)"
    )
    dense_score: Optional[float] = Field(
        None,
        description="Dense(벡터) 검색 점수 (hybrid 모드에서만 표시, dense 모드에서는 None)",
    )
    sparse_score: Optional[float] = Field(
        None,
        description="Sparse(BM25) 검색 점수 (hybrid 모드에서만 표시, dense 모드에서는 None)",
    )
    group_id: int = Field(..., description="그룹 ID")
    filename: str = Field(..., description="파일명")
    parsed_text: str = Field(..., description="추출된 텍스트")
    page_number: int = Field(..., description="페이지 번호")
    chunk_index: int = Field(..., description="청크 인덱스")
    hash_sha256: str = Field(..., description="문서 고유 해시값")
    graph_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Graph RAG 정보 (엔티티 매칭 정보, hop 수, 관계 경로 등)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "score": 0.692,
                "dense_score": 0.86,
                "sparse_score": 0.30,
                "group_id": 101,
                "filename": "디딤365_여비규정.pdf",
                "parsed_text": "제5조(국내출장) ① 국내출장은 공무로 소속기관의 장이 명한 경우에 한하며, 출장기간은 당해 공무수행에 필요한 최소한의 기간으로 한다.",
                "page_number": 3,
                "chunk_index": 2,
                "hash_sha256": "abc123def456789...",
                "graph_info": {
                    "matched_entity": {"name": "김철수", "type": "person"},
                    "hop": 1,
                    "relation_path": ["김철수", "담당함", "프로젝트X"],
                },
            }
        }


class SearchStatisticsDTO(BaseModel):
    """검색 통계 DTO"""

    total_results: int = Field(..., description="총 검색 결과 수")
    documents_found: int = Field(..., description="검색된 문서 개수")
    document_distribution: Dict[str, int] = Field(
        ..., description="문서별 결과 개수 (filename: count)"
    )
    similarity_distribution: Dict[str, Dict[str, int]] = Field(
        ...,
        description="문서별 유사도 분포 (filename: {high: count, medium: count, low: count}). high: ≥82.5%, medium: 80~82.5%, low: <80%",
    )
    average_score: float = Field(..., description="평균 유사도 점수")
    max_score: float = Field(..., description="최고 유사도 점수")
    min_score: float = Field(..., description="최저 유사도 점수")
    search_time_ms: int = Field(..., description="검색 소요 시간 (밀리초)")

    class Config:
        json_schema_extra = {
            "example": {
                "total_results": 10,
                "documents_found": 2,
                "document_distribution": {
                    "디딤365_여비규정.pdf": 8,
                    "출장경비_지침.pdf": 2,
                },
                "similarity_distribution": {
                    "디딤365_여비규정.pdf": {"high": 4, "medium": 2, "low": 2},
                    "출장경비_지침.pdf": {"high": 1, "medium": 1, "low": 0},
                },
                "average_score": 0.847,
                "max_score": 0.95,
                "min_score": 0.76,
                "search_time_ms": 1234,
            }
        }


class RetrievalResponseWithStatsDTO(BaseModel):
    """검색 결과 및 통계 DTO"""

    results: List[RetrievalReponseDTO] = Field(..., description="검색 결과 리스트")
    statistics: SearchStatisticsDTO = Field(..., description="검색 통계")

    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "score": 0.92,
                        "group_id": 101,
                        "filename": "디딤365_여비규정.pdf",
                        "parsed_text": "제5조(국내출장)...",
                        "page_number": 3,
                        "chunk_index": 2,
                        "hash_sha256": "abc123...",
                    }
                ],
                "statistics": {
                    "total_results": 10,
                    "documents_found": 2,
                    "document_distribution": {
                        "디딤365_여비규정.pdf": 8,
                        "출장경비_지침.pdf": 2,
                    },
                    "similarity_distribution": {
                        "디딤365_여비규정.pdf": {"high": 4, "medium": 2, "low": 2},
                        "출장경비_지침.pdf": {"high": 1, "medium": 1, "low": 0},
                    },
                    "average_score": 0.847,
                    "max_score": 0.95,
                    "min_score": 0.76,
                    "search_time_ms": 1234,
                },
            }
        }


class UpdateIndexRequestDTO(BaseModel):
    """인덱스 업데이트 DTO"""

    index_type: str = Field(
        default="IVF_FLAT",
        description="인덱스 타입 (FLAT, IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, ANNOY)",
    )
    params: Dict[str, Any] = Field(
        default={"nlist": 128}, description="인덱스 파라미터"
    )
    metric_type: str = Field(
        default="COSINE",
        description="메트릭 타입 (L2, IP, COSINE, HAMMING, JACCARD, TANIMOTO)",
    )


# 각 컬렉션 별 인덱스 업데이트 결과를 나타내는 DTO
class IndexUpdateResultDTO(BaseModel):
    collection_name: str = Field(..., description="업데이트한 컬렉션 이름")
    status: str = Field(..., description="업데이트 상태 (success 또는 failed)")
    error: Optional[str] = Field(default=None, description="실패 시 에러 메시지")


# API 전체 응답 DTO
class UpdateIndexResponseDTO(BaseModel):
    detail: str = Field(..., description="전체 작업에 대한 상세 메시지")
    results: List[IndexUpdateResultDTO] = Field(
        ..., description="각 컬렉션 별 업데이트 결과 리스트"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "인덱스 업데이트 완료: 2개 컬렉션 성공",
                "results": [
                    {
                        "collection_name": "TB_1_meta",
                        "status": "success",
                        "error": None,
                    },
                    {
                        "collection_name": "TB_1_vector",
                        "status": "success",
                        "error": None,
                    },
                ],
            }
        }
