"""
사용자 정의 카테고리 API

사용자별 커스텀 카테고리 관리를 위한 API 엔드포인트를 제공합니다.
"""

import logging
from typing import List

from fastapi import APIRouter, Path, Depends

from app.dto.category_dto import (
    UserCategoryCreateDTO,
    UserCategoryUpdateDTO,
    UserCategoryResponseDTO,
    UserCategoryTreeNodeDTO,
    SystemCategoryResponseDTO,
    CategoryDeleteResponseDTO,
)
from app.service import user_category_service
from app.utils.auth_utils import get_parsed_jwt_data

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        400: {"description": "bad request"},
        401: {"description": "unauthorized"},
        404: {"description": "not found"},
        500: {"description": "internal server error"},
    },
)


@router.get(
    "/templates",
    summary="시스템 템플릿 카테고리 조회",
    response_model=List[SystemCategoryResponseDTO],
    responses={
        200: {
            "description": "성공적으로 시스템 템플릿을 조회했습니다.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "name": "계약서",
                            "retention_period": 10,
                            "description": "각종 계약 관련 문서",
                        }
                    ]
                }
            },
        }
    },
    description="""
**시스템 기본 카테고리 템플릿 목록**

시스템에서 제공하는 기본 카테고리 템플릿 목록을 조회합니다.
사용자는 이 템플릿을 참고하여 자신만의 카테고리를 생성할 수 있습니다.

## 용도
- 사용자 카테고리 생성 시 참고용 템플릿
- 기본 보관 기간 확인
    """,
)
async def get_system_templates(
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> List[SystemCategoryResponseDTO]:
    """
    시스템 템플릿 카테고리 목록을 조회합니다.

    Args:
        jwt_data: JWT에서 파싱된 사용자 정보

    Returns:
        List[SystemCategoryResponseDTO]: 시스템 템플릿 목록
    """
    templates = await user_category_service.get_system_templates()
    return [SystemCategoryResponseDTO(**t) for t in templates]


@router.get(
    "/user",
    summary="내 카테고리 목록 조회",
    response_model=List[UserCategoryResponseDTO],
    responses={
        200: {
            "description": "성공적으로 카테고리 목록을 조회했습니다.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 103,
                            "user_id": 100,
                            "group_id": 1,
                            "name": "NDA",
                            "description": "비밀유지계약서",
                            "default_retention_period": 10,
                            "parent_id": 101,
                            "depth": 2,
                            "path": "101/103",
                            "created_at": "2026-01-13T09:00:00Z",
                            "updated_at": "2026-01-13T09:00:00Z",
                            "document_count": 5,
                        }
                    ]
                }
            },
        }
    },
    description="""
**내 카테고리 목록 조회**

로그인한 사용자가 생성한 커스텀 카테고리 목록을 조회합니다.
각 카테고리별 문서 수도 함께 제공됩니다.

## 특징
- 사용자별 독립적인 카테고리 체계
- 계층 구조 지원 (무제한 깊이)
- 각 카테고리별 문서 수 제공
    """,
)
async def get_user_categories(
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> List[UserCategoryResponseDTO]:
    """
    사용자의 카테고리 목록을 조회합니다.

    Args:
        jwt_data: JWT에서 파싱된 사용자 정보

    Returns:
        List[UserCategoryResponseDTO]: 사용자 카테고리 목록
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]
    role_ids = jwt_data["total_role"]

    categories = await user_category_service.get_user_categories(
        user_id=user_id,
        group_id=group_id,
        role_ids=role_ids,
    )

    return [UserCategoryResponseDTO(**c) for c in categories]


@router.post(
    "/user",
    summary="카테고리 생성",
    response_model=UserCategoryResponseDTO,
    status_code=201,
    responses={
        201: {
            "description": "성공적으로 카테고리를 생성했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 103,
                        "user_id": 100,
                        "group_id": 1,
                        "name": "NDA",
                        "description": "비밀유지계약서",
                        "default_retention_period": 10,
                        "parent_id": 101,
                        "depth": 2,
                        "path": "101/103",
                        "created_at": "2026-01-13T09:00:00Z",
                        "updated_at": "2026-01-13T09:00:00Z",
                        "document_count": 0,
                    }
                }
            },
        },
        400: {
            "description": "잘못된 요청 (중복 이름, 부모 카테고리 없음 등)",
        },
    },
    description="""
**새 카테고리 생성**

사용자 정의 카테고리를 생성합니다.

## 규칙
- 같은 부모 아래에 동일한 이름의 카테고리 생성 불가
- 부모 카테고리 지정 시, 본인 소유 카테고리여야 함
- 깊이 제한 없음 (파일탐색기 스타일)

## 필드
- **name**: 카테고리 이름 (필수, 최대 100자)
- **description**: 카테고리 설명 (선택)
- **default_retention_period**: 만료기간 추천값 (기본 3년)
- **parent_id**: 부모 카테고리 ID (NULL이면 루트)
    """,
)
async def create_user_category(
    data: UserCategoryCreateDTO,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> UserCategoryResponseDTO:
    """
    새 카테고리를 생성합니다.

    Args:
        data: 카테고리 생성 데이터
        jwt_data: JWT에서 파싱된 사용자 정보

    Returns:
        UserCategoryResponseDTO: 생성된 카테고리 정보
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    category = await user_category_service.create_user_category(
        user_id=user_id,
        group_id=group_id,
        data=data,
    )

    return UserCategoryResponseDTO(**category)


@router.put(
    "/user/{category_id}",
    summary="카테고리 수정",
    response_model=UserCategoryResponseDTO,
    responses={
        200: {
            "description": "성공적으로 카테고리를 수정했습니다.",
        },
        400: {
            "description": "잘못된 요청 (중복 이름 등)",
        },
        404: {
            "description": "카테고리를 찾을 수 없음",
        },
    },
    description="""
**카테고리 수정**

기존 카테고리의 정보를 수정합니다.

## 수정 가능한 필드
- **name**: 카테고리 이름
- **description**: 카테고리 설명
- **default_retention_period**: 만료기간 추천값

## 제한사항
- 본인 소유 카테고리만 수정 가능
- 같은 부모 아래 동일 이름으로 변경 불가
    """,
)
async def update_user_category(
    category_id: int = Path(..., description="수정할 카테고리 ID"),
    data: UserCategoryUpdateDTO = ...,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> UserCategoryResponseDTO:
    """
    카테고리를 수정합니다.

    Args:
        category_id: 수정할 카테고리 ID
        data: 카테고리 수정 데이터
        jwt_data: JWT에서 파싱된 사용자 정보

    Returns:
        UserCategoryResponseDTO: 수정된 카테고리 정보
    """
    user_id = jwt_data["user_id"]

    category = await user_category_service.update_user_category(
        category_id=category_id,
        user_id=user_id,
        data=data,
    )

    return UserCategoryResponseDTO(**category)


@router.delete(
    "/user/{category_id}",
    summary="카테고리 삭제",
    response_model=CategoryDeleteResponseDTO,
    responses={
        200: {
            "description": "성공적으로 카테고리를 삭제했습니다.",
        },
        400: {
            "description": "삭제 불가 (하위 카테고리 또는 문서 존재)",
        },
        404: {
            "description": "카테고리를 찾을 수 없음",
        },
    },
    description="""
**카테고리 삭제**

빈 카테고리를 삭제합니다.

## 삭제 조건
| 조건 | 결과 |
|------|------|
| 타 사용자 카테고리 | 권한 없음 |
| 하위 카테고리 존재 | 하위 먼저 삭제 필요 |
| 문서 존재 | 문서 먼저 이동/삭제 필요 |
| 빈 카테고리 | 삭제 가능 |
    """,
)
async def delete_user_category(
    category_id: int = Path(..., description="삭제할 카테고리 ID"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> CategoryDeleteResponseDTO:
    """
    카테고리를 삭제합니다.

    Args:
        category_id: 삭제할 카테고리 ID
        jwt_data: JWT에서 파싱된 사용자 정보

    Returns:
        CategoryDeleteResponseDTO: 삭제 결과
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]
    role_ids = jwt_data["total_role"]

    await user_category_service.delete_user_category(
        category_id=category_id,
        user_id=user_id,
        group_id=group_id,
        role_ids=role_ids,
    )

    return CategoryDeleteResponseDTO(
        message="카테고리가 성공적으로 삭제되었습니다.",
        deleted_id=category_id,
    )


@router.get(
    "/user/tree",
    summary="카테고리 트리 조회",
    response_model=List[UserCategoryTreeNodeDTO],
    responses={
        200: {
            "description": "성공적으로 카테고리 트리를 조회했습니다.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 101,
                            "name": "계약서",
                            "description": "각종 계약 관련 문서",
                            "depth": 1,
                            "default_retention_period": 10,
                            "document_count": 10,
                            "children": [
                                {
                                    "id": 102,
                                    "name": "NDA",
                                    "description": "비밀유지계약서",
                                    "depth": 2,
                                    "default_retention_period": 10,
                                    "document_count": 3,
                                    "children": [],
                                }
                            ],
                        }
                    ]
                }
            },
        }
    },
    description="""
**카테고리 트리 구조 조회**

사용자의 카테고리를 계층적 트리 구조로 조회합니다.
UI에서 폴더 구조 표시용으로 사용됩니다.

## 응답 구조
- 루트 카테고리 목록을 반환
- 각 노드는 `children` 필드에 하위 카테고리 포함
- 무제한 깊이 지원
    """,
)
async def get_user_category_tree(
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> List[UserCategoryTreeNodeDTO]:
    """
    카테고리를 트리 구조로 조회합니다.

    Args:
        jwt_data: JWT에서 파싱된 사용자 정보

    Returns:
        List[UserCategoryTreeNodeDTO]: 트리 구조의 카테고리 목록
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]
    role_ids = jwt_data["total_role"]

    tree = await user_category_service.get_user_category_tree(
        user_id=user_id,
        group_id=group_id,
        role_ids=role_ids,
    )

    # 재귀적으로 DTO 변환
    def convert_to_dto(nodes: list) -> List[UserCategoryTreeNodeDTO]:
        result = []
        for node in nodes:
            children = convert_to_dto(node["children"])
            dto = UserCategoryTreeNodeDTO(
                id=node["id"],
                name=node["name"],
                description=node["description"],
                depth=node["depth"],
                default_retention_period=node["default_retention_period"],
                document_count=node["document_count"],
                children=children,
            )
            result.append(dto)
        return result

    return convert_to_dto(tree)


@router.get(
    "/user/{category_id}",
    summary="카테고리 상세 조회",
    response_model=UserCategoryResponseDTO,
    responses={
        200: {
            "description": "성공적으로 카테고리를 조회했습니다.",
        },
        404: {
            "description": "카테고리를 찾을 수 없음",
        },
    },
    description="""
**카테고리 상세 조회**

특정 카테고리의 상세 정보를 조회합니다.
    """,
)
async def get_user_category_by_id(
    category_id: int = Path(..., description="조회할 카테고리 ID"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> UserCategoryResponseDTO:
    """
    ID로 카테고리를 조회합니다.

    Args:
        category_id: 조회할 카테고리 ID
        jwt_data: JWT에서 파싱된 사용자 정보

    Returns:
        UserCategoryResponseDTO: 카테고리 정보
    """
    user_id = jwt_data["user_id"]

    category = await user_category_service.get_category_by_id(
        category_id=category_id,
        user_id=user_id,
    )

    return UserCategoryResponseDTO(**category)
