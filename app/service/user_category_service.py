"""
사용자 정의 카테고리 서비스

사용자 카테고리 관련 비즈니스 로직을 처리합니다.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.crud.postgres.user_category_crud import user_category_crud
from app.crud.postgres.user_crud import select_document_categories
from app.crud.milvus.document_crud import select_documents
from app.dto.category_dto import (
    UserCategoryCreateDTO,
    UserCategoryUpdateDTO,
)
from app.dto.document_status import DocumentStatus

logger = logging.getLogger(__name__)


_RECENT_DOC_FIELDS = ("id", "title", "filename", "file_type", "status")


def _get_default_status_counts() -> Dict[str, int]:
    """기본 status_counts 딕셔너리 생성"""
    return {s.value: 0 for s in DocumentStatus}


def _extract_recent_documents(
    documents: List[Dict[str, Any]],
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    문서 목록에서 최근 등록순(start_date 내림차순) 상위 N건을 추출합니다.

    Args:
        documents: 문서 dict 리스트 (start_date 필드 포함)
        limit: 추출할 최대 건수

    Returns:
        List[Dict]: RecentDocumentDTO 필드 구조의 dict 리스트
    """
    if not documents:
        return []

    sorted_docs = sorted(documents, key=lambda d: d["start_date"], reverse=True)
    return [
        {field: doc[field] for field in _RECENT_DOC_FIELDS}
        | {"created_at": doc["start_date"]}
        for doc in sorted_docs[:limit]
    ]


