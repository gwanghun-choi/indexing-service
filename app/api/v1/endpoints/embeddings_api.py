import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from app.crud.milvus.document_crud import validate_documents
from app.crud.milvus.search_crud import get_hybrid_search_service
from app.dto.embeddings_dto import (
    GenerateEmbeddingRequestDTO,
    GenerateEmbeddingResponseDTO,
    RollbackEmbeddingRequestDTO,
    RollbackEmbeddingResponseDTO,
)
from app.service.embedding_rollback_service import rollback_embeddings
from app.dto.table_dto import (
    RetrievalRequestDTO,
    RetrievalResponseWithStatsDTO,
    UpdateIndexRequestDTO,
)
from app.service.embedding_generation_pipeline import run_embedding_generation_pipeline
from app.service.index_service import update_index
from app.service.langgraph_service import LangGraphService
from app.utils.auth_utils import get_parsed_jwt_data, get_user_passport_header
from app.utils.search_utils import calculate_search_statistics


logger = logging.getLogger(__name__)


class PIIAnonymizationStrategy(str, Enum):
    """PII 비식별화 전략"""

    NONE = "none"  # 비식별화 하지 않음
    MASKING = "masking"  # 마스킹 (***로 대체)
    PSEUDONYMIZATION = "pseudonymization"  # 가명화 (ID로 대체)
    GENERALIZATION = "generalization"  # 일반화 (상위 개념으로 대체)


router = APIRouter(
    responses={
        400: {"description": "잘못된 요청 - 요청 매개변수가 유효하지 않습니다."},
        401: {"description": "인증 실패 - 유효한 인증 정보가 필요합니다."},
        403: {"description": "권한 부족 - 요청된 작업에 대한 권한이 없습니다."},
        404: {"description": "찾을 수 없음 - 요청된 리소스가 존재하지 않습니다."},
        500: {"description": "서버 오류 - 서버 내부 오류가 발생했습니다."},
    },
)


