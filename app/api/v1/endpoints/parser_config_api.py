"""
파서 설정 관리 API

외부 문서 파서 설정을 관리하는 관리자 전용 API 엔드포인트를 제공합니다.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.crud.postgres.parser_config_crud import (
    create_parser_config as create_parser_config_crud,
    delete_parser_config as delete_parser_config_crud,
    select_active_parser_configs,
    select_parser_config,
    update_parser_config as update_parser_config_crud,
)
from app.dto.parser_config_dto import (
    CreateParserConfigRequestDTO,
    MessageResponseDTO,
    ParserConfigListResponseDTO,
    ParserConfigResponseDTO,
    UpdateParserConfigRequestDTO,
)
from app.utils.auth_utils import get_parsed_jwt_data
from app.utils.passport_utils.parser import is_admin_role

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        400: {"description": "잘못된 요청 - 요청 매개변수가 유효하지 않습니다."},
        401: {"description": "인증 실패 - 유효한 인증 정보가 필요합니다."},
        403: {"description": "권한 부족 - 관리자 권한이 필요합니다."},
        404: {"description": "찾을 수 없음 - 요청된 파서 설정이 존재하지 않습니다."},
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
    "",
    summary="파서 설정 목록 조회 (관리자 전용)",
    response_model=ParserConfigListResponseDTO,
    responses={
        200: {
            "description": "파서 설정 목록이 성공적으로 반환되었습니다.",
        }
    },
    description="""
📋 **파서 설정 목록 조회 (관리자 전용)**

활성화된 외부 문서 파서 설정 목록을 조회합니다.

## 반환 정보
- 파서 식별자 (parser_name)
- 표시 이름 (display_name)
- API 엔드포인트
- 활성화 여부
- 타임아웃 설정
- 추가 설정
    """,
)
async def get_parser_configs(
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ParserConfigListResponseDTO:
    """
    파서 설정 목록 조회 (관리자 전용)

    Args:
        request: FastAPI Request 객체
        jwt_data: JWT 인증 정보

    Returns:
        Dict[str, Any]: 파서 설정 목록

    Raises:
        HTTPException: 관리자 권한이 없는 경우 403
    """
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"📋 파서 설정 목록 조회 요청: user_id={user_id}")

    configs = await select_active_parser_configs()

    items = [
        {
            "id": config.id,
            "parser_name": config.parser_name,
            "display_name": config.display_name,
            "api_endpoint": config.api_endpoint,
            "is_active": config.is_active,
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
            "extra_config": config.extra_config or {},
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        }
        for config in configs
    ]

    return {
        "items": items,
        "total": len(items),
    }


@router.get(
    "/{parser_name}",
    summary="파서 설정 상세 조회 (관리자 전용)",
    response_model=ParserConfigResponseDTO,
    responses={
        200: {
            "description": "파서 설정 정보가 성공적으로 반환되었습니다.",
        },
        404: {
            "description": "파서 설정을 찾을 수 없습니다.",
        },
    },
    description="""
🔍 **파서 설정 상세 조회 (관리자 전용)**

특정 파서의 상세 설정 정보를 조회합니다.
    """,
)
async def get_parser_config(
    parser_name: str,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ParserConfigResponseDTO:
    """
    파서 설정 상세 조회 (관리자 전용)

    Args:
        parser_name: 파서 식별자
        request: FastAPI Request 객체
        jwt_data: JWT 인증 정보

    Returns:
        ParserConfigResponseDTO: 파서 설정 정보

    Raises:
        HTTPException: 관리자 권한이 없는 경우 403
    """
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"🔍 파서 설정 상세 조회: {parser_name}, user_id={user_id}")

    config = await select_parser_config(parser_name)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"파서 설정을 찾을 수 없습니다: {parser_name}",
        )

    return {
        "id": config.id,
        "parser_name": config.parser_name,
        "display_name": config.display_name,
        "api_endpoint": config.api_endpoint,
        "is_active": config.is_active,
        "timeout_seconds": config.timeout_seconds,
        "max_retries": config.max_retries,
        "extra_config": config.extra_config or {},
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.post(
    "",
    summary="파서 설정 생성 (관리자 전용)",
    response_model=ParserConfigResponseDTO,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "파서 설정이 성공적으로 생성되었습니다.",
        },
        400: {
            "description": "잘못된 요청 - 이미 존재하는 파서명이거나 필수 필드가 누락되었습니다.",
        },
    },
    description="""
➕ **파서 설정 생성 (관리자 전용)**

새로운 외부 문서 파서 설정을 등록합니다.

## 필수 정보
- parser_name: 파서 식별자 (영문, 숫자, 언더스코어만 허용)
- display_name: 표시 이름
- api_endpoint: API 엔드포인트 URL
- api_key: API 인증 키

