"""
MCP Tools API 클라이언트

외부 MCP Tools 서버와 통신하기 위한 비동기 HTTP 클라이언트입니다.
"""

import logging
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import text

from app.config.settings import settings
from app.config.database.session import get_async_db_context

logger = logging.getLogger(__name__)


class McpToolsClient:
    """MCP Tools API 클라이언트"""

    # retrieval mcp 도구 이름
    RETRIEVAL_TOOL_NAME = "retrieval-mcp-v2"

    def __init__(self, passport_header: Optional[str] = None):
        """
        MCP Tools 클라이언트 초기화

        Args:
            passport_header: x-user-passport 헤더 값
        """
        self.base_url = settings.MCP_TOOLS_BASE_URL
        self.passport_header = passport_header
        self.timeout = httpx.Timeout(30.0)

    def _get_headers(self) -> Dict[str, str]:
        """API 호출용 헤더 생성"""
        headers = {
            "Content-Type": "application/json",
        }
        if self.passport_header:
            headers["x-user-passport"] = self.passport_header
        return headers

    async def get_tool_id_by_name(self, tool_name: str) -> Optional[int]:
        """
        도구 이름으로 tool_id 조회 (DB에서 동적 조회)

        Args:
            tool_name: 도구 이름 (예: 'retrieval-mcp-v2')

        Returns:
            tool_id 또는 None (조회 실패시)
        """
        try:
            async with get_async_db_context() as session:
                # mcp_tools 스키마의 mcp_tool 테이블에서 조회
                query = text("SELECT id FROM mcp_tools.mcp_tool WHERE name = :name")
                result = await session.execute(query, {"name": tool_name})
                row = result.fetchone()

                if row:
                    tool_id = row[0]
                    logger.info(f"✅ tool_id 조회 성공: {tool_name} → {tool_id}")
                    return tool_id
                else:
                    logger.warning(
                        f"⚠️ tool_id 조회 실패: {tool_name} 도구를 찾을 수 없음"
                    )
                    return None

        except Exception as e:
            logger.error(f"❌ tool_id 조회 중 오류: {e}")
            return None

    async def create_user_config(
        self,
        tool_id: int,
        config_name: str,
        secrets: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        개인 인스턴스 생성 (POST)

        Args:
            tool_id: 도구 ID
            config_name: 설정 이름
            secrets: 유사도 검색 옵션

        Returns:
            API 응답 데이터
        """
        url = f"{self.base_url}/v1/mcp-tools/{tool_id}/user-configs"
        payload = {
            "config_name": config_name,
            "secrets": secrets,
        }

        logger.info(f"🚀 MCP 개인 인스턴스 생성 요청: tool_id={tool_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )

            if response.status_code in (200, 201, 202):
                result = response.json()
                logger.info(f"✅ MCP 개인 인스턴스 생성 성공: {result}")
                return result
            else:
                error_msg = (
                    f"MCP 인스턴스 생성 실패: "
                    f"{response.status_code} - {response.text}"
                )
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)

    async def update_user_config(
        self,
        tool_id: int,
        config_id: int,
        secrets: Dict[str, Any],
        config_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        개인 인스턴스 업데이트 (PUT)

        Args:
            tool_id: 도구 ID
            config_id: 설정 ID
            secrets: 유사도 검색 옵션
            config_name: 설정 이름 (선택)

        Returns:
            API 응답 데이터
        """
        url = f"{self.base_url}/v1/mcp-tools/{tool_id}/user-configs/{config_id}"
        payload: Dict[str, Any] = {
            "secrets": secrets,
        }
        if config_name:
            payload["config_name"] = config_name

        logger.info(
            f"🔄 MCP 개인 인스턴스 업데이트 요청: "
            f"tool_id={tool_id}, config_id={config_id}"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.put(
                url,
                json=payload,
                headers=self._get_headers(),
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ MCP 개인 인스턴스 업데이트 성공: {result}")
                return result
            else:
                error_msg = (
                    f"MCP 인스턴스 업데이트 실패: "
                    f"{response.status_code} - {response.text}"
                )
                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)
