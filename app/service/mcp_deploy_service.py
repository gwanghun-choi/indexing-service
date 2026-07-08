"""
MCP 배포 서비스

Retrieval MCP 개인 인스턴스 배포를 위한 비즈니스 로직을 처리합니다.
"""

import logging
from typing import Optional

from app.dto.mcp_deploy_dto import (
    RetrievalDeployRequestDTO,
    RetrievalDeployResponseDTO,
)
from app.utils.mcp_tools_client import McpToolsClient

logger = logging.getLogger(__name__)


class McpDeployService:
    """MCP 배포 서비스"""

    def __init__(self, passport_header: Optional[str] = None):
        """
        서비스 초기화

        Args:
            passport_header: x-user-passport 헤더 값
        """
        self.client = McpToolsClient(passport_header=passport_header)

    async def deploy_retrieval(
        self,
        request: RetrievalDeployRequestDTO,
    ) -> RetrievalDeployResponseDTO:
        """
        Retrieval MCP 배포

        Args:
            request: 배포 요청 DTO

        Returns:
            배포 결과 DTO
        """
        try:
            # 1. tool_id 조회
            tool_id = await self.client.get_tool_id_by_name(
                McpToolsClient.RETRIEVAL_TOOL_NAME
            )
            if not tool_id:
                return RetrievalDeployResponseDTO(
                    success=False,
                    message="tool_id 조회 실패. RETRIEVAL_MCP_TOOL_ID 환경 변수를 확인하세요.",
                    config_id=None,
                    tool_id=None,
                )

            # 2. secrets 딕셔너리 변환
            secrets_dict = request.secrets.model_dump(exclude_none=True)

            # 3. config_id 분기 처리
            if request.config_id:
                # 업데이트
                result = await self.client.update_user_config(
                    tool_id=tool_id,
                    config_id=request.config_id,
                    secrets=secrets_dict,
                    config_name=request.config_name,
                )
                message = "MCP 개인 인스턴스 업데이트 완료"
                config_id = request.config_id
            else:
                # 신규 생성
                result = await self.client.create_user_config(
                    tool_id=tool_id,
                    config_name=request.config_name,
                    secrets=secrets_dict,
                )
                message = "MCP 개인 인스턴스 생성 완료"
                # 응답에서 config_id 추출
                config_id = result.get("id") or result.get("config_id")

            logger.info(f"✅ {message}: tool_id={tool_id}, config_id={config_id}")

            return RetrievalDeployResponseDTO(
                success=True,
                message=message,
                config_id=config_id,
                tool_id=tool_id,
            )

        except Exception as e:
            error_msg = f"MCP 배포 실패: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return RetrievalDeployResponseDTO(
                success=False,
                message=error_msg,
                config_id=request.config_id,
                tool_id=None,
            )

