import logging
from typing import List, Optional, Union

from fastapi import APIRouter, HTTPException, Path, Query, Depends

from app.crud.milvus.document_crud import (
    select_documents,
    count_documents,
    count_vector_documents,
    get_vector_chunk_by_id,
    delete_document,
    select_expiring_documents,
    delete_documents_batch as delete_documents_batch_crud,
)
from app.crud.postgres.user_crud import (
    select_user_full_names_batch,
)
from app.dto.table_dto import (
    DocumentResponseDTO,
    DeleteDocumentsRequestDTO,
    DeletedChunkInfoDTO,
    DocumentMetaResponseDTO,
    DocumentMetaSearchRequestDTO,
    DocumentExpiringResponseDTO,
    DocumentVectorResponseDTO,
    VectorChunkDeleteResponseDTO,
)
from app.dto.pagination_dto import (
    PaginationMetaDTO,
    PaginatedDocumentMetaResponseDTO,
    PaginatedDocumentVectorResponseDTO,
)
from app.dto.category_dto import CombinedCategoryResponseDTO
from app.dto.document_status import DocumentStatus
from app.service import user_category_service
from app.service.opensearch_bm25_service import (
    create_opensearch_client,
    delete_chunk_by_doc_id,
    delete_documents_by_hash,
)
from app.config.database.async_milvus import async_query
from app.dto.chunk_dto import ChunkUpdateRequestDTO, ChunkUpdateResponseDTO
from app.dto.summary_dto import MetaDocUpdateRequestDTO, MetaDocUpdateResponseDTO
from app.service.chunk_edit_service import update_vector_chunk, reindex_bm25_chunk
from app.service.summary_edit_service import update_meta_document
from app.utils.auth_utils import get_parsed_jwt_data
from app.utils.initialization import ensure_collection_loaded

logger = logging.getLogger(__name__)

# 지원되는 정렬 필드 목록 (set: O(1) membership test)
ALLOWED_SORT_FIELDS = {"created_at", "updated_at", "title", "id"}
DEFAULT_SORT_FIELD = "created_at"
DEFAULT_SORT_ORDER = "desc"

router = APIRouter(
    responses={
        400: {"description": "bad request"},
        401: {"description": "unauthorized"},
        404: {"description": "not found"},
        500: {"description": "internal server error"},
    },
)


