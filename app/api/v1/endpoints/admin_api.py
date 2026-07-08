"""
관리자 전용 API

Milvus 컬렉션 관리를 위한 관리자 전용 API 엔드포인트를 제공합니다.
모든 엔드포인트는 Admin 권한이 필요합니다.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.crud.milvus.admin_crud import (
    delete_collection_data,
    get_collection_detail,
    list_all_collections,
    modify_meta_data,
    modify_vector_data,
    preview_delete,
    query_collection_data,
)
from app.dto.admin_dto import (
    AdminMetaDataItemDTO,
    AdminMetaSummaryItemDTO,
    AdminVectorDataItemDTO,
    CollectionDetailResponseDTO,
    CollectionListResponseDTO,
    DataDeleteRequestDTO,
    MetaCollectionDataResponseDTO,
    MetaModifyResponseDTO,
    MetaPatchRequestDTO,
    MetaPutRequestDTO,
    MetaSummaryResponseDTO,
    VectorCollectionDataResponseDTO,
    VectorModifyResponseDTO,
    VectorPatchRequestDTO,
    VectorPutRequestDTO,
)
from app.utils.auth_utils import get_parsed_jwt_data
from app.utils.passport_utils.parser import is_admin_role

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        400: {"description": "잘못된 요청 - 요청 매개변수가 유효하지 않습니다."},
        401: {"description": "인증 실패 - 유효한 인증 정보가 필요합니다."},
        403: {"description": "권한 부족 - 관리자 권한이 필요합니다."},
        404: {"description": "찾을 수 없음 - 요청된 리소스가 존재하지 않습니다."},
        500: {"description": "서버 오류 - 서버 내부 오류가 발생했습니다."},
    },
)


def verify_admin_role(request: Request, user_id: int) -> None:
    """
    관리자 권한을 검증합니다.

    Args:
        request: FastAPI Request 객체
        user_id: 사용자 ID

    Raises:
        HTTPException: 관리자 권한이 없는 경우 403
    """
    passport_data = request.state.passport_data
    if not is_admin_role(passport_data):
        logger.warning(f"⚠️ 관리자 권한 필요: user_id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )


@router.get(
    "/collections",
    summary="컬렉션 목록 조회 (관리자 전용)",
    response_model=CollectionListResponseDTO,
    description="""
📋 **컬렉션 목록 조회 (관리자 전용)**

모든 Milvus 컬렉션 목록을 조회합니다.

