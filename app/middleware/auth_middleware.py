from typing import Optional, Any
import logging

from fastapi import HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.auth_utils import get_optional_user as auth_get_optional_user, TEST_PASSPORT_DATA
from app.utils.passport_utils.parser import (
    parse_passport_from_headers,
    parse_passport_from_dict,
    is_admin_role,
    has_permission,
)
from app.service.permission_service import PermissionService
from app.config.settings import settings

# 디버깅을 위한 print와 로깅 설정
logger = logging.getLogger(__name__)


class CustomOAuth2Bearer(OAuth2PasswordBearer):
    """커스텀 OAuth2 Bearer 토큰 처리 클래스"""

    async def __call__(self, request: Request) -> Optional[str]:
        """
        공개 접근이 허용된 경로는 인증 검사를 건너뜀
        """
        logger.debug(f"🔍 CustomOAuth2Bearer called for path: {request.url.path}")

        if request.url.path in ["/docs", "/openapi.json", "/health"]:
            logger.debug(f"✅ Public path detected, skipping auth: {request.url.path}")
            return None
        return await super().__call__(request)


async def get_optional_user(auth_header: str | None) -> dict | None:
    """Authorization 헤더를 검사하여 선택적으로 사용자 정보를 반환"""
    logger.debug("🔍 get_optional_user called")

    try:
        user = await auth_get_optional_user(auth_header)
        if user:
            logger.debug("✅ JWT 검증 성공")
            logger.info(f"✅ User authorized: {user.get('user_id')}")
        else:
            logger.debug("⚠️ JWT 검증 실패 또는 토큰 없음")

        return user
    except Exception as e:
        logger.debug("❌ Token processing failed")
        logger.warning(f"❌ Token verification failed: {str(e)}")
        return None


# OAuth2 스키마 설정
oauth2_scheme = CustomOAuth2Bearer(tokenUrl="/auth/token", description="JWT 인증 토큰")


class AuthMiddleware(BaseHTTPMiddleware):
    """인증/인가 미들웨어 - Models 레포지토리의 방식을 참고하여 구현"""

    EXCLUDED_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/v1/sse/",  # SSE 엔드포인트 인증 제외
    ]

    def __init__(self, app: Any, permission_service: PermissionService = None):
        super().__init__(app)
        self.app_instance = app  # FastAPI app 인스턴스 저장
        self.permission_service = permission_service
        logger.info("🚀 AuthMiddleware initialized")

    async def dispatch(self, request: Request, call_next):
        # 제외 경로 체크
        if request.url.path in self.EXCLUDED_PATHS or any(
            request.url.path.startswith(path) for path in self.EXCLUDED_PATHS
        ):
            return await call_next(request)

        # 🔥 로컬 테스트 모드: 인증 우회 (테스트 전용 계정)
        if settings.SKIP_AUTH:
            logger.warning("⚠️ SKIP_AUTH 모드 - 테스트 계정으로 우회 중")
            request.state.passport_data = parse_passport_from_dict(TEST_PASSPORT_DATA)
            return await call_next(request)

        # 📖 Swagger UI(/docs)에서 보낸 요청 인증 우회 (원격 테스트용)
        if self._is_swagger_request(request):
            logger.warning("📖 Swagger UI 요청 - 테스트 계정으로 우회 중")
            request.state.passport_data = parse_passport_from_dict(TEST_PASSPORT_DATA)
            return await call_next(request)

        try:
            path = request.url.path
            logger.info(f"🔍 인증 체크 시작: {request.method} {path}")

            # Passport 헤더 파싱 (무조건 있다고 가정)
            passport_data = parse_passport_from_headers(request.headers)
            request.state.passport_data = passport_data

            # Admin 권한 확인
            if is_admin_role(passport_data):
                logger.info(f"✅ 관리자 권한 확인됨: {path}")
                return await call_next(request)

            # 일반 사용자 권한 검증
            await self.verify_permissions(request)
            logger.info(f"✅ 권한 검증 통과: {path}")

            return await call_next(request)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 인증 오류: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication error: {str(e)}",
            )

    async def verify_permissions(self, request: Request):
        """권한 검증 - passport_utils.has_permission 사용"""
        try:
            passport_data = request.state.passport_data
            method = request.method
            path = request.url.path

            # Permission service가 없으면 통과
            if not self.permission_service:
                return

            # DB에서 권한 정보 조회
            permission_data = await self.permission_service.get_path_permissions(
                path, method
            )
            if not permission_data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No permissions configured for {path}",
                )

            # 권한 검증
            resource_type = permission_data["resource_type"]
            action_type = permission_data["action_type"]

            if not has_permission(passport_data, action_type, resource_type):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions for {method} {path}",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 권한 검증 실패: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission verification failed",
            )

    def _is_swagger_request(self, request: Request) -> bool:
        """Swagger UI(/docs)에서 보낸 요청인지 확인"""

        # Referer 헤더에서 /docs 포함 여부만 확인
        referer = request.headers.get("referer", "")
        is_from_docs = "/docs" in referer

        if is_from_docs:
            logger.debug(f"📖 Swagger UI 요청 감지 - Referer: {referer}")
        else:
            logger.debug(f"🌐 일반 클라이언트 요청 - Referer: {referer}")

        return is_from_docs

    async def is_public_path(self, path: str) -> bool:
        """공개 접근 가능한 경로인지 확인"""
        public_paths = [
            "/api/v1/docs",
            "/api/v1/health",
        ]

        is_public = any(path.startswith(p) for p in public_paths)
        logger.debug(f"🔍 Path '{path}' is_public: {is_public}")
        return is_public