def _build_all_documents_summary(
    documents: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    전체 문서의 통합 요약(통계 + 최근 문서)을 생성합니다.

    Args:
        documents: 전체 문서 dict 리스트

    Returns:
        Dict: AllDocumentsSummaryDTO 필드 구조의 dict
    """
    status_counts = _get_default_status_counts()
    total_size = 0

    for doc in documents:
        status_counts[doc["status"]] += 1
        total_size += doc["file_size"]

    return {
        "name": "전체",
        "document_count": len(documents),
        "total_size": total_size,
        "status_counts": status_counts,
        "recent_documents": _extract_recent_documents(documents),
    }


async def get_system_templates() -> List[Dict[str, Any]]:
    """
    시스템 템플릿 카테고리 목록을 조회합니다.

    Returns:
        List[Dict[str, Any]]: 시스템 카테고리 목록

    Raises:
        HTTPException: 조회 중 오류 발생 시
    """
    try:
        categories = await select_document_categories()

        logger.info(f"시스템 템플릿 조회 완료: {len(categories)}개")

        return categories

    except Exception as e:
        logger.error(f"시스템 템플릿 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="시스템 템플릿 조회 중 오류가 발생했습니다.",
        )


async def get_user_categories(
    user_id: int,
    group_id: int,
    role_ids: List[int],
) -> List[Dict[str, Any]]:
    """
    사용자의 카테고리 목록을 조회합니다.

    각 카테고리별 문서 수도 함께 계산합니다.

    Args:
        user_id: 사용자 ID
        group_id: 그룹 ID
        role_ids: 역할 ID 목록

    Returns:
        List[Dict[str, Any]]: 사용자 카테고리 목록

    Raises:
        HTTPException: 조회 중 오류 발생 시
    """
    try:
        # 병렬 조회 (카테고리 + 문서)
        categories, documents = await asyncio.gather(
            user_category_crud.select_categories_by_user(
                user_id=user_id,
                include_all=True,
            ),
            select_documents(
                group_id=group_id,
                user_id=user_id,
                role_ids=role_ids,
                db_type="meta",
                use_iterator=True,
            ),
        )

        # 카테고리별 통계 계산 (defaultdict 사용 - O(1) lookup)
        category_stats = defaultdict(
            lambda: {"document_count": 0, "status_counts": _get_default_status_counts()}
        )
        for doc in documents:
            stats = category_stats[doc["category"]]
            stats["document_count"] += 1
            stats["status_counts"][doc["status"]] += 1

        # 카테고리에 통계 추가
        for category in categories:
            stats = category_stats[category["name"]]
            category["document_count"] = stats["document_count"]
            category["status_counts"] = stats["status_counts"]

        logger.info(f"사용자 카테고리 조회 완료: user_id={user_id}, count={len(categories)}")

        return categories

    except Exception as e:
        logger.error(f"사용자 카테고리 조회 중 오류: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"사용자 카테고리 조회 중 오류가 발생했습니다: {str(e)}",
        )


async def create_user_category(
    user_id: int,
    group_id: int,
    data: UserCategoryCreateDTO,
) -> Dict[str, Any]:
    """
    새 사용자 카테고리를 생성합니다.

    Args:
        user_id: 사용자 ID
        group_id: 그룹 ID
        data: 카테고리 생성 데이터

    Returns:
        Dict[str, Any]: 생성된 카테고리 정보

    Raises:
        HTTPException: 생성 중 오류 발생 시
    """
    try:
        category = await user_category_crud.create_category(
            user_id=user_id,
            group_id=group_id,
            name=data.name,
            description=data.description,
            default_retention_period=data.default_retention_period,
            parent_id=data.parent_id,
        )

        # 새 카테고리는 문서 없음
        category["document_count"] = 0
        category["status_counts"] = _get_default_status_counts()

        logger.info(f"사용자 카테고리 생성 완료: user_id={user_id}, name={data.name}")

        return category

    except ValueError as e:
        logger.warning(f"카테고리 생성 실패 (유효성 오류): {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"카테고리 생성 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리 생성 중 오류가 발생했습니다.",
        )


async def update_user_category(
    category_id: int,
    user_id: int,
    data: UserCategoryUpdateDTO,
) -> Dict[str, Any]:
    """
    사용자 카테고리를 수정합니다.

    Args:
        category_id: 카테고리 ID
        user_id: 사용자 ID
        data: 카테고리 수정 데이터

    Returns:
        Dict[str, Any]: 수정된 카테고리 정보

    Raises:
        HTTPException: 수정 중 오류 발생 시
    """
    try:
        update_dict = data.model_dump(exclude_unset=True)

        if not update_dict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="수정할 내용이 없습니다.",
            )

        category = await user_category_crud.update_category(
            category_id=category_id,
            user_id=user_id,
            update_data=update_dict,
        )

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"카테고리를 찾을 수 없습니다: id={category_id}",
            )

        logger.info(f"사용자 카테고리 수정 완료: id={category_id}")

        return category

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"카테고리 수정 실패 (유효성 오류): {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"카테고리 수정 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리 수정 중 오류가 발생했습니다.",
        )


async def delete_user_category(
    category_id: int,
    user_id: int,
    group_id: int,
    role_ids: List[int],
) -> bool:
    """
    사용자 카테고리를 삭제합니다.

    하위 카테고리가 있거나 해당 카테고리에 문서가 있으면 삭제할 수 없습니다.

    Args:
        category_id: 카테고리 ID
        user_id: 사용자 ID
        group_id: 그룹 ID
        role_ids: 역할 ID 목록

    Returns:
        bool: 삭제 성공 여부

    Raises:
        HTTPException: 삭제 중 오류 발생 시
    """
    try:
        # 카테고리 조회
        category = await user_category_crud.select_category_by_id(
            category_id=category_id,
            user_id=user_id,
        )

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"카테고리를 찾을 수 없습니다: id={category_id}",
            )

        # 해당 카테고리에 문서가 있는지 확인
        documents = await select_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=role_ids,
            db_type="meta",
            category_option=category["name"],
            use_iterator=True,
        )

        if documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"해당 카테고리에 {len(documents)}개의 문서가 있습니다. 먼저 문서를 이동하거나 삭제해주세요.",
            )

        # 삭제 실행
        success = await user_category_crud.delete_category(
            category_id=category_id,
            user_id=user_id,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"카테고리를 찾을 수 없습니다: id={category_id}",
            )

        logger.info(f"사용자 카테고리 삭제 완료: id={category_id}")

        return True

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"카테고리 삭제 실패 (유효성 오류): {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"카테고리 삭제 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리 삭제 중 오류가 발생했습니다.",
        )


async def get_user_category_tree(
    user_id: int,
    group_id: int,
    role_ids: List[int],
) -> List[Dict[str, Any]]:
    """
    사용자의 카테고리를 트리 구조로 조회합니다.

    Args:
        user_id: 사용자 ID
        group_id: 그룹 ID
        role_ids: 역할 ID 목록

    Returns:
        List[Dict[str, Any]]: 트리 구조의 카테고리 목록

    Raises:
        HTTPException: 조회 중 오류 발생 시
    """
    try:
        # 병렬 조회 (트리 + 문서)
        tree, documents = await asyncio.gather(
            user_category_crud.select_category_tree(user_id=user_id),
            select_documents(
                group_id=group_id,
                user_id=user_id,
                role_ids=role_ids,
                db_type="meta",
                use_iterator=True,
            ),
        )

        # 카테고리별 통계 계산 (defaultdict 사용 - O(1) lookup)
        category_stats = defaultdict(
            lambda: {"document_count": 0, "status_counts": _get_default_status_counts()}
        )
        for doc in documents:
            stats = category_stats[doc["category"]]
            stats["document_count"] += 1
            stats["status_counts"][doc["status"]] += 1

        # 트리에 통계 추가 (재귀)
        def add_stats(nodes: List[Dict]) -> None:
            for node in nodes:
                stats = category_stats[node["name"]]
                node["document_count"] = stats["document_count"]
                node["status_counts"] = stats["status_counts"]
                if node["children"]:
                    add_stats(node["children"])

        add_stats(tree)

        logger.info(f"사용자 카테고리 트리 조회 완료: user_id={user_id}")

        return tree

    except Exception as e:
        logger.error(f"카테고리 트리 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리 트리 조회 중 오류가 발생했습니다.",
        )


async def get_combined_categories(
    user_id: int,
    group_id: int,
    role_ids: List[int],
) -> Dict[str, Any]:
    """
    시스템 카테고리와 사용자 카테고리를 통합하여 조회합니다.

    Args:
        user_id: 사용자 ID
        group_id: 그룹 ID
        role_ids: 역할 ID 목록

    Returns:
        Dict[str, Any]: 통합된 카테고리 정보

    Raises:
        HTTPException: 조회 중 오류 발생 시
    """
    try:
        # 병렬 조회 (시스템 카테고리 + 사용자 카테고리 + 문서)
        system_categories, user_categories, documents = await asyncio.gather(
            get_system_templates(),
            user_category_crud.select_categories_by_user(
                user_id=user_id,
                include_all=True,
            ),
            select_documents(
                group_id=group_id,
                user_id=user_id,
                role_ids=role_ids,
                db_type="meta",
                use_iterator=True,  # 전체 문서 조회 (query_iterator로 64MB/16384 한도 우회)
            ),
        )

        # 카테고리별 통계 + 문서 그룹핑 (단일 루프)
        category_stats = defaultdict(
            lambda: {
                "total_size": 0,
                "document_count": 0,
                "status_counts": _get_default_status_counts(),
                "documents": [],
            }
        )
        for doc in documents:
            stats = category_stats[doc["category"]]
            stats["total_size"] += doc["file_size"]
            stats["document_count"] += 1
            stats["status_counts"][doc["status"]] += 1
            stats["documents"].append(doc)

        # 시스템 카테고리에 통계 + 최근 문서 추가
        for cat in system_categories:
            stats = category_stats[cat["name"]]
            cat["total_size"] = stats["total_size"]
            cat["document_count"] = stats["document_count"]
            cat["status_counts"] = stats["status_counts"]
            cat["recent_documents"] = _extract_recent_documents(stats["documents"])

        # 사용자 카테고리에 통계 + 최근 문서 추가
        for cat in user_categories:
            stats = category_stats[cat["name"]]
            cat["total_size"] = stats["total_size"]
            cat["document_count"] = stats["document_count"]
            cat["status_counts"] = stats["status_counts"]
            cat["recent_documents"] = _extract_recent_documents(stats["documents"])

        # 전체 문서 통합 요약
        all_documents = _build_all_documents_summary(documents)

        logger.info(
            f"통합 카테고리 조회 완료: 시스템={len(system_categories)}, 사용자={len(user_categories)}, 전체 문서={all_documents['document_count']}"
        )

        return {
            "all_documents": all_documents,
            "system_categories": system_categories,
            "user_categories": user_categories,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"통합 카테고리 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리 조회 중 오류가 발생했습니다.",
        )


async def get_category_by_id(
    category_id: int,
    user_id: int,
) -> Optional[Dict[str, Any]]:
    """
    ID로 카테고리를 조회합니다.

    Args:
        category_id: 카테고리 ID
        user_id: 사용자 ID

    Returns:
        Optional[Dict[str, Any]]: 카테고리 정보

    Raises:
        HTTPException: 조회 중 오류 발생 시
    """
    try:
        category = await user_category_crud.select_category_by_id(
            category_id=category_id,
            user_id=user_id,
        )

        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"카테고리를 찾을 수 없습니다: id={category_id}",
            )

        return category

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"카테고리 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="카테고리 조회 중 오류가 발생했습니다.",
        )
