"""
권한 서비스

API 엔드포인트에 대한 권한 검증 및 관리를 담당합니다.
Models 레포지토리의 permission_service.py를 참고하여 구현되었습니다.
"""

import json
import logging
import re
from typing import Dict, Any, Optional

from fastapi import HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.database.session import async_session_factory
from app.entity.postgres.api_permission_entity import ApiPermission

logger = logging.getLogger(__name__)


class PermissionService:
    """권한 서비스 클래스"""

    def __init__(self, redis_cache=None, db: Optional[AsyncSession] = None):
        """
        권한 서비스 초기화

        Args:
            redis_cache: Redis 캐시 인스턴스 (선택적)
            db: 데이터베이스 세션 (선택적, 런타임에 설정 가능)
        """
        self.db = db
        self.redis_cache = redis_cache
        self.cache_key_prefix = "endpoint_permissions:"
        self.cache_ttl = 3600
        self._path_pattern_cache = {}

        logger.info("✅ PermissionService initialized successfully")

    def _compile_path_pattern(self, pattern: str) -> re.Pattern:
        """경로 패턴을 정규식으로 컴파일"""
        if pattern in self._path_pattern_cache:
            return self._path_pattern_cache[pattern]

        # {변수명} 형태를 정규식 패턴으로 변환
        regex_pattern = re.sub(r"\{([^}]+)\}", r"(?P<\1>[^/]+)", pattern)
        compiled = re.compile(f"^{regex_pattern}$")
        self._path_pattern_cache[pattern] = compiled
        return compiled

    def _match_path_pattern(self, request_path: str, db_path_pattern: str) -> bool:
        """정규식 기반 경로 패턴 매칭"""
        # 쿼리 파라미터 제거
        if "?" in request_path:
            request_path = request_path.split("?")[0]

        # 정확한 일치 확인
        if request_path == db_path_pattern:
            return True

        # 정규식 패턴 컴파일 및 매칭
        pattern = self._compile_path_pattern(db_path_pattern)
        return bool(pattern.match(request_path))

    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """캐시에서 권한 정보 조회"""
        if not self.redis_cache or not self.redis_cache.redis:
            return None

        try:
            cached_data = await self.redis_cache.redis.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {cache_key}")
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get data from cache: {str(e)}")

        return None

    async def _set_to_cache(self, cache_key: str, data: Dict[str, Any]) -> None:
        """권한 정보를 캐시에 저장"""
        if not self.redis_cache or not self.redis_cache.redis:
            return

        try:
            await self.redis_cache.redis.set(
                cache_key, json.dumps(data), ex=self.cache_ttl
            )
            logger.debug(f"Cached data for {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to set data to cache: {str(e)}")

    async def get_path_permissions(
        self, path: str, method: str
    ) -> Optional[Dict[str, Any]]:
        """경로와 메서드에 따른 권한 정보 조회"""
        try:
            logger.debug(f"{path} 경로와 {method} 메소드에 대한 권한 확인")

            # 쿼리 파라미터 제거
            base_path = path.split("?")[0] if "?" in path else path
            cache_key = f"{self.cache_key_prefix}{base_path}:{method}"

            # 1. 캐시에서 먼저 조회
            cached_permission = await self._get_from_cache(cache_key)
            if cached_permission:
                return cached_permission

            # 2. 정확한 경로 매칭 시도
            permission = await self._find_exact_path_permission(base_path, method)

            # 3. 패턴 매칭 시도
            if not permission:
                permission = await self._find_pattern_matching_permission(
                    base_path, method
                )

            # 4. 권한 정보 없음
            if not permission:
                logger.debug(
                    f"요청 경로와 메서드에 대한 권한 없음 : {base_path} {method}"
                )
                return None

            # 5. 권한 정보 변환 및 캐싱
            permission_dict = self._convert_permission_to_dict(permission)
            await self._set_to_cache(cache_key, permission_dict)

            return permission_dict

        except Exception as e:
            logger.error(f"Error in get_path_permissions: {str(e)}", exc_info=True)
            raise

    async def _find_exact_path_permission(
        self, path: str, method: str
    ) -> Optional[ApiPermission]:
        """정확한 경로 일치로 권한 정보 찾기"""
        async with async_session_factory() as session:
            result = await session.execute(
                select(ApiPermission).where(
                    ApiPermission.path == path, ApiPermission.http_method == method
                )
            )
            return result.scalar_one_or_none()

    async def _find_pattern_matching_permission(
        self, path: str, method: str
    ) -> Optional[ApiPermission]:
        """패턴 매칭으로 권한 정보 찾기"""
        logger.debug(f"요청된 {path} 풀 경로가 DB에 저장되어 있는지 찾기")

        async with async_session_factory() as session:
            # 모든 API 권한 가져오기
            all_permissions_result = await session.execute(
                select(ApiPermission).where(ApiPermission.http_method == method)
            )
            all_permissions = all_permissions_result.scalars().all()

        # 패턴 매칭 검사
        for perm in all_permissions:
            if self._match_path_pattern(path, perm.path):
                logger.debug(
                    f"요청 경로와 메서드에 대한 패턴 매칭 검사: {perm.path}, {path}"
                )
                return perm

        return None

    def _convert_permission_to_dict(self, permission: ApiPermission) -> Dict[str, Any]:
        """ApiPermission 객체를 딕셔너리로 변환"""
        return {
            "id": permission.id,
            "required_role": permission.required_role,
            "resource_type": permission.resource_type,
            "action_type": permission.action_type,
        }


class AuthMiddleware(BaseHTTPMiddleware):
    """인증/인가 미들웨어"""

    def __init__(self, app, permission_service: PermissionService):
        super().__init__(app)
        self.permission_service = permission_service

    async def verify_permissions(self, request: Request):
        """권한 검증"""
        try:
            user = request.state.user
            method = request.method
            path = request.url.path

            logger.debug(f"Verifying permissions for user: {user}")

            permission_data = await self.permission_service.get_path_permissions(
                path, method
            )
            if not permission_data:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No permissions configured for path: {path} and method: {method}",
                )

            logger.debug(f"Permission data received: {permission_data}")

            # 역할 검증 - 사용자 역할과 필요 역할 비교
            required_role = permission_data.get("required_role")
            user_role = user.get("role")

            logger.debug(f"Required role: {required_role}, User role: {user_role}")

            # 역할이 필요하고 사용자 역할이 일치하지 않으면 거부
            if required_role and user_role != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role {required_role} required",
                )

            # 권한 목록 처리
            user_permissions = user.get("permissions", [])
            if isinstance(user_permissions, str):
                try:
                    user_permissions = json.loads(user_permissions)
                except json.JSONDecodeError:
                    user_permissions = [
                        {"resource_type": user_permissions, "action_type": "*"}
                    ]

            if not isinstance(user_permissions, list):
                user_permissions = [user_permissions]

            logger.debug(f"User permissions after processing: {user_permissions}")

            # 권한 검증 - 리소스 타입과 액션 타입 모두 검사
            has_permission = any(
                isinstance(perm, dict)
                and perm.get("resource_type") == permission_data["resource_type"]
                and perm.get("action_type") == permission_data["action_type"]
                for perm in user_permissions
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions for {method} {path}",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Permission verification error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error during permission verification",
            )