## 선택 정보
- is_active: 활성화 여부 (기본: true)
- timeout_seconds: 타임아웃 (기본: 300초)
- max_retries: 최대 재시도 횟수 (기본: 3)
- extra_config: 추가 설정 (JSON)
    """,
)
async def create_parser_config(
    request_body: CreateParserConfigRequestDTO,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ParserConfigResponseDTO:
    """
    파서 설정 생성 (관리자 전용)

    Args:
        request_body: 파서 설정 생성 요청
        request: FastAPI Request 객체
        jwt_data: JWT 인증 정보

    Returns:
        ParserConfigResponseDTO: 생성된 파서 설정 정보

    Raises:
        HTTPException: 관리자 권한이 없는 경우 403
    """
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"➕ 파서 설정 생성 요청: {request_body.parser_name}, user_id={user_id}")

    config_data = {
        "parser_name": request_body.parser_name,
        "display_name": request_body.display_name,
        "api_endpoint": request_body.api_endpoint,
        "api_key": request_body.api_key,
        "is_active": request_body.is_active,
        "timeout_seconds": request_body.timeout_seconds,
        "max_retries": request_body.max_retries,
        "extra_config": request_body.extra_config,
    }

    config = await create_parser_config_crud(config_data)

    logger.info(f"✅ 파서 설정 생성 완료: {config.parser_name}")

    return {
        "id": config.id,
        "parser_name": config.parser_name,
        "display_name": config.display_name,
        "api_endpoint": config.api_endpoint,
        "is_active": config.is_active,
        "timeout_seconds": config.timeout_seconds,
        "max_retries": config.max_retries,
        "extra_config": config.extra_config or {},
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.put(
    "/{parser_name}",
    summary="파서 설정 수정 (관리자 전용)",
    response_model=ParserConfigResponseDTO,
    responses={
        200: {
            "description": "파서 설정이 성공적으로 수정되었습니다.",
        },
        404: {
            "description": "파서 설정을 찾을 수 없습니다.",
        },
    },
    description="""
✏️ **파서 설정 수정 (관리자 전용)**

기존 파서 설정을 수정합니다. 수정할 필드만 요청에 포함합니다.

## 수정 가능 항목
- display_name: 표시 이름
- api_endpoint: API 엔드포인트 URL
- api_key: API 인증 키
- is_active: 활성화 여부
- timeout_seconds: 타임아웃
- max_retries: 최대 재시도 횟수
- extra_config: 추가 설정
    """,
)
async def update_parser_config(
    parser_name: str,
    request_body: UpdateParserConfigRequestDTO,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ParserConfigResponseDTO:
    """
    파서 설정 수정 (관리자 전용)

    Args:
        parser_name: 파서 식별자
        request_body: 수정 요청
        request: FastAPI Request 객체
        jwt_data: JWT 인증 정보

    Returns:
        ParserConfigResponseDTO: 수정된 파서 설정 정보

    Raises:
        HTTPException: 관리자 권한이 없는 경우 403
    """
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"✏️ 파서 설정 수정 요청: {parser_name}, user_id={user_id}")

    # None이 아닌 필드만 추출
    update_data = {
        k: v for k, v in request_body.model_dump().items() if v is not None
    }

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="수정할 필드가 없습니다.",
        )

    config = await update_parser_config_crud(parser_name, update_data)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"파서 설정을 찾을 수 없습니다: {parser_name}",
        )

    logger.info(f"✅ 파서 설정 수정 완료: {parser_name}")

    return {
        "id": config.id,
        "parser_name": config.parser_name,
        "display_name": config.display_name,
        "api_endpoint": config.api_endpoint,
        "is_active": config.is_active,
        "timeout_seconds": config.timeout_seconds,
        "max_retries": config.max_retries,
        "extra_config": config.extra_config or {},
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.delete(
    "/{parser_name}",
    summary="파서 설정 삭제 (관리자 전용)",
    response_model=MessageResponseDTO,
    responses={
        200: {
            "description": "파서 설정이 성공적으로 삭제되었습니다.",
        },
        404: {
            "description": "파서 설정을 찾을 수 없습니다.",
        },
    },
    description="""
🗑️ **파서 설정 삭제 (관리자 전용)**

파서 설정을 삭제합니다.

## 주의사항
- 삭제 후 복구할 수 없습니다.
- 해당 파서를 사용 중인 문서가 있는 경우 처리에 영향을 줄 수 있습니다.
    """,
)
async def delete_parser_config(
    parser_name: str,
    request: Request,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> MessageResponseDTO:
    """
    파서 설정 삭제 (관리자 전용)

    Args:
        parser_name: 파서 식별자
        request: FastAPI Request 객체
        jwt_data: JWT 인증 정보

    Returns:
        MessageResponseDTO: 삭제 결과 메시지

    Raises:
        HTTPException: 관리자 권한이 없는 경우 403
    """
    user_id = jwt_data["user_id"]
    verify_admin_role(request, user_id)

    logger.info(f"🗑️ 파서 설정 삭제 요청: {parser_name}, user_id={user_id}")

    result = await delete_parser_config_crud(parser_name)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"파서 설정을 찾을 수 없습니다: {parser_name}",
        )

    logger.info(f"✅ 파서 설정 삭제 완료: {parser_name}")

    return {
        "message": f"파서 설정이 성공적으로 삭제되었습니다: {parser_name}",
    }
