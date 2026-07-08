"""
MCP API 엔드포인트

Retrieval MCP 개인 인스턴스 배포 API를 제공합니다.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.dto.mcp_deploy_dto import (
    RetrievalDeployRequestDTO,
    RetrievalDeployResponseDTO,
)
from app.service.mcp_deploy_service import McpDeployService

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        400: {"description": "잘못된 요청 - 요청 매개변수가 유효하지 않습니다."},
        401: {"description": "인증 실패 - 유효한 인증 정보가 필요합니다."},
        403: {"description": "권한 부족 - 요청된 작업에 대한 권한이 없습니다."},
        500: {"description": "서버 오류 - 서버 내부 오류가 발생했습니다."},
    },
)


@router.post(
    "/deploy-retrieval",
    summary="Retrieval MCP 개인 인스턴스 배포",
    response_model=RetrievalDeployResponseDTO,
    description="""
🚀 **Retrieval MCP 개인 인스턴스 배포**

유사도 검색 옵션을 설정하여 Retrieval MCP를 개인 인스턴스로 배포합니다.

## 시나리오
1. **신규 배포** (config_id 없음): 새로운 개인 인스턴스 생성
2. **옵션 업데이트** (config_id 있음): 기존 인스턴스의 검색 옵션 변경

## 유사도 검색 옵션 (secrets)
- `limit`: 반환 결과 수 (1~100)
- `threshold`: 유사도 threshold (0.0~1.0)
- `search_mode`: 검색 모드 (hybrid | dense)
- `dense_weight`: Dense 가중치 (0.0~1.0)
- `sparse_weight`: Sparse 가중치 (0.0~1.0)
- `use_multi_query`: MultiQuery 사용 여부
- `reranker`: Reranker 선택 (null | cohere | flashrank)
- `graph_search_enabled`: Graph RAG 활성화
    """,
)
async def deploy_retrieval(
    request: Request,
    body: RetrievalDeployRequestDTO,
) -> RetrievalDeployResponseDTO:
    """
    Retrieval MCP 개인 인스턴스 배포

    Args:
        request: FastAPI Request 객체
        body: 배포 요청 DTO

    Returns:
        배포 결과 DTO
    """
    try:
        # 1. x-user-passport 헤더 추출
        passport_header = request.headers.get("x-user-passport")

        # 2. 서비스 호출
        service = McpDeployService(passport_header=passport_header)
        result = await service.deploy_retrieval(body)

        # 3. 결과 반환
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Retrieval MCP 배포 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