## 반환 정보
- 컬렉션 이름
- 컬렉션 타입 (meta/vector)
- 그룹 ID
- 레코드 수
    """,
)
async def get_collections(
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=50, ge=1, le=1000, description="페이지 크기"),
) -> Dict[str, Any]:
    """컬렉션 목록을 조회합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"📋 컬렉션 목록 조회: user_id={user_id}")

    collections = await list_all_collections()

    # 페이지네이션 적용
    total = len(collections)
    start = (page - 1) * page_size
    end = start + page_size
    items = collections[start:end]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/collections/{collection_name}",
    summary="컬렉션 상세 조회 (관리자 전용)",
    response_model=CollectionDetailResponseDTO,
    description="""
🔍 **컬렉션 상세 조회 (관리자 전용)**

특정 컬렉션의 상세 정보를 조회합니다.

## 반환 정보
- 컬렉션 이름
- 컬렉션 타입 (meta/vector)
- 레코드 수
- 스키마 필드 목록
- 인덱스 정보
    """,
)
async def get_collection_detail_endpoint(
    collection_name: str,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """컬렉션 상세 정보를 조회합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"🔍 컬렉션 상세 조회: {collection_name}, user_id={user_id}")

    detail = await get_collection_detail(collection_name)

    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"컬렉션을 찾을 수 없습니다: {collection_name}",
        )

    return detail


# Meta 요약 엔드포인트에서 조회할 필드 목록 (7개)
META_SUMMARY_FIELDS = [
    "category",
    "file_type",
    "filename",
    "token",
    "file_size",
    "start_date",
    "status",
]


@router.get(
    "/collections/{collection_name}/meta",
    summary="Meta 컬렉션 요약 데이터 조회 (관리자 전용)",
    response_model=MetaSummaryResponseDTO,
    description="""
📊 **Meta 컬렉션 요약 데이터 조회 (관리자 전용)**

Meta 컬렉션의 경량화된 요약 데이터를 페이지네이션하여 조회합니다.
전체 30개 이상 필드 대신 핵심 7개 필드만 반환합니다.

## 반환 필드
- category: 문서 카테고리
- file_type: 파일 유형
- filename: 파일명
- token: 토큰 사용량
- file_size: 파일 크기
- start_date: 등록일
- status: 처리 상태

## 파라미터
- page: 페이지 번호 (기본값: 1)
- page_size: 페이지 크기 (기본값: 50, 최대: 1000)
- filter_expr: Milvus 필터 표현식 (선택)
    """,
)
async def get_meta(
    collection_name: str,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=50, ge=1, le=1000, description="페이지 크기"),
    filter_expr: Optional[str] = Query(default=None, description="필터 표현식"),
) -> MetaSummaryResponseDTO:
    """Meta 컬렉션 요약 데이터를 조회합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"📊 Meta 컬렉션 요약 조회: {collection_name}, user_id={user_id}")

    result = await query_collection_data(
        collection_name=collection_name,
        filter_expr=filter_expr,
        output_fields=META_SUMMARY_FIELDS,
        page=page,
        page_size=page_size,
    )

    items = [AdminMetaSummaryItemDTO(**item) for item in result["items"]]

    return MetaSummaryResponseDTO(
        items=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get(
    "/collections/{collection_name}/meta/detail",
    summary="Meta 컬렉션 상세 데이터 조회 (관리자 전용)",
    response_model=MetaCollectionDataResponseDTO,
    description="""
📊 **Meta 컬렉션 상세 데이터 조회 (관리자 전용)**

Meta 컬렉션의 전체 필드 데이터를 페이지네이션하여 조회합니다.

## 파라미터
- page: 페이지 번호 (기본값: 1)
- page_size: 페이지 크기 (기본값: 50, 최대: 1000)
- filter_expr: Milvus 필터 표현식 (선택)
    """,
)
async def get_meta_detail(
    collection_name: str,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=50, ge=1, le=1000, description="페이지 크기"),
    filter_expr: Optional[str] = Query(default=None, description="필터 표현식"),
) -> MetaCollectionDataResponseDTO:
    """Meta 컬렉션 상세 데이터를 조회합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"📊 Meta 컬렉션 상세 조회: {collection_name}, user_id={user_id}")

    result = await query_collection_data(
        collection_name=collection_name,
        filter_expr=filter_expr,
        page=page,
        page_size=page_size,
    )

    items = [AdminMetaDataItemDTO(**item) for item in result["items"]]

    return MetaCollectionDataResponseDTO(
        items=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get(
    "/collections/{collection_name}/vector",
    summary="Vector 컬렉션 데이터 조회 (관리자 전용)",
    response_model=VectorCollectionDataResponseDTO,
    description="""
📊 **Vector 컬렉션 데이터 조회 (관리자 전용)**

Vector 컬렉션의 데이터를 페이지네이션하여 조회합니다.