@router.get(
    "/categories",
    summary="문서 카테고리 목록 조회 (통합)",
    response_model=CombinedCategoryResponseDTO,
    responses={
        200: {
            "description": "성공적으로 카테고리 목록을 조회했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "all_documents": {
                            "name": "전체",
                            "document_count": 20,
                            "total_size": 104857600,
                            "status_counts": {
                                "uploading": 0,
                                "registered": 2,
                                "running": 0,
                                "uploaded": 18,
                                "failed": 0,
                                "skipped": 0,
                                "ocr_required": 0,
                            },
                            "recent_documents": [
                                {
                                    "id": 101,
                                    "title": "계약서A",
                                    "filename": "contract_a.pdf",
                                    "file_type": "pdf",
                                    "status": "uploaded",
                                    "created_at": 1708419600,
                                }
                            ],
                        },
                        "system_categories": [
                            {
                                "id": 1,
                                "name": "계약서",
                                "retention_period": 10,
                                "description": "각종 계약 관련 문서",
                                "total_size": 52428800,
                                "document_count": 15,
                                "recent_documents": [
                                    {
                                        "id": 99,
                                        "title": "NDA_2026",
                                        "filename": "nda.pdf",
                                        "file_type": "pdf",
                                        "status": "uploaded",
                                        "created_at": 1708419600,
                                    }
                                ],
                            }
                        ],
                        "user_categories": [
                            {
                                "id": 103,
                                "user_id": 100,
                                "group_id": 1,
                                "name": "NDA",
                                "description": "비밀유지계약서",
                                "default_retention_period": 10,
                                "parent_id": None,
                                "depth": 1,
                                "path": "103",
                                "created_at": "2026-01-13T09:00:00Z",
                                "updated_at": "2026-01-13T09:00:00Z",
                                "document_count": 5,
                                "recent_documents": [],
                            }
                        ],
                    }
                }
            },
        }
    },
    description="""
**문서 카테고리 목록 조회 (시스템 + 사용자 통합)**

시스템 기본 카테고리와 사용자 정의 카테고리를 함께 조회합니다.
각 카테고리별 저장된 문서 수와 총 용량 정보를 함께 제공합니다.

## 응답 구조
- **all_documents**: 전체 문서 통합 요약 (통계 + 최근 문서 3건)
- **system_categories**: 시스템 기본 카테고리 목록 (각 카테고리별 최근 문서 3건 포함)
- **user_categories**: 사용자 정의 카테고리 목록 (각 카테고리별 최근 문서 3건 포함)

## 권한 체계
- **user_id**: 개인 문서만 조회
- **group_id**: 같은 그룹 문서 조회
- **role_id**: 역할에 따른 접근 범위 결정
    """,
)
async def get_document_categories_list(
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> CombinedCategoryResponseDTO:
    """
    시스템 카테고리와 사용자 카테고리를 통합하여 조회합니다.

    Args:
        jwt_data: JWT에서 파싱된 사용자 정보 (자동 의존성 주입)
            - user_id: 사용자 ID
            - group_id: 그룹 ID (멀티테넌시)
            - role_id: 역할 ID (권한 레벨)

    Returns:
        CombinedCategoryResponseDTO: 통합 카테고리 목록
            - system_categories: 시스템 카테고리 목록
            - user_categories: 사용자 카테고리 목록

    Raises:
        HTTPException: 카테고리 조회 실패 시
            - 404: 카테고리 정보 없음
            - 500: 데이터베이스 연결 오류, 내부 서버 오류
    """
    try:
        # JWT에서 파싱된 값 사용
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        # 통합 카테고리 조회 (Service 활용)
        combined = await user_category_service.get_combined_categories(
            user_id=user_id,
            group_id=group_id,
            role_ids=total_role,
        )

        return CombinedCategoryResponseDTO(**combined)

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"카테고리 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"카테고리 목록 조회 실패: {str(e)}"
        )


@router.get(
    "/meta",
    summary="문서 메타데이터 조회 (페이징)",
    response_model=PaginatedDocumentMetaResponseDTO,
    responses={
        200: {
            "description": "성공적으로 문서 메타데이터를 조회했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": 123,
                                "category": "계약서",
                                "title": "2024년 근로계약서",
                                "filename": "근로계약서_2024_김철수.pdf",
                                "summary": "본 계약서는 2024년도 정규직 근로자의 고용 조건을 명시합니다...",
                                "file_type": "pdf",
                                "file_size": 1048576,
                                "status": "completed",
                                "role_ids": [3],
                                "persona_id": 5,
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
                            }
                        ],
                        "pagination": {
                            "total_count": 150,
                            "total_pages": 15,
                            "current_page": 1,
                            "page_size": 10,
                            "has_next": True,
                            "has_previous": False,
                        },
                    }
                }
            },
        }
    },
    description="""
📄 **문서 메타데이터 조회 (페이징)**

사용자의 권한 범위 내에서 문서 메타데이터를 페이징하여 조회합니다.
문서의 기본 정보(제목, 카테고리, 파일 크기, 업로드 시간 등)를 확인할 수 있습니다.

## 페이징 파라미터
- **page**: 페이지 번호 (1부터 시작, 기본값: 1)
- **page_size**: 페이지당 항목 수 (기본값: 10, 최대: 50)
- **sort_by**: 정렬 기준 필드 (created_at, updated_at, title, id / 기본값: created_at)
- **sort_order**: 정렬 방향 (asc/desc, 기본값: desc)

## 필터링 옵션
- **카테고리**: 특정 카테고리의 문서만 조회
- **제목**: 제목에 특정 키워드가 포함된 문서 검색
- **해시**: 특정 파일 해시값으로 정확한 문서 조회

## 권한 체계
- 사용자는 자신의 그룹 및 역할에 따라 제한된 문서만 조회 가능
- 멀티테넌시 환경에서 그룹별 격리 보장

## Milvus 제한사항
- offset + limit < 16,384 (page_size=50 기준 최대 327페이지)
    """,
)
async def get_meta_info(
    jwt_data: dict = Depends(get_parsed_jwt_data),
    page: int = Query(default=1, ge=1, description="페이지 번호 (1부터 시작)"),
    page_size: int = Query(default=10, ge=1, le=50, description="페이지당 항목 수 (최대 50)"),
    sort_by: str = Query(default="created_at", description="정렬 기준 필드 (created_at, updated_at, title, id)"),
    sort_order: str = Query(default="desc", description="정렬 방향 (asc/desc)"),
    category_option: Optional[str] = Query(
        default=None, description="카테고리 필터링 옵션"
    ),
    title_option: Optional[str] = Query(default=None, description="제목 필터링 옵션"),
    hash_sha256_option: Optional[str] = Query(
        default=None, description="해시 필터링 옵션"
    ),
    persona_id_option: Optional[int] = Query(
        default=None, description="페르소나 ID 필터링 옵션"
    ),
    filename_option: Optional[str] = Query(
        default=None, description="파일명 필터링 옵션"
    ),
    status_option: Optional[str] = Query(
        default=None, description="문서 상태 필터링 옵션 (uploading, registered, running, uploaded, failed, skipped, ocr_required)"
    ),
) -> PaginatedDocumentMetaResponseDTO:
    """GET 방식 문서 메타데이터 조회 (단순 필터용)"""
    return await _search_documents_meta(
        jwt_data=jwt_data,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        category_option=category_option,
        title_option=title_option,
        hash_sha256_option=hash_sha256_option,
        persona_id_option=persona_id_option,
        filename_option=filename_option,
        status_option=status_option,
    )