@router.post(
    "/generate",
    summary="문서 임베딩 생성 (무제한 배치 처리)",
    response_model=GenerateEmbeddingResponseDTO,
    responses={
        200: {
            "description": "임베딩 생성 작업이 성공적으로 시작되었습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "result": True,
                        "message": "3개 문서가 큐에 등록되었습니다. 가용한 worker가 병렬로 처리합니다.",
                        "task_ids": ["task-1", "task-2", "task-3"],
                        "success_count": 3,
                        "failed_count": 0,
                        "failed_documents": None,
                    }
                }
            },
        },
        400: {
            "description": "잘못된 요청 - 처리 가능한 문서가 없습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "message": "처리 가능한 문서가 없습니다. 모든 문서가 실패했습니다 (실패: 1개)",
                            "failed_count": 1,
                            "failed_documents": [
                                {
                                    "hash_sha256": "abc123...",
                                    "title": "문서제목",
                                    "reason": "문서 상태가 'registered'가 아닙니다 (현재: failed)",
                                }
                            ],
                        }
                    }
                }
            },
        },
    },
    description="""
🤖 **등록된 문서의 임베딩 생성 (배치 처리)**

이미 등록된 문서(status=registered)에 대해 임베딩을 생성합니다.
여러 문서를 한 번에 요청할 수 있으며, 모두 Celery 큐에 등록되어 가용한 worker가 병렬로 처리합니다.

## 청킹 전략 (Chunking Strategy)

| 전략 | 설명 | 파라미터 |
|------|------|----------|
| `fixed` | 고정 크기 분할 (기본) | chunk_size, chunk_overlap |
| `semantic` | 의미 기반 분할 (권장) | similarity_threshold, max_chunk_size, min_chunk_size |

## 사용 예시 - Fixed Chunking (고정 크기 청킹)
```bash
curl -X POST "http://localhost:8002/api/v1/embeddings/generate" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "hash_sha256_list": ["abc123...", "def456..."],
    "chunking": {
      "strategy": "fixed",
      "chunk_size": 500,
      "chunk_overlap": 50
    },
    "enable_pii_anonymization": false
  }'
```

## 사용 예시 - Semantic Chunking (의미 기반 청킹, 권장)
```bash
curl -X POST "http://localhost:8002/api/v1/embeddings/generate" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "hash_sha256_list": ["abc123..."],
    "chunking": {
      "strategy": "semantic",
      "similarity_threshold": 0.5,
      "max_chunk_size": 1500,
      "min_chunk_size": 100
    },
    "enable_pii_anonymization": false
  }'
```

## 사용 예시 - 전체 옵션 (PII + KTC Parser + Semantic)
```bash
curl -X POST "http://localhost:8002/api/v1/embeddings/generate" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "hash_sha256_list": ["abc123..."],
    "chunking": {
      "strategy": "semantic",
      "similarity_threshold": 0.5,
      "max_chunk_size": 1500
    },
    "enable_pii_anonymization": true,
    "pii_strategy": "masking",
    "pii_types": ["이름", "전화번호"],
    "document_parser": "ktc_parser",
    "persona_id": 123,
    "filter_score": 0.7
  }'
```

## 하위 호환 - 레거시 방식 (chunk_size/chunk_overlap 직접 사용)
> ⚠️ 이 방식은 하위 호환을 위해 유지됩니다. 새로운 `chunking` 객체 사용을 권장합니다.
```bash
curl -X POST "http://localhost:8002/api/v1/embeddings/generate" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "hash_sha256_list": ["abc123..."],
    "chunk_size": 500,
    "chunk_overlap": 50,
    "enable_pii_anonymization": false
  }'
```

## 처리 흐름
1. 문서 배치 조회 및 권한 검증 (group_id, role_ids 확인)
2. 각 문서의 상태 검증 (registered 확인)
3. 유효한 모든 문서를 Celery 큐에 태스크로 등록
4. API는 즉시 응답 (task_ids 반환)
5. 가용한 모든 worker가 병렬로 태스크를 처리
   - 예: worker 5개 × concurrency 4 = 최대 20개 동시 처리
6. 각 문서별 백그라운드 처리 파이프라인:
   - 문서 파싱 및 청크 분할
   - 벡터 임베딩 생성 (Milvus 저장)
   - 문서 요약 생성 (LLM)
   - 엔티티 추출 (PERSON, ORGANIZATION, DATE, PROJECT, CONCEPT, DOCUMENT_TYPE, CATEGORY)
   - BM25 인덱스 업데이트 (Redis 저장)
7. 각 문서별 처리 결과는 SSE로 실시간 알림

## 주요 특징
- **무제한 배치 처리**: 요청된 모든 문서를 Celery 큐에 등록
- **병렬 처리**: 가용한 모든 worker가 동시에 처리
- **권한 검증**: group_id, user_id, role_ids 기반 접근 제어
- **부분 성공 지원**: 일부 문서만 실패해도 나머지는 처리
- **Semantic Chunking**: `chunking.strategy="semantic"` 옵션으로 의미 기반 텍스트 분할
  - 문장 간 의미적 유사도 기반 분할 (kiwipiepy + OpenAI Embedding)
  - 의미적으로 연결된 내용을 하나의 청크로 유지
  - RAG 검색 품질 향상
- **고급 문서 파싱**: `document_parser="ktc_parser"` 옵션으로 KT Cloud Document Parse API 사용
  - 복잡한 표, 차트, 다단 레이아웃 정확 파싱
  - 이미지 문서 자동 OCR 처리
  - Markdown 포맷으로 구조 유지
- **Graph RAG 자동 구축**: 문서 임베딩 생성 시 엔티티 추출 및 그래프 관계 자동 구축 (검색 시 활용)
    """,
)
async def generate_embedding(
    request: GenerateEmbeddingRequestDTO,
    http_request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> GenerateEmbeddingResponseDTO:
    """
    등록된 문서의 임베딩을 배치로 생성합니다.

    Args:
        request: 임베딩 생성 요청 정보
            - hash_sha256_list: 문서 해시값 리스트 (필수)
            - chunking: 청킹 설정 객체 (선택, 권장)
                * strategy: 'fixed' 또는 'semantic'
                * fixed 전략: chunk_size, chunk_overlap 필수
                * semantic 전략: similarity_threshold, max_chunk_size, min_chunk_size 설정 가능
            - chunk_size: [하위 호환] 청크 크기 (chunking 미사용 시 필수)
            - chunk_overlap: [하위 호환] 청크 오버랩 크기 (chunking 미사용 시 필수)
            - enable_pii_anonymization: 개인정보 비식별화 활성화 (필수)
            - pii_strategy: 비식별화 전략 (선택)
            - pii_types: 비식별화할 개인정보 유형 리스트 (선택)
            - persona_id: 페르소나 ID (기본값: 0, 0이면 필터링 안함)
            - filter_score: 필터링 점수 (선택)
            - document_parser: 사용할 문서 파서 (기본값: None)
                * None: 기본 파서 사용 (빠름, 무료)
                * 'ktc_parser': KT Cloud Document Parse API 사용 (고품질, 복잡한 문서 처리)
        jwt_data: JWT 인증 정보

    Returns:
        GenerateEmbeddingResponseDTO:
            - result: 작업 성공 여부
            - message: 처리 결과 메시지
            - task_ids: 생성된 작업 ID 리스트
            - success_count: 성공한 문서 수
            - failed_count: 실패한 문서 수
            - failed_documents: 실패한 문서 정보

    Raises:
        HTTPException:
            - 400: 잘못된 요청 (처리 가능한 문서가 없음)
            - 403: 권한 없음
            - 500: 서버 내부 오류
    """
    try:
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        logger.info(
            f"🤖 임베딩 배치 생성 요청: user={user_id}, 문서 수={len(request.hash_sha256_list)}"
        )

        # 1. 문서 배치 검증 (권한 + 상태 확인)
        valid_docs, failed_docs = await validate_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=total_role,
            hash_sha256_list=request.hash_sha256_list,
        )

        # 2. 유효한 문서가 없으면 즉시 에러 반환
        if not valid_docs:
            error_msg = f"처리 가능한 문서가 없습니다. 모든 문서가 실패했습니다 (실패: {len(failed_docs)}개)"
            logger.warning(f"⚠️ {error_msg}")
            logger.warning(f"⚠️ 실패 상세: {failed_docs}")
            raise HTTPException(
                status_code=400,
                detail={
                    "message": error_msg,
                    "failed_count": len(failed_docs),
                    "failed_documents": failed_docs,
                },
            )

        task_ids = []

        # 3. 유효한 문서들에 대해 임베딩 파이프라인 실행
        for doc in valid_docs:
            task_id = str(uuid.uuid4())

            # 파이프라인 페이로드 구성
            # 후속 `download_document` task 가 cloud-storage 의 인증 endpoint 호출 시
            # `x-user-passport` 헤더로 사용하기 위해 client 의 passport raw 동봉.
            payload = {
                "task_id": task_id,
                "user_id": user_id,
                "group_id": group_id,
                "total_role": total_role,
                "passport_json": http_request.headers.get("x-user-passport"),
                "hash_sha256": doc["hash_sha256"],
                "category": doc["category"],
                "embedding_model": "openai",
                "model_name": "text-embedding-ada-002",
                "chunk_size": request.chunk_size,
                "chunk_overlap": request.chunk_overlap,
                "chunking": request.chunking,
                "enable_pii_anonymization": request.enable_pii_anonymization,
                "pii_strategy": request.pii_strategy,
                "pii_types": request.pii_types,
                "persona_id": request.persona_id,
                "filter_score": request.filter_score,
                "document_parser": request.document_parser,
            }

            # 임베딩 생성 파이프라인 실행
            run_embedding_generation_pipeline.apply_async(
                args=[payload], task_id=task_id
            )

            task_ids.append(task_id)

            logger.info(
                f"✅ 임베딩 태스크 등록: task_id={task_id}, hash={doc['hash_sha256'][:16]}..."
            )

        success_count = len(valid_docs)
        failed_count = len(failed_docs)

        logger.info(
            f"✅ 임베딩 배치 요청 완료: "
            f"큐 등록 {success_count}개, 실패 {failed_count}개 "
            f"(가용 worker가 병렬 처리 중)"
        )

        return GenerateEmbeddingResponseDTO(
            result=True,
            message=f"{success_count}개 문서가 큐에 등록되었습니다. 가용한 worker가 병렬로 처리합니다.",
            task_ids=task_ids,
            success_count=success_count,
            failed_count=failed_count,
            failed_documents=failed_docs if failed_docs else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 임베딩 배치 생성 요청 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/rollback",
    summary="임베딩 롤백 (registered 상태로 되돌림)",
    response_model=RollbackEmbeddingResponseDTO,
    description="""
🔄 **임베딩 롤백 (registered 상태로 되돌림)**

임베딩 파이프라인 실행 전 상태(registered)로 문서를 되돌립니다.

## 롤백 가능 상태
- `uploaded`: 임베딩 완료
- `failed`: 임베딩 중 실패
- `running`: 임베딩 진행 중 (중단된 경우)

## 롤백 대상
1. **Vector 컬렉션**: 해당 문서의 청크+벡터 삭제
2. **BM25 인덱스**: 해당 문서의 BM25 인덱스 제거
3. **Meta 컬렉션**: summary, entities, embedding_value 초기화 + status → registered
    """,
)
async def rollback_embedding(
    request: RollbackEmbeddingRequestDTO,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> RollbackEmbeddingResponseDTO:
    """임베딩 롤백 - 문서를 registered 상태로 되돌립니다."""
    try:
        result = await rollback_embeddings(
            group_id=jwt_data["group_id"],
            user_id=jwt_data["user_id"],
            role_ids=jwt_data["total_role"],
            hash_sha256_list=request.hash_sha256_list,
        )

        if result["success_count"] == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"롤백 가능한 문서가 없습니다 (실패: {result['failed_count']}개)",
                    "failed_count": result["failed_count"],
                    "failed_documents": result["failed_docs"],
                },
            )

        return RollbackEmbeddingResponseDTO(
            result=True,
            message=f"{result['success_count']}개 문서 임베딩 롤백 완료",
            success_count=result["success_count"],
            failed_count=result["failed_count"],
            deleted_vectors=result["deleted_vectors"],
            deleted_bm25_docs=result["deleted_bm25_docs"],
            failed_documents=result["failed_docs"] if result["failed_docs"] else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 임베딩 롤백 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/retrieval",
    summary="AI 문서 검색 (Hybrid + MultiQuery + Reranker + Graph RAG)",
    response_model=RetrievalResponseWithStatsDTO,
    responses={
        200: {
            "description": "성공적으로 하이브리드 검색 결과를 반환했습니다.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "filename": "여비규정.pdf",
                            "page_number": 5,
                            "chunk_index": 2,
                            "text": "해외 출장 시 일비는 국가별로 상이하며, 기본적으로 USD 130을 기준으로 합니다...",
                            "similarity": 0.92,
                            "hash_sha256": "abc123def456...",
                            "category": "규정",
                            "title": "디딜365 여비규정",
                        },
                        {
                            "filename": "travel_policy_2024.pdf",
                            "page_number": 12,
                            "chunk_index": 5,
                            "text": "출장 경비 정산은 귀국 후 7일 이내에 완료해야 하며...",
                            "similarity": 0.88,
                            "hash_sha256": "def789ghi123...",
                            "category": "규정",
                            "title": "2024년 출장 정책",
                        },
                    ]
                }
            },
        }
    },
    description="""
🔍 **AI 기반 문서 검색 (Advanced RAG + Graph RAG)**

고급 RAG 기술과 지식 그래프를 활용한 최대 5단계 검색 프로세스를 제공합니다.

## 🎯 검색 프로세스
1. **검색 모드 선택**: Dense 또는 Hybrid 검색
   - Dense: 벡터 유사도만 사용
   - Hybrid: Dense + Sparse (BM25) 결합 (권장)
2. **MultiQuery (선택적)**: LLM이 쿼리를 3~5개로 확장하여 다양한 관점에서 검색 (Hybrid 모드만 지원)
3. **Reranker (선택적)**: Cross-Encoder로 결과 재정렬하여 정확도 향상 (Dense/Hybrid 모두 지원)
4. **Graph RAG (선택적)**: LLM 기반 질문 분석 + 엔티티/관계 기반 검색 확장
5. **통계 분석**: 검색 결과에 대한 상세 통계 제공

## 📊 주요 파라미터
### 기본 검색
- **query**: 검색할 자연어 쿼리
- **limit**: 초기 검색에서 반환할 결과 수 (기본: 10, 범위: 1~100)
- **search_mode**: 검색 모드 선택 (기본: 'hybrid')
  - 🔀 'hybrid': 하이브리드 검색 (Dense + Sparse, 권장)
  - 📊 'dense': Dense 검색만 (벡터 유사도만 사용)
- **dense_weight**: Dense 검색 가중치 (기본: 0.7, 범위: 0.0~1.0, hybrid 모드에서만 적용)
- **sparse_weight**: Sparse 검색 가중치 (기본: 0.3, 범위: 0.0~1.0, hybrid 모드에서만 적용)

### Advanced RAG
- **use_multi_query**: LLM 쿼리 확장 사용 여부 (기본: False, hybrid 모드에서만 지원)
  - ✅ False: 무료, 원본 쿼리로만 검색
  - 💰 True: OpenAI API 비용 발생 (GPT-4o-mini, 약 $0.0002/검색)
- **reranker**: Reranker 선택 (기본: None, Dense/Hybrid 모두 지원)
  - ✅ None: 무료, 검색 결과만 반환
  - ⚡ 'flashrank': 무료, 로컬 실행, CPU 최적화
  - 🌐 'cohere': API 비용 발생 (한국어 우수, 약 $2/1000 검색)
- **rerank_top_n**: Reranker 최종 반환 개수 (기본: 10, 범위: 1~50)
- **cohere_api_key**: Cohere API 키 (reranker='cohere' 사용 시 필수, 환경 변수 미사용)

### Graph RAG
- **graph_search_enabled**: 그래프 검색 활성화 여부 (기본: False)
  - ✅ False: 기존 하이브리드 검색만 사용
  - 🕸️ True: LangGraph 워크플로우 활성화 (질문 분석 + 엔티티/관계 기반 검색)
  - 💰 True 시 OpenAI API 비용 발생 (GPT-4o-mini, 약 $0.0002/검색)
- **max_hops**: 그래프 관계 추적 최대 홉 수 (기본: 1, 범위: 0~2, graph_search_enabled=True일 때만 적용)
  - 0: 엔티티 매칭만 (관계 확장 없음)
  - 1: 1홉 확장 (직접 연결된 문서, 권장)
  - 2: 2홉 확장 (2단계 떨어진 문서까지, 결과 많을 수 있음)

## 💡 사용 예시
### 기본 검색 (무료, 하이브리드)
```json
{
  "query": "디딤365 야근 시간",
  "limit": 10,
  "search_mode": "hybrid"
}
```

### Dense 검색만 (벡터 유사도만)
```json
{
  "query": "디딤365 야근 시간",
  "limit": 10,
  "search_mode": "dense"
}
```

### Dense 검색 + Reranker (무료)
```json
{
  "query": "디딤365 야근 시간",
  "limit": 30,
  "search_mode": "dense",
  "reranker": "flashrank",
  "rerank_top_n": 10
}
```

### Dense 검색 + Cohere Reranker (유료, 고정확도)
```json
{
  "query": "디딤365 야근 시간",
  "limit": 30,
  "search_mode": "dense",
  "reranker": "cohere",
  "rerank_top_n": 10,
  "cohere_api_key": "your-cohere-api-key-here"
}
```

### 커스텀 가중치 하이브리드 검색
```json
{
  "query": "야근",
  "limit": 10,
  "search_mode": "hybrid",
  "dense_weight": 0.8,
  "sparse_weight": 0.2
}
```

### 최고 정확도 (유료, Hybrid + MultiQuery + Reranker)
```json
{
  "query": "야근",
  "limit": 30,
  "search_mode": "hybrid",
  "dense_weight": 0.7,
  "sparse_weight": 0.3,
  "use_multi_query": true,
  "reranker": "cohere",
  "rerank_top_n": 10,
  "cohere_api_key": "your-cohere-api-key-here"
}
```

### Graph RAG 검색 (유료, 엔티티/관계 기반)
```json
{
  "query": "홍길동이 작성한 프로젝트 문서",
  "limit": 10,
  "search_mode": "hybrid",
  "graph_search_enabled": true,
  "max_hops": 1
}
```

### Graph RAG + 2홉 확장 (유료, 관련 문서까지 확장)
```json
{
  "query": "디딤AI 프로젝트와 관련된 모든 문서",
  "limit": 20,
  "search_mode": "hybrid",
  "graph_search_enabled": true,
  "max_hops": 2
}
```

### Graph RAG + Reranker (유료, 최고 정확도)
```json
{
  "query": "2024년 프로젝트 관련 문서",
  "limit": 30,
  "search_mode": "hybrid",
  "graph_search_enabled": true,
  "max_hops": 1,
  "reranker": "flashrank",
  "rerank_top_n": 10
}
```

## 🔧 필터링 옵션
- **category_filter**: 카테고리별 필터링
- **hash_sha256_filter**: 특정 파일만 검색
    """,
)
async def search_documents(
    request: RetrievalRequestDTO,
    http_request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> RetrievalResponseWithStatsDTO:
    """
    AI 기반 문서 검색 (Hybrid + MultiQuery + Reranker + Graph RAG)

    이 API는 고급 RAG 기술과 지식 그래프를 활용한 최대 5단계 검색 프로세스를 수행합니다:
    1. **검색 모드 선택**: Dense (벡터만) 또는 Hybrid (Dense + Sparse)
    2. **MultiQuery (선택적)**: LLM이 쿼리를 3~5개로 확장하여 다양한 관점에서 검색 (Hybrid 모드만)
    3. **Reranker (선택적)**: 검색 결과를 Cross-Encoder로 재정렬하여 정확도 향상 (Dense/Hybrid 모두 지원)
    4. **Graph RAG (선택적)**: LLM 기반 질문 분석 + 엔티티/관계 기반 검색 확장
    5. **통계 분석**: 검색 결과에 대한 상세 통계 제공

    Args:
        request: 검색 요청 정보 (RetrievalRequestDTO)
            - query: 검색할 자연어 쿼리 (필수)
            - limit: 초기 검색에서 반환할 결과 수 (기본: 10, 범위: 1~100)
            - category_filter: 카테고리 필터링 (선택적)
            - hash_sha256_filter: 파일 해시 필터링 (선택적)
            - search_mode: 검색 모드 (기본: 'hybrid')
                * 'hybrid': 하이브리드 검색 (Dense + Sparse, 권장)
                * 'dense': Dense 검색만 (벡터 유사도만 사용)
            - dense_weight: Dense 검색 가중치 (기본: 0.7, 범위: 0.0~1.0, hybrid 모드에서만 적용)
            - sparse_weight: Sparse 검색 가중치 (기본: 0.3, 범위: 0.0~1.0, hybrid 모드에서만 적용)
            - use_multi_query: MultiQueryRetriever 사용 여부 (기본: False, hybrid 모드에서만 지원)
                * False: 원본 쿼리로만 검색 (무료, 기본값)
                * True: LLM이 쿼리를 확장하여 검색 (OpenAI API 비용 발생)
            - reranker: Reranker 선택 (기본: None, Dense/Hybrid 모두 지원)
                * None: Reranker 미사용
                * 'cohere': CohereRerank (한국어 우수, API 비용 발생, 권장)
                * 'flashrank': FlashrankRerank (로컬, 무료, CPU 최적화)
            - rerank_top_n: Reranker 최종 반환 개수 (기본: 10, 범위: 1~50)
            - cohere_api_key: Cohere API 키 (reranker='cohere' 사용 시 필수, 환경 변수 미사용)
            - graph_search_enabled: 그래프 검색 활성화 여부 (기본: False)
                * False: 기존 하이브리드 검색만 사용
                * True: LangGraph 워크플로우 활성화 (질문 분석 + 엔티티/관계 기반 검색, OpenAI API 비용 발생)
            - max_hops: 그래프 관계 추적 최대 홉 수 (기본: 1, 범위: 0~2, graph_search_enabled=True일 때만 적용)
                * 0: 엔티티 매칭만 (관계 확장 없음)
                * 1: 1홉 확장 (직접 연결된 문서, 권장)
                * 2: 2홉 확장 (2단계 떨어진 문서까지)
            - threshold: 최종 결과 필터링 threshold (기본: 0.0, 범위: 0.0~1.0)
                * 0.0: 필터링 없음 (모든 결과 반환)
                * 0.5: 50% 이상 유사도만 반환
                * 0.7: 70% 이상 유사도만 반환 (권장)
        jwt_data: JWT에서 파싱된 사용자 정보 (자동 의존성 주입)
            - user_id: 사용자 ID
            - group_id: 그룹 ID (멀티테넌시)
            - total_role: 역할 ID 리스트

    Returns:
        RetrievalResponseWithStatsDTO: 검색 결과 및 통계
            - results: 정확도 순으로 정렬된 검색 결과 리스트
            - statistics: 검색 통계 (문서별 개수, 유사도 분포, 평균/최고/최저 점수 등)

    Raises:
        HTTPException: 검색 실패 시
            - 500: 벡터 검색 오류, 임베딩 생성 실패, 내부 서버 오류

    Note:
        - 검색 모드: hybrid(하이브리드) 또는 dense(벡터만) 선택 가능
        - 하이브리드 검색은 기본적으로 Dense(70%) + Sparse(30%) 가중치로 RRF 통합됩니다.
        - dense_weight와 sparse_weight는 커스터마이징 가능합니다 (합이 1.0 권장).
        - MultiQuery는 hybrid 모드에서만 지원되며, 짧거나 모호한 쿼리에 효과적이나 LLM API 비용이 발생합니다.
        - Reranker는 Dense/Hybrid 모두에서 사용 가능하며, 검색 정확도를 크게 향상시킵니다.
        - CohereRerank는 한국어에 최적화되어 있어 권장되나, API 비용이 발생합니다.
        - CohereRerank 사용 시 cohere_api_key를 반드시 제공해야 합니다 (환경 변수 미사용).
        - FlashrankRerank는 무료이나, 영어 성능이 더 우수합니다.
        - Graph RAG는 LLM을 사용하여 질문을 분석하고, 엔티티와 관계를 기반으로 검색을 확장합니다 (OpenAI API 비용 발생).
        - Graph RAG는 관계 기반 질문("홍길동이 작성한 문서", "프로젝트 A와 관련된 문서")에 효과적입니다.
    """
    try:
        # 검색 시작 시간
        search_start_time = time.time()

        # JWT에서 파싱된 값 사용
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        logger.info(
            f"🔍 검색 요청: user={user_id}, query='{request.query}', "
            f"graph_search_enabled={request.graph_search_enabled}"
        )

        langgraph_service = None
        hybrid_search_service = None

        try:
            # x-user-passport 헤더 가져오기 (SKIP_AUTH 모드 지원)
            user_passport = get_user_passport_header(http_request)

            # 그래프 검색 활성화 여부에 따라 분기
            if request.graph_search_enabled:
                # LangGraph 워크플로우 사용
                logger.info("🕸️ Graph RAG 모드: LangGraph 워크플로우 실행")
                langgraph_service = LangGraphService()

                # LangGraphService는 항상 Graph RAG를 포함한 검색 수행
                # (graph_search_enabled=True 분기에서만 호출됨)
                workflow_result = await langgraph_service.run(
                    query=request.query,
                    group_id=group_id,
                    total_role=total_role,
                    limit=request.limit,
                    search_mode=request.search_mode,
                    dense_weight=request.dense_weight,
                    sparse_weight=request.sparse_weight,
                    rerank_top_n=request.rerank_top_n,
                    use_multi_query=request.use_multi_query,
                    threshold=request.threshold,
                    user_passport=user_passport,
                    category_filter=request.category_filter,
                    hash_sha256_filter=request.hash_sha256_filter,
                    reranker=request.reranker,
                    cohere_api_key=request.cohere_api_key,
                    max_hops=request.max_hops,
                )

                results = workflow_result["results"]
                query_analysis = workflow_result["query_analysis"]

                logger.info(
                    f"✅ Graph RAG 검색 완료: {len(results)}개 결과, "
                    f"질문 유형: {query_analysis['query_type']}"
                )
            else:
                # 기존 하이브리드 검색
                logger.info("📊 하이브리드 검색 모드")
                hybrid_search_service = get_hybrid_search_service()

                results = await hybrid_search_service.search(
                    query=request.query,
                    group_id=group_id,
                    total_role=total_role,
                    limit=request.limit,
                    search_mode=request.search_mode,
                    dense_weight=request.dense_weight,
                    sparse_weight=request.sparse_weight,
                    rerank_top_n=request.rerank_top_n,
                    use_multi_query=request.use_multi_query,
                    threshold=request.threshold,
                    user_passport=user_passport,
                    category_filter=request.category_filter,
                    hash_sha256_filter=request.hash_sha256_filter,
                    reranker=request.reranker,
                    cohere_api_key=request.cohere_api_key,
                )

                logger.info(f"✅ 하이브리드 검색 완료: {len(results)}개 결과")

            # 검색 종료 시간 및 소요 시간 계산
            search_end_time = time.time()
            search_time_ms = int((search_end_time - search_start_time) * 1000)

            # 통계 계산
            statistics = calculate_search_statistics(results)
            statistics["search_time_ms"] = search_time_ms

            logger.debug(
                f"📊 통계: 문서 {statistics['documents_found']}개, "
                f"평균 유사도 {statistics['average_score']:.3f}, "
                f"소요 시간 {search_time_ms}ms"
            )

            # 결과 + 통계 반환
            return {
                "results": results,
                "statistics": statistics,
            }

        finally:
            if langgraph_service:
                langgraph_service.cleanup()
            if hybrid_search_service:
                hybrid_search_service.cleanup()

            logger.debug("✅ 검색 API 메모리 정리 완료")

    except Exception as e:
        logger.error(f"❌ 검색 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/index",
    summary="인덱스 생성",
    response_model=Dict[str, Any],
    responses={
        200: {
            "description": "성공적으로 인덱스를 생성/업데이트했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "인덱스 업데이트 완료: 2개 컬렉션 성공",
                        "results": [
                            {
                                "collection": "TB_1_meta",
                                "status": "success",
                                "message": "HNSW 인덱스 생성 완료",
                                "index_info": {
                                    "type": "HNSW",
                                    "metric_type": "L2",
                                    "params": {"M": 16, "efConstruction": 200},
                                },
                            },
                            {
                                "collection": "TB_1_vector",
                                "status": "success",
                                "message": "HNSW 인덱스 생성 완료",
                                "index_info": {
                                    "type": "HNSW",
                                    "metric_type": "L2",
                                    "params": {"M": 16, "efConstruction": 200},
                                },
                            },
                        ],
                    }
                }
            },
        }
    },
    description="""
🗝️ **벡터 데이터베이스 인덱스 관리**

벡터 데이터베이스의 인덱스를 생성하거나 업데이트합니다. 관리자 권한이 필요합니다.

## 인덱스 타입
- **FLAT**: 브루트포스 검색 (정확도 100%, 속도 느림)
- **IVF_FLAT**: 클러스터 기반 검색 (속도와 정확도 균형)
- **HNSW**: 그래프 기반 근사 검색 (고속, 높은 정확도)

## 거리 측정 방식
- **L2**: 유클리드 거리
- **IP**: 내적 (Inner Product)
- **COSINE**: 코사인 유사도

## 주의사항
⚠️ 인덱스 생성은 대용량 데이터의 경우 시간이 오래 걸릴 수 있습니다.
    """,
)
async def create_index(
    request: UpdateIndexRequestDTO,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """
    벡터 검색 성능 최적화를 위한 인덱스를 생성합니다.

    Args:
        request: 인덱스 생성 요청 정보 (UpdateIndexRequestDTO)
            - index_type: 생성할 인덱스 유형 (FLAT, IVF_FLAT, HNSW 등)
            - metric_type: 거리 측정 방식 (L2, IP, COSINE)
            - params: 인덱스별 고유 매개변수 (선택적)
        jwt_data: JWT에서 파싱된 사용자 정보 (자동 의존성 주입)
            - user_id: 사용자 ID
            - group_id: 그룹 ID (멀티테넌시)
            - role_id: 역할 ID (1=관리자만 허용)

    Returns:
        Dict[str, Any]: 인덱스 생성 결과
            - detail: 전체 작업 요약 메시지
            - results: 각 컬렉션별 상세 결과

    Raises:
        HTTPException: 인덱스 생성 실패 시
            - 403: 관리자 권한 부족 (role_id ≠ 1)
            - 404: 존재하지 않는 컬렉션 또는 인덱스 타입
            - 500: Milvus 연결 오류, 인덱스 빌드 실패, 내부 서버 오류
    """
    try:
        # JWT에서 파싱된 값 사용
        user_id = jwt_data["user_id"]
        role_id = jwt_data["role_id"]

        # 관리자 권한 확인 (role_id = 1)
        if role_id != 1:
            logger.warning(
                f"관리자 권한 필요 작업 시도: 사용자 ID {user_id}, 역할 ID {role_id}"
            )
            raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")

        logger.info(
            f"✅ 인덱스 생성 요청 받음: 인덱스 타입={request.index_type}, 사용자 ID={user_id}"
        )

        logger.info(f"✅ 관리자 권한 확인됨: user_id={user_id}, role_id={role_id}")

        # 입력 변수 설정
        input = {
            "index_type": request.index_type,
            "params": request.params,
            "metric_type": request.metric_type,
        }
        logger.debug(f"✅ 인덱스 파라미터: {input}")

        # 인덱스 업데이트 수행
        logger.info("✅ 인덱스 업데이트 작업 시작")
        results = update_index(input)

        # 결과 메시지 설정
        failed_collections = [r for r in results if r["status"] == "failed"]
        if failed_collections:
            detail_msg = f"인덱스 업데이트 완료 (일부 컬렉션에서 오류 발생: {len(failed_collections)}개)"
            logger.warning(f"⚠️ {detail_msg}")
        else:
            detail_msg = f"인덱스 업데이트 완료: {len(results)}개 컬렉션 성공"
            logger.info(f"✅ {detail_msg}")

        return {"detail": detail_msg, "results": results}
    except ValueError as ve:
        logger.warning(f"⚠️ 인덱스 생성 중 값 오류 발생: {ve}")
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ 인덱스 생성 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))