## 파라미터
- page: 페이지 번호 (기본값: 1)
- page_size: 페이지 크기 (기본값: 50, 최대: 1000)
- filter_expr: Milvus 필터 표현식 (선택)
    """,
)
async def get_vector(
    collection_name: str,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=50, ge=1, le=1000, description="페이지 크기"),
    filter_expr: Optional[str] = Query(default=None, description="필터 표현식"),
) -> VectorCollectionDataResponseDTO:
    """Vector 컬렉션 데이터를 조회합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"📊 Vector 컬렉션 데이터 조회: {collection_name}, user_id={user_id}")

    result = await query_collection_data(
        collection_name=collection_name,
        filter_expr=filter_expr,
        page=page,
        page_size=page_size,
    )

    items = [AdminVectorDataItemDTO(**item) for item in result["items"]]

    return VectorCollectionDataResponseDTO(
        items=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.put(
    "/collections/{collection_name}/meta",
    summary="Meta 컬렉션 데이터 전체 교체 (관리자 전용)",
    response_model=MetaModifyResponseDTO,
    description="""
✏️ **Meta 컬렉션 데이터 전체 교체 (관리자 전용)**

Meta 컬렉션의 수정 가능한 필드를 전체 교체합니다.
임베딩 재계산이 필요한 필드(summary, embedding_value)와 시스템 산출 필드는 제외됩니다.

## 수정 가능 필드 (16개)
category, title, filename, status, role_ids, persona_id, group_id, user_id,
file_path, download_url, start_date, end_date, expiration_date,
anonymization_strategy, enable_pii_anonymization, pii_types
    """,
)
async def put_meta(
    collection_name: str,
    request_body: MetaPutRequestDTO,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> MetaModifyResponseDTO:
    """Meta 컬렉션 데이터를 전체 교체합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"✏️ Meta PUT 요청: {collection_name}, user_id={user_id}")

    items = [item.model_dump() for item in request_body.data]

    try:
        result = await modify_meta_data(
            collection_name=collection_name,
            items=items,
            mode="put",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"컬렉션을 찾을 수 없습니다: {collection_name}",
        )

    return MetaModifyResponseDTO(
        collection_name=result["collection_name"],
        modified_count=result["modified_count"],
        items=[AdminMetaDataItemDTO(**item) for item in result["items"]],
    )


@router.put(
    "/collections/{collection_name}/vector",
    summary="Vector 컬렉션 데이터 전체 교체 (관리자 전용)",
    response_model=VectorModifyResponseDTO,
    description="""
✏️ **Vector 컬렉션 데이터 전체 교체 (관리자 전용)**

Vector 컬렉션의 수정 가능한 필드를 전체 교체합니다.
임베딩 재계산이 필요한 필드(parsed_text, embedding_value)와 시스템 산출 필드는 제외됩니다.

## 수정 가능 필드 (6개)
category, title, filename, role_ids, group_id, user_id
    """,
)
async def put_vector(
    collection_name: str,
    request_body: VectorPutRequestDTO,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> VectorModifyResponseDTO:
    """Vector 컬렉션 데이터를 전체 교체합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"✏️ Vector PUT 요청: {collection_name}, user_id={user_id}")

    items = [item.model_dump() for item in request_body.data]

    try:
        result = await modify_vector_data(
            collection_name=collection_name,
            items=items,
            mode="put",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"컬렉션을 찾을 수 없습니다: {collection_name}",
        )

    return VectorModifyResponseDTO(
        collection_name=result["collection_name"],
        modified_count=result["modified_count"],
        items=[AdminVectorDataItemDTO(**item) for item in result["items"]],
    )


@router.patch(
    "/collections/{collection_name}/meta",
    summary="Meta 컬렉션 데이터 부분 수정 (관리자 전용)",
    response_model=MetaModifyResponseDTO,
    description="""
🔧 **Meta 컬렉션 데이터 부분 수정 (관리자 전용)**

Meta 컬렉션의 데이터를 부분 수정합니다. 변경할 필드만 제공하면 됩니다.
임베딩 재계산이 필요한 필드(summary, embedding_value)와 시스템 산출 필드는 제외됩니다.

## 수정 가능 필드 (16개, 모두 Optional)
category, title, filename, status, role_ids, persona_id, group_id, user_id,
file_path, download_url, start_date, end_date, expiration_date,
anonymization_strategy, enable_pii_anonymization, pii_types
    """,
)
async def patch_meta(
    collection_name: str,
    request_body: MetaPatchRequestDTO,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> MetaModifyResponseDTO:
    """Meta 컬렉션 데이터를 부분 수정합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"🔧 Meta PATCH 요청: {collection_name}, user_id={user_id}")

    items = [item.model_dump(exclude_unset=True) for item in request_body.data]

    try:
        result = await modify_meta_data(
            collection_name=collection_name,
            items=items,
            mode="patch",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"컬렉션을 찾을 수 없습니다: {collection_name}",
        )

    return MetaModifyResponseDTO(
        collection_name=result["collection_name"],
        modified_count=result["modified_count"],
        items=[AdminMetaDataItemDTO(**item) for item in result["items"]],
    )


@router.patch(
    "/collections/{collection_name}/vector",
    summary="Vector 컬렉션 데이터 부분 수정 (관리자 전용)",
    response_model=VectorModifyResponseDTO,
    description="""
🔧 **Vector 컬렉션 데이터 부분 수정 (관리자 전용)**

Vector 컬렉션의 데이터를 부분 수정합니다. 변경할 필드만 제공하면 됩니다.
임베딩 재계산이 필요한 필드(parsed_text, embedding_value)와 시스템 산출 필드는 제외됩니다.

## 수정 가능 필드 (6개, 모두 Optional)
category, title, filename, role_ids, group_id, user_id
    """,
)
async def patch_vector(
    collection_name: str,
    request_body: VectorPatchRequestDTO,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> VectorModifyResponseDTO:
    """Vector 컬렉션 데이터를 부분 수정합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"🔧 Vector PATCH 요청: {collection_name}, user_id={user_id}")

    items = [item.model_dump(exclude_unset=True) for item in request_body.data]

    try:
        result = await modify_vector_data(
            collection_name=collection_name,
            items=items,
            mode="patch",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"컬렉션을 찾을 수 없습니다: {collection_name}",
        )

    return VectorModifyResponseDTO(
        collection_name=result["collection_name"],
        modified_count=result["modified_count"],
        items=[AdminVectorDataItemDTO(**item) for item in result["items"]],
    )


@router.delete(
    "/collections/data",
    summary="컬렉션 데이터 삭제 (관리자 전용)",
    description="""
🗑️ **컬렉션 데이터 삭제 (관리자 전용)**

필터 조건에 맞는 데이터를 삭제합니다.

## 미리보기 모드
- preview=True (기본값): 삭제될 데이터만 조회
- preview=False: 실제 삭제 수행

## 주의사항
- 삭제된 데이터는 복구할 수 없습니다.
- 반드시 미리보기로 확인 후 삭제하세요.
    """,
)
async def delete_collection_data_endpoint(
    request_body: DataDeleteRequestDTO,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """컬렉션 데이터를 삭제합니다."""
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(
        f"🗑️ 데이터 삭제 요청: {request_body.collection_name}, "
        f"preview={request_body.preview}, user_id={user_id}"
    )

    if request_body.preview:
        # 미리보기 모드
        result = await preview_delete(
            collection_name=request_body.collection_name,
            filter_expr=request_body.filter_expr,
        )

        # DTO 변환으로 RepeatedScalarContainer -> List 자동 변환
        collection_name = request_body.collection_name
        if "_meta" in collection_name:
            sample_records = [
                AdminMetaDataItemDTO(**item).model_dump()
                for item in result["sample_records"]
            ]
        else:
            sample_records = [
                AdminVectorDataItemDTO(**item).model_dump()
                for item in result["sample_records"]
            ]

        return {
            "collection_name": result["collection_name"],
            "affected_count": result["affected_count"],
            "sample_records": sample_records,
        }
    else:
        # 실제 삭제 모드
        result = await delete_collection_data(
            collection_name=request_body.collection_name,
            filter_expr=request_body.filter_expr,
        )
        logger.info(
            f"✅ 데이터 삭제 완료: {request_body.collection_name}, "
            f"{result['deleted_count']}개 삭제"
        )
        return result