@router.post(
    "/meta/search",
    summary="문서 메타데이터 검색 (POST body)",
    response_model=PaginatedDocumentMetaResponseDTO,
    description="""\
**문서 메타데이터 검색 (POST body)**

GET `/meta`와 동일한 기능을 POST body로 제공합니다.
hash_sha256_option을 리스트로 전달하여 여러 문서를 한번에 조회할 수 있습니다.

## 사용 예시

```json
{
  "hash_sha256_option": ["abc123", "def456", "ghi789"],
  "category_option": "계약서",
  "page": 1,
  "page_size": 20
}
```

## GET /meta와의 차이

| 항목 | GET /meta | POST /meta/search |
|------|-----------|-------------------|
| hash_sha256_option | 단일 문자열 | 문자열 리스트 (복수 지정) |
| 전달 방식 | Query Parameter | Request Body (JSON) |
| 적합 상황 | 단순 필터 조회 | 복합 필터, 다수 해시 조회 |
    """,
)
async def search_meta_info(
    request: DocumentMetaSearchRequestDTO,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> PaginatedDocumentMetaResponseDTO:
    """POST 방식 문서 메타데이터 검색 (복합 필터, 해시 리스트 지원)"""
    return await _search_documents_meta(
        jwt_data=jwt_data,
        page=request.page,
        page_size=request.page_size,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
        category_option=request.category_option,
        title_option=request.title_option,
        hash_sha256_option=request.hash_sha256_option,
        persona_id_option=request.persona_id_option,
        filename_option=request.filename_option,
        status_option=request.status_option,
    )


async def _search_documents_meta(
    jwt_data: dict,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    category_option: Optional[str] = None,
    title_option: Optional[str] = None,
    hash_sha256_option: Optional[Union[str, List[str]]] = None,
    persona_id_option: Optional[int] = None,
    filename_option: Optional[str] = None,
    status_option: Optional[str] = None,
) -> PaginatedDocumentMetaResponseDTO:
    """GET/POST 공통 문서 메타데이터 조회 로직"""
    try:
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        role_ids = jwt_data["total_role"]

        offset = (page - 1) * page_size

        # status_option 유효성 검증 (GET 경로에서만 필요, POST는 DTO validator가 처리)
        if status_option:
            valid_statuses = DocumentStatus.get_all_values()
            if status_option not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"유효하지 않은 문서 상태: '{status_option}'. 가능한 값: {', '.join(valid_statuses)}"
                )

        total_count = await count_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=role_ids,
            category_option=category_option,
            title_option=title_option,
            hash_sha256_option=hash_sha256_option,
            persona_id_option=persona_id_option,
            filename_option=filename_option,
            status_option=status_option,
        )

        result = await select_documents(
            group_id,
            user_id,
            role_ids,
            db_type="meta",
            category_option=category_option,
            title_option=title_option,
            hash_sha256_option=hash_sha256_option,
            persona_id_option=persona_id_option,
            filename_option=filename_option,
            status_option=status_option,
            limit=page_size,
            offset=offset,
        )

        # 정렬 처리 (애플리케이션 레벨)
        effective_sort_by = sort_by if sort_by in ALLOWED_SORT_FIELDS else DEFAULT_SORT_FIELD
        effective_sort_order = sort_order.lower() if sort_order.lower() in ("asc", "desc") else DEFAULT_SORT_ORDER
        reverse = effective_sort_order == "desc"
        if result and effective_sort_by in result[0]:
            result = sorted(result, key=lambda x: x[effective_sort_by] or "", reverse=reverse)

        # user_full_name 배치 조회 (N+1 방지)
        if result:
            user_ids = list({item["user_id"] for item in result})
            user_names = await select_user_full_names_batch(user_ids)
            for item in result:
                item["user_full_name"] = user_names[item["user_id"]]

        # 페이징 메타데이터
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

        pagination = PaginationMetaDTO(
            total_count=total_count,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

        items = [DocumentMetaResponseDTO(**item) for item in result]
        return PaginatedDocumentMetaResponseDTO(items=items, pagination=pagination)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/vector",
    summary="문서 벡터 데이터 조회",
    response_model=PaginatedDocumentVectorResponseDTO,
    description="""
📊 **문서 벡터 데이터 조회**

문서의 벡터 데이터(청크)를 조회합니다.
각 문서는 여러 개의 청크로 분할되어 저장되며, 각 청크별로 벡터 임베딩이 생성됩니다.

## 필터링 옵션
- **id**: Milvus PK로 특정 청크 1건 조회
- **page_number**: 페이지 번호 필터
- **chunk_index**: 청크 인덱스 필터
- **keyword**: 텍스트 키워드 검색
- **카테고리/제목/해시**: 기존 필터 유지

## 페이지네이션
- **page**: 페이지 번호 (기본: 1)
- **page_size**: 페이지당 건수 (기본: 20, 최대: 50)
    """,
)
async def get_vector_info(
    jwt_data: dict = Depends(get_parsed_jwt_data),
    category_option: Optional[str] = Query(
        default=None, description="카테고리 필터링 옵션"
    ),
    title_option: Optional[str] = Query(default=None, description="제목 필터링 옵션"),
    hash_sha256_option: Optional[str] = Query(
        default=None, description="해시 필터링 옵션"
    ),
    id: Optional[int] = Query(default=None, description="벡터 ID(Milvus PK)로 단건 조회"),
    page_number: Optional[int] = Query(default=None, description="페이지 번호 필터"),
    chunk_index: Optional[int] = Query(default=None, description="청크 인덱스 필터"),
    keyword: Optional[str] = Query(default=None, description="텍스트 키워드 검색"),
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=20, ge=1, description="페이지당 건수"),
) -> PaginatedDocumentVectorResponseDTO:
    """
    문서 벡터 데이터를 조회합니다 (페이지네이션 + 필터 지원).

    Args:
        jwt_data: JWT에서 파싱된 사용자 정보 (자동 의존성 주입)
        category_option: 카테고리 필터링 (선택적)
        title_option: 제목 필터링 (선택적)
        hash_sha256_option: 해시 필터링 (선택적)
        id: Milvus PK로 단건 조회 (선택적)
        page_number: 페이지 번호 필터 (선택적)
        chunk_index: 청크 인덱스 필터 (선택적)
        keyword: 텍스트 키워드 검색 (선택적)
        page: 페이지 번호 (기본: 1)
        page_size: 페이지당 건수 (기본: 20, 최대: 50)

    Returns:
        PaginatedDocumentVectorResponseDTO: 페이징된 벡터 데이터

    Raises:
        HTTPException: 문서 조회 실패 시
    """
    try:
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        role_ids = jwt_data["total_role"]

        # page_size 상한 적용
        page_size = min(page_size, 50)
        offset = (page - 1) * page_size

        filter_kwargs = {
            "category_option": category_option,
            "title_option": title_option,
            "hash_sha256_option": hash_sha256_option,
            "id_option": id,
            "page_number_option": page_number,
            "chunk_index_option": chunk_index,
            "keyword_option": keyword,
        }

        # 카운트 조회
        total_count = await count_vector_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=role_ids,
            **filter_kwargs,
        )

        # 데이터 조회
        result = await select_documents(
            group_id,
            user_id,
            role_ids,
            db_type="vector",
            limit=page_size,
            offset=offset,
            **filter_kwargs,
        )

        # 페이지네이션 메타 구성
        import math
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        pagination = PaginationMetaDTO(
            total_count=total_count,
            total_pages=total_pages,
            current_page=page,
            page_size=page_size,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

        items = [DocumentVectorResponseDTO(**item) for item in result]
        return PaginatedDocumentVectorResponseDTO(items=items, pagination=pagination)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/vector/{id}",
    summary="청크 텍스트 수정",
    response_model=ChunkUpdateResponseDTO,
    description="""
✏️ **청크 텍스트 수정**

특정 청크의 parsed_text를 수정합니다.
임베딩 벡터는 내부에서 자동 갱신되며, Milvus + OpenSearch 양쪽에 반영됩니다.
    """,
)
async def update_chunk_text(
    id: int = Path(..., description="벡터 ID (Milvus PK)"),
    body: ChunkUpdateRequestDTO = ...,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ChunkUpdateResponseDTO:
    """
    청크 텍스트를 수정합니다.

    Args:
        id: 수정할 청크의 Milvus PK
        body: 수정할 텍스트
        jwt_data: JWT 인증 정보

    Returns:
        ChunkUpdateResponseDTO: 수정 결과

    Raises:
        HTTPException: 404 (미존재), 403 (권한 없음), 500 (서버 오류)
    """
    try:
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        # 1. 기존 청크 조회
        chunk = await get_vector_chunk_by_id(group_id=group_id, chunk_id=id)
        if not chunk:
            raise HTTPException(status_code=404, detail="청크를 찾을 수 없습니다.")

        # 2. 권한 검증
        item_role_ids = chunk["role_ids"]
        if not set(total_role) & set(item_role_ids):
            raise HTTPException(status_code=403, detail="해당 청크에 대한 수정 권한이 없습니다.")

        # 3. 원본 텍스트 로깅 (FR-4)
        logger.info(
            f"📝 청크 텍스트 수정: id={id}, 원본='{chunk['parsed_text'][:100]}...'"
        )

        # 4. meta 컬렉션에서 expiration_date 조회 (BM25 재색인에 필요)
        user_id = jwt_data["user_id"]
        meta_results = await select_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=total_role,
            db_type="meta",
            hash_sha256_option=chunk["hash_sha256"],
            limit=1,
        )
        if not meta_results:
            raise HTTPException(
                status_code=404,
                detail=f"문서 메타데이터를 찾을 수 없습니다: hash={chunk['hash_sha256']}",
            )
        expiration_date = meta_results[0]["expiration_date"]

        # 5. Milvus 업데이트 (임베딩 자동 갱신 + token/cost 재계산)
        new_id = await update_vector_chunk(
            group_id=group_id,
            chunk_data=chunk,
            new_parsed_text=body.parsed_text,
        )

        # 6. OpenSearch BM25 재색인 (새 ID 반영)
        bm25_sync_status = "success"
        bm25_chunk_data = {**chunk, "id": new_id}
        try:
            await reindex_bm25_chunk(
                group_id=group_id,
                chunk_data=bm25_chunk_data,
                new_parsed_text=body.parsed_text,
                expiration_date=expiration_date,
            )
        except Exception as bm25_error:
            logger.error(f"⚠️ BM25 재색인 실패: id={new_id}, {bm25_error}")
            bm25_sync_status = "failed"

        # 7. 응답 (새 ID 반환)
        return ChunkUpdateResponseDTO(
            id=new_id,
            parsed_text=body.parsed_text,
            chunk_index=chunk["chunk_index"],
            page_number=chunk["page_number"],
            hash_sha256=chunk["hash_sha256"],
            title=chunk["title"],
            filename=chunk["filename"],
            bm25_sync_status=bm25_sync_status,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/expiring",
    summary="만료 임박 문서 목록 조회",
    response_model=List[DocumentExpiringResponseDTO],
    responses={
        200: {
            "description": "성공적으로 만료 임박 문서를 조회했습니다.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 123,
                            "category": "계약서",
                            "title": "2024년 임시 계약서",
                            "filename": "임시계약서_2024.pdf",
                            "summary": "2024년도 임시직 계약 조건을 명시한 문서입니다...",
                            "file_type": "pdf",
                            "file_size": 524288,
                            "status": "completed",
                            "role_id": 3,
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
                        }
                    ]
                }
            },
        }
    },
    description="""
⏰ **만료 임박 문서 조회**

보관기간이 지정된 일수 이내로 만료되는 문서 목록을 조회합니다.
문서 관리 및 갱신 계획 수립에 유용합니다.

## 기능
- 만료 예정일 기준으로 문서 필터링
- 사용자 권한에 따른 접근 제어
- 관리자는 모든 만료 문서, 일반 사용자는 본인 문서만 조회
    """,
)
async def get_expiring_documents(
    jwt_data: dict = Depends(get_parsed_jwt_data),
    days_before_expiration: int = Query(default=7, description="만료 전 확인할 일수"),
) -> List[DocumentExpiringResponseDTO]:
    """
    만료 임박 문서 목록을 조회합니다.

    Args:
        jwt_data: JWT에서 파싱된 사용자 정보 (자동 의존성 주입)
            - user_id: 사용자 ID
            - group_id: 그룹 ID (멀티테넌시)
            - role_id: 역할 ID (권한 레벨)
        days_before_expiration: 만료 전 확인할 일수 (기본값: 7일)
            - 현재 날짜로부터 몇 일 이내 만료되는 문서를 조회할지 설정

    Returns:
        List[Dict]: 만료 임박 문서 목록
            - id: 문서 ID
            - title: 문서 제목
            - category: 카테고리
            - expiration_date: 만료일
            - days_until_expiration: 만료까지 남은 일수

    Raises:
        HTTPException: 문서 조회 실패 시
            - 404: 만료 임박 문서 없음
            - 500: 데이터베이스 연결 오류, 내부 서버 오류
    """
    try:
        # JWT에서 파싱된 값 사용
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        # role_id를 리스트로 변환하여 전달
        role_ids = total_role

        result = await select_expiring_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=role_ids,
            days_before_expiration=days_before_expiration,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/meta/{id}",
    summary="메타 문서 수정 (요약 수정 시 임베딩 자동 갱신)",
    response_model=MetaDocUpdateResponseDTO,
    description="""
✏️ **메타 문서 수정**

메타 문서의 제목, 카테고리, 만료일, 요약을 수정합니다.
summary 수정 시 임베딩 벡터 + 토큰 + 비용이 자동 재계산됩니다.

## 수정 가능한 필드
- `title`: 문서 제목
- `category`: 문서 카테고리
- `expiration_date`: 문서 만료일
- `summary`: 문서 요약 (수정 시 임베딩 자동 갱신)
    """,
)
async def update_meta_doc(
    id: int = Path(..., description="메타 문서 ID (Milvus PK)"),
    body: MetaDocUpdateRequestDTO = ...,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> MetaDocUpdateResponseDTO:
    """
    메타 문서를 수정합니다.

    Args:
        id: 수정할 메타 문서의 Milvus PK
        body: 수정할 필드 (전달된 필드만 업데이트)
        jwt_data: JWT 인증 정보

    Returns:
        MetaDocUpdateResponseDTO: 수정 결과

    Raises:
        HTTPException: 404 (미존재), 403 (권한 없음), 500 (서버 오류)
    """
    try:
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        result = await update_meta_document(
            group_id=group_id,
            doc_id=id,
            request=body,
            role_ids=total_role,
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/",
    summary="문서 삭제",
    response_model=DocumentResponseDTO,
    responses={
        200: {
            "description": "성공적으로 문서를 삭제했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Documents deleted successfully.",
                        "code": 200,
                    }
                }
            },
        }
    },
    description="""
🗑️ **문서 일괄 삭제**

여러 해시값을 가진 문서들을 한 번에 삭제합니다.
메타데이터와 벡터 데이터를 모두 제거합니다.

## 삭제 과정
1. 해시값으로 문서 식별
2. 벡터 데이터베이스에서 임베딩 데이터 삭제
3. 메타데이터 데이터베이스에서 문서 정보 삭제
    """,
)
async def delete_documents_batch(
    request: DeleteDocumentsRequestDTO = ...,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> DocumentResponseDTO:
    """
    여러 문서를 일괄 삭제합니다.

    Args:
        request: 삭제 요청 정보 (DeleteDocumentsRequestDTO)
            - hash_sha256_list: 삭제할 문서들의 해시값 목록
        jwt_data: JWT에서 파싱된 사용자 정보 (자동 의존성 주입)
            - user_id: 사용자 ID
            - group_id: 그룹 ID (멀티테넌시)
            - role_id: 역할 ID (권한 레벨)

    Returns:
        DocumentResponseDTO: 문서 삭제 결과
            - message: 처리 결과 메시지
            - code: 응답 코드 (200: 성공)

    Raises:
        HTTPException: 문서 삭제 실패 시
            - 404: 삭제할 문서를 찾을 수 없음
            - 403: 권한 부족
            - 500: 데이터베이스 연결 오류, 내부 서버 오류
    """
    os_client = None
    try:
        # JWT에서 파싱된 값 사용
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        logger.info(
            f"🗑️ 문서 삭제 요청: user_id={user_id}, group_id={group_id}, "
            f"대상 문서={len(request.hash_sha256_list)}개"
        )

        # 1. 권한 확인: 사용자가 접근 가능한 문서만 조회
        authorized_docs = await select_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=total_role,
            db_type="meta",
            hash_sha256_option=request.hash_sha256_list,
        )

        # 권한이 있는 문서의 hash_sha256 목록 추출
        authorized_hashes = {doc["hash_sha256"] for doc in authorized_docs}

        # 권한이 없는 문서 확인
        unauthorized_hashes = set(request.hash_sha256_list) - authorized_hashes
        if unauthorized_hashes:
            logger.warning(
                f"⚠️ 권한 없는 문서 삭제 시도: user_id={user_id}, "
                f"unauthorized={len(unauthorized_hashes)}개"
            )

        if not authorized_hashes:
            raise HTTPException(
                status_code=403,
                detail="삭제 권한이 있는 문서가 없습니다.",
            )

        # 2. 권한이 있는 문서만 배치 삭제 (성능 최적화)
        delete_result = await delete_documents_batch_crud(
            group_id=group_id,
            hash_sha256_list=list(authorized_hashes),
        )

        logger.info(
            f"✅ Milvus 문서 배치 삭제 완료: "
            f"vector={delete_result['vector_deleted']}개, "
            f"meta={delete_result['meta_deleted']}개, "
            f"권한없음={len(unauthorized_hashes)}개"
        )

        # 3. OpenSearch BM25 인덱스에서도 해당 문서들 제거 (권한 확인된 문서만)
        try:
            os_client = create_opensearch_client()

            removed_count = delete_documents_by_hash(
                client=os_client,
                group_id=group_id,
                hash_list=list(authorized_hashes),
            )
            logger.info(
                f"✅ OpenSearch BM25 인덱스 문서 제거 완료: group_id={group_id}, "
                f"제거={removed_count}개"
            )
        except Exception as os_error:
            # BM25 인덱스 업데이트 실패해도 문서 삭제는 완료된 것으로 처리
            logger.warning(f"⚠️ OpenSearch BM25 인덱스 업데이트 실패 (무시): {os_error}")

        # 권한 없는 문서가 있었다면 부분 성공 메시지 반환
        if unauthorized_hashes:
            return DocumentResponseDTO(
                message=f"부분 삭제 완료: {len(authorized_hashes)}개 삭제, "
                f"{len(unauthorized_hashes)}개 권한 없음",
                code=200,
            )

        return DocumentResponseDTO(message="Documents deleted successfully.", code=200)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os_client:
            os_client.close()


@router.delete(
    "/vector/{id}",
    summary="벡터 청크 삭제",
    response_model=VectorChunkDeleteResponseDTO,
    description="""
벡터 컬렉션의 특정 청크를 삭제합니다.
Milvus vector 컬렉션과 OpenSearch BM25 인덱스 양쪽에서 해당 청크를 제거합니다.
    """,
)
async def delete_vector_chunk(
    id: int = Path(..., description="벡터 ID (Milvus PK)"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> VectorChunkDeleteResponseDTO:
    """
    벡터 청크를 삭제합니다 (Milvus + BM25 동기화).

    Args:
        id: 삭제할 청크의 Milvus PK
        jwt_data: JWT 인증 정보

    Returns:
        VectorChunkDeleteResponseDTO: 삭제 결과

    Raises:
        HTTPException: 404 (미존재), 403 (권한 없음), 500 (서버 오류)
    """
    os_client = None
    try:
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]
        total_role = jwt_data["total_role"]

        collection_name = f"TB_{group_id}_vector"

        # 1. 청크 조회 (권한 검증 + BM25 삭제용 hash/chunk_index 확보)
        await ensure_collection_loaded(collection_name, "vector")
        results = await async_query(
            collection_name=collection_name,
            filter=f"id == {id}",
            output_fields=["id", "hash_sha256", "title", "chunk_index", "role_ids"],
        )

        if not results:
            raise HTTPException(status_code=404, detail="청크를 찾을 수 없습니다.")

        chunk = results[0]

        # 2. RBAC 권한 검증
        item_role_ids = chunk.get("role_ids", [])
        if not set(total_role) & set(item_role_ids):
            logger.warning(
                f"권한 없는 청크 삭제 시도: user_id={user_id}, chunk_id={id}"
            )
            raise HTTPException(
                status_code=403, detail="해당 청크에 대한 삭제 권한이 없습니다."
            )

        # 3. Milvus vector 컬렉션에서 삭제
        await delete_document(collection_name, "vector", {"id": id})

        logger.info(f"Milvus 청크 삭제 완료: user_id={user_id}, chunk_id={id}")

        # 4. OpenSearch BM25 인덱스에서 해당 청크 삭제
        bm25_deleted = False
        try:
            os_client = create_opensearch_client()
            deleted = delete_chunk_by_doc_id(
                client=os_client,
                group_id=group_id,
                hash_sha256=chunk["hash_sha256"],
                chunk_index=chunk["chunk_index"],
            )
            bm25_deleted = deleted > 0
            logger.info(
                f"BM25 청크 삭제 완료: chunk_id={id}, bm25_deleted={bm25_deleted}"
            )
        except Exception as bm25_error:
            logger.warning(f"BM25 청크 삭제 실패 (무시): {bm25_error}")

        return VectorChunkDeleteResponseDTO(
            message="Vector chunk deleted successfully.",
            code=200,
            deleted_chunk=DeletedChunkInfoDTO(
                id=chunk["id"],
                hash_sha256=chunk["hash_sha256"],
                title=chunk["title"],
                chunk_index=chunk["chunk_index"],
                bm25_deleted=bm25_deleted,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os_client:
            os_client.close()
