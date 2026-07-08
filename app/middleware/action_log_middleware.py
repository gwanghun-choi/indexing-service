"""
Action Log Middleware

모든 API 요청에 대한 로깅을 수행하는 미들웨어입니다.
JWT에서 사용자 정보를 추출하여 요청, 응답, 에러 정보를 데이터베이스에 기록합니다.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config.database.session import get_async_db_context
from app.entity.postgres.action_log_entity import UserActionLog

# TODO: user_service.py 제거됨 - JWT 기반으로 사용자 정보 추출 필요

logger = logging.getLogger("app.middleware.action_log")


class ActionLogMiddleware(BaseHTTPMiddleware):
    """
    사용자 액션 로그 수집 미들웨어

    모든 API 요청과 응답을 추적하여 UserActionLog 테이블에 저장합니다.
    사용자 인증 정보, 요청 세부사항, 응답 결과, 성능 메트릭 등을 포함합니다.
    """

    # 로그 수집에서 제외할 경로들
    EXCLUDED_PATHS = {
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/favicon.ico",
        "/static",
        "/v1/action-logs",
    }

    # 민감한 필드들 (로그에서 필터링)
    SENSITIVE_FIELDS = {
        "password",
        "token",
        "secret",
        "api_key",
        "authorization",
        "refresh_token",
        "access_token",
        "private_key",
        "credential",
    }

    # HTTP 메서드별 액션 타입 매핑
    ACTION_TYPE_MAPPING = {
        "GET": "READ",
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
        "WEBSOCKET": "WEBSOCKET",
    }

    def __init__(self, app):
        super().__init__(app)

    def _should_log_request(self, path: str) -> bool:
        """요청을 로그해야 하는지 판단"""
        return not any(excluded in path for excluded in self.EXCLUDED_PATHS)

    def _extract_path_info(self, path: str) -> Dict[str, Any]:
        """URL 경로에서 path parameters와 user_id, item_id를 함께 추출"""
        result = {
            "path_params": {},  # 로깅용 모든 매개변수 (정수)
            "user_id": None,  # 비즈니스 로직용 user_id (정수)
            "item_id": None,  # 비즈니스 로직용 item_id (정수)
        }

        try:
            path_parts = path.strip("/").split("/")

            # /documents/{user_id} 패턴
            if "documents" in path_parts:
                doc_index = path_parts.index("documents")
                if doc_index + 1 < len(path_parts):
                    user_id_str = path_parts[doc_index + 1]
                    try:
                        user_id_int = int(user_id_str)
                        result["path_params"]["user_id"] = user_id_int
                        result["user_id"] = user_id_int
                    except ValueError:
                        pass

            # /documents/items/{user_id}/{id} 패턴
            if "items" in path_parts:
                items_index = path_parts.index("items")
                if items_index + 2 < len(path_parts):
                    user_id_str = path_parts[items_index + 1]
                    item_id_str = path_parts[items_index + 2]
                    try:
                        user_id_int = int(user_id_str)
                        item_id_int = int(item_id_str)
                        result["path_params"]["user_id"] = user_id_int
                        result["path_params"]["id"] = item_id_int
                        result["user_id"] = user_id_int
                        result["item_id"] = item_id_int
                    except ValueError:
                        pass

            # /notifications/{user_id} 패턴
            if "notifications" in path_parts:
                notif_index = path_parts.index("notifications")
                if notif_index + 1 < len(path_parts):
                    user_id_str = path_parts[notif_index + 1]
                    try:
                        user_id_int = int(user_id_str)
                        result["path_params"]["user_id"] = user_id_int
                        result["user_id"] = user_id_int
                    except ValueError:
                        pass

            logger.debug(f"✅ Path 정보 추출됨: {result} from {path}")

        except Exception as e:
            logger.debug(f"⚠️ Path 정보 추출 실패: {e}")

        return result

    def _sanitize_data(self, data: Any) -> Any:
        """민감한 데이터를 필터링"""
        if isinstance(data, dict):
            return {
                k: (
                    "[FILTERED]"
                    if k.lower() in self.SENSITIVE_FIELDS
                    else self._sanitize_data(v)
                )
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._sanitize_data(item) for item in data]
        else:
            return data

    async def _extract_user_id_from_form_data(self, request: Request) -> Optional[int]:
        """Form data에서 user_id만 안전하게 추출 - 사용하지 않음 (request body 소모 방지)"""
        # 이 메서드는 request body를 소모하므로 사용하지 않음
        return None

    async def _extract_user_info(
        self,
        request: Request,
        request_body: Dict = None,
        path_info: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """요청에서 사용자 정보 추출"""
        user_info = {"user_id": None, "group_id": None, "role_id": None}
        user_id = None

        try:
            # 먼저 JWT에서 사용자 정보 추출 시도
            jwt_info = await get_user_info_from_jwt(request)
            if jwt_info and jwt_info.get("user_id"):
                user_info.update(jwt_info)
                logger.debug(f"JWT에서 사용자 정보 추출 성공: {user_info}")
                return user_info

            # JWT에서 정보를 가져오지 못한 경우 다른 소스에서 추출
            # 1. Path parameter에서 user_id 추출 (통합 함수 사용)
            if path_info:
                user_id = path_info["user_id"]
            else:
                # fallback: path_info가 없는 경우 직접 추출
                path_info = self._extract_path_info(request.url.path)
                user_id = path_info["user_id"]

            # 2. Request body에서 user_id 추출 (JSON 요청만)
            if not user_id and request_body:
                try:
                    user_id = request_body.get("user_id")
                    if user_id:
                        user_id = int(user_id)
                except (ValueError, TypeError):
                    user_id = None

            # 3. Query parameter에서 user_id 추출
            if not user_id:
                try:
                    query_user_id = request.query_params.get("user_id")
                    if query_user_id:
                        user_id = int(query_user_id)
                except (ValueError, TypeError):
                    user_id = None

            # 4. Form data 요청의 경우 일단 건너뛰고 나중에 처리
            if not user_id and request.headers.get("content-type", "").startswith(
                "multipart/form-data"
            ):
                logger.debug(
                    "⚠️ Form data 요청 - user_id는 응답 후 form_data_for_logging에서 추출 예정"
                )

            # user_id가 있으면 사용자 정보 설정
            if user_id:
                user_info["user_id"] = user_id
                # JWT에서 group_id, role_id 정보 다시 확인
                if hasattr(request.state, "user") and request.state.user:
                    jwt_data = request.state.user
                    if jwt_data.get("group_id"):
                        user_info["group_id"] = jwt_data.get("group_id")
                    if jwt_data.get("role_id"):
                        user_info["role_id"] = jwt_data.get("role_id")
                logger.debug(f"사용자 정보 설정 완료: {user_info}")

        except Exception as e:
            logger.error(f"사용자 정보 추출 중 예상치 못한 오류: {e}")
            # 전체 과정에서 오류가 발생해도 빈 user_info 반환하여 계속 진행

        return user_info

    def _extract_document_info(
        self, request: Request, request_body: Dict, path_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """요청에서 문서 관련 정보 추출"""
        document_info = {
            "document_id": None,
            "document_title": None,
            "document_category": None,
            "file_name": None,
            "file_type": None,
            "file_size": None,
        }

        # path_info에서 item_id 추출 (문서 ID로 사용) - 문자열로 변환
        if path_info and path_info.get("item_id"):
            document_info["document_id"] = str(path_info["item_id"])  # 문자열로 변환
        else:
            # 기존 방식으로 fallback
            path_parts = request.url.path.split("/")
            if "documents" in path_parts:
                try:
                    doc_index = path_parts.index("documents")
                    if doc_index + 1 < len(path_parts):
                        doc_id_str = path_parts[doc_index + 1]
                        document_info["document_id"] = doc_id_str  # 문자열 그대로 저장
                except (ValueError, IndexError):
                    pass

        # 요청 본문에서 문서 정보 추출
        if request_body:
            document_info.update(
                {
                    "document_title": request_body.get("title"),
                    "document_category": request_body.get("category"),
                    "file_name": request_body.get("file_name"),
                    "file_type": request_body.get("file_type"),
                    "file_size": request_body.get("file_size"),
                }
            )

        return document_info

    def _extract_search_info(
        self, request: Request, request_body: Dict
    ) -> Dict[str, Any]:
        """검색 관련 정보 추출"""
        search_info = {
            "search_query": None,
            "search_results_count": None,
            "use_reranker": None,
        }

        # 검색 엔드포인트인지 확인
        if (
            "search" in request.url.path.lower()
            or "retrieval" in request.url.path.lower()
        ):
            if request_body:
                search_info.update(
                    {
                        "search_query": request_body.get("query"),
                        "use_reranker": request_body.get("use_reranker", False),
                    }
                )

            # 쿼리 파라미터에서도 검색어 추출
            query_params = dict(request.query_params)
            if "q" in query_params or "query" in query_params:
                search_info["search_query"] = query_params.get("q") or query_params.get(
                    "query"
                )

        return search_info

    async def _get_request_body(self, request: Request) -> Optional[Dict]:
        """요청 본문 추출"""
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                # JSON 요청 처리
                if request.headers.get("content-type", "").startswith(
                    "application/json"
                ):
                    body = await request.json()
                    return self._sanitize_data(body)
                # Form data 요청은 미들웨어에서 읽지 않음 (request body 소모 방지)
                elif request.headers.get("content-type", "").startswith(
                    "multipart/form-data"
                ):
                    # Form data는 엔드포인트에서 읽도록 하고, 미들웨어에서는 건너뜀
                    logger.debug("✅ Form data 요청 감지 - request body 읽기 건너뜀")
                    return None
            except Exception as e:
                logger.debug(f"⚠️ 요청 본문 파싱 실패: {e}")
                return None
        return None

    def _extract_cost_info(
        self, request_body: Dict, response_body: Dict = None
    ) -> Dict[str, Any]:
        """비용 및 토큰 사용량 정보 추출"""
        cost_info = {"tokens_used": None, "cost_incurred": None}

        # 응답에서 비용 정보 추출
        if response_body:
            cost_info.update(
                {
                    "tokens_used": response_body.get("tokens_used"),
                    "cost_incurred": response_body.get("cost_incurred"),
                }
            )

        return cost_info

    def _determine_action_type(self, method: str, path: str) -> str:
        """HTTP 메서드와 경로를 기반으로 액션 타입 결정"""
        # 특별한 경우들 처리
        if "search" in path.lower() or "retrieval" in path.lower():
            return "SEARCH"
        elif "upload" in path.lower():
            return "UPLOAD"
        elif "download" in path.lower():
            return "DOWNLOAD"
        elif "websocket" in path.lower() or path.startswith("/notifications/"):
            return "WEBSOCKET"
        else:
            return self.ACTION_TYPE_MAPPING.get(method, "UNKNOWN")

    async def _save_action_log(self, log_data: Dict[str, Any]):
        """액션 로그를 데이터베이스에 저장 (DB 연결 실패 시 graceful degradation)"""
        try:
            async with get_async_db_context() as db:
                action_log = UserActionLog(**log_data)
                db.add(action_log)
                await db.commit()
                logger.debug(f"✅ 액션 로그 저장 완료: {log_data.get('request_id')}")

        except Exception as e:
            # DB 연결 실패 등의 오류를 상세히 로깅하되, 원본 요청에는 영향 없음
            logger.error(
                f"❌ 액션 로그 저장 실패 (request_id: {log_data.get('request_id', 'unknown')}): {str(e)}"
            )

            # 개발 환경에서는 더 상세한 정보 로깅
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"✅ 로그 데이터: {log_data}")

            # 로그 저장 실패가 원본 요청에 영향을 주지 않도록 예외를 삼킴
            # 이는 의도적인 설계로, 로깅 시스템 장애가 서비스 전체를 중단시키지 않도록 함

    async def dispatch(self, request: Request, call_next) -> Response:
        # 로그 수집 대상인지 확인
        if not self._should_log_request(request.url.path):
            return await call_next(request)

        # 요청 시작 시간 및 고유 ID 생성 (한국 시간대 사용)
        request_start_time = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
        start_time = time.time()
        request_id = str(uuid.uuid4())

        # Form data 요청인지 확인
        is_form_data = request.headers.get("content-type", "").startswith(
            "multipart/form-data"
        )

        # Path 정보 추출 (한 번만 호출)
        path_info = self._extract_path_info(request.url.path)

        # 요청 정보 수집
        request_body = await self._get_request_body(request)
        user_info = await self._extract_user_info(request, request_body, path_info)
        document_info = self._extract_document_info(
            request, request_body or {}, path_info
        )
        search_info = self._extract_search_info(request, request_body or {})

        # 요청 파라미터 수집 (Query + Path Parameters)
        all_params = dict(request.query_params)
        all_params.update(path_info["path_params"])

        # 기본 로그 데이터 구성 (JSON 컬럼은 딕셔너리 그대로 전달)
        log_data = {
            "request_id": request_id,
            "user_id": user_info["user_id"],
            "group_id": user_info["group_id"],
            "role_id": user_info["role_id"],
            "action_type": self._determine_action_type(
                request.method, request.url.path
            ),
            "endpoint": request.url.path,
            "http_method": request.method,
            "request_params": self._sanitize_data(all_params),  # 딕셔너리 그대로
            "action_details": self._sanitize_data(request_body),  # 딕셔너리 그대로
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "session_id": request.headers.get("x-session-id"),
            "request_start_time": request_start_time,
            "created_at": request_start_time,
            **document_info,
            **search_info,
        }

        try:
            # 요청 처리
            response = await call_next(request)

            # 응답 정보 수집 (한국 시간대 사용)
            request_end_time = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Form data 요청의 경우 응답 후 action_details 및 사용자 정보 보완
            if is_form_data:
                logger.debug(f"✅ Form data 요청 감지됨 - request_id: {request_id}")
                if hasattr(request.state, "form_data_for_logging"):
                    form_data = request.state.form_data_for_logging
                    logger.debug(f"✅ Form data 로깅 정보 발견됨: {form_data}")
                    log_data["action_details"] = self._sanitize_data(form_data)

                    # Form data에서 사용자 정보 업데이트 (user_id가 없는 경우)
                    if not log_data["user_id"] and "user_id" in form_data:
                        try:
                            user_id = int(form_data["user_id"])
                            log_data["user_id"] = user_id

                            # JWT에서 group_id, role_id 정보 가져오기
                            if hasattr(request.state, "user") and request.state.user:
                                jwt_data = request.state.user
                                if jwt_data.get("group_id"):
                                    log_data["group_id"] = jwt_data.get("group_id")
                                if jwt_data.get("role_id"):
                                    log_data["role_id"] = jwt_data.get("role_id")
                            
                            logger.debug(
                                f"✅ Form data에서 사용자 정보 업데이트 완료: user_id={user_id}, group_id={log_data.get('group_id')}, role_id={log_data.get('role_id')}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"⚠️ Form data에서 사용자 정보 업데이트 실패: {e}"
                            )

                    # 문서 정보도 업데이트
                    if "title" in form_data:
                        log_data["document_title"] = form_data["title"]
                    if "category" in form_data:
                        log_data["document_category"] = form_data["category"]

                else:
                    logger.warning(
                        f"⚠️ Form data 요청이지만 form_data_for_logging 속성이 없음 - request_id: {request_id}"
                    )

            # 응답 본문에서 추가 정보 추출 (가능한 경우)
            response_body = {}
            try:
                if hasattr(response, "body"):
                    response_body = json.loads(response.body.decode())
            except Exception:
                pass

            # 검색 결과 개수 추출
            if log_data["action_type"] == "SEARCH" and response_body:
                log_data["search_results_count"] = len(response_body.get("results", []))

            # 비용 정보 추출
            cost_info = self._extract_cost_info(request_body or {}, response_body)

            # 로그 데이터 완성
            log_data.update(
                {
                    "status_code": response.status_code,
                    "success": (
                        "SUCCESS" if 200 <= response.status_code < 400 else "FAILED"
                    ),
                    "processing_time_ms": processing_time_ms,
                    "request_end_time": request_end_time,
                    **cost_info,
                }
            )

            # 비동기로 로그 저장
            await self._save_action_log(log_data)

            return response

        except Exception as e:
            # 오류 발생 시 로그 데이터 업데이트 (한국 시간대 사용)
            request_end_time = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Form data 요청의 경우 오류 시에도 action_details 및 사용자 정보 보완 시도
            if is_form_data and hasattr(request.state, "form_data_for_logging"):
                form_data = request.state.form_data_for_logging
                log_data["action_details"] = self._sanitize_data(form_data)

                # Form data에서 사용자 정보 업데이트 (user_id가 없는 경우)
                if not log_data["user_id"] and "user_id" in form_data:
                    try:
                        user_id = int(form_data["user_id"])
                        log_data["user_id"] = user_id

                        # JWT에서 group_id, role_id 정보 가져오기
                        if hasattr(request.state, "user") and request.state.user:
                            jwt_data = request.state.user
                            if jwt_data.get("group_id"):
                                log_data["group_id"] = jwt_data.get("group_id")
                            if jwt_data.get("role_id"):
                                log_data["role_id"] = jwt_data.get("role_id")
                        
                        logger.debug(
                            f"✅ 오류 시 Form data에서 사용자 정보 업데이트 완료: user_id={user_id}, group_id={log_data.get('group_id')}, role_id={log_data.get('role_id')}"
                        )
                    except Exception as update_e:
                        logger.warning(
                            f"⚠️ 오류 시 Form data에서 사용자 정보 업데이트 실패: {update_e}"
                        )

            log_data.update(
                {
                    "status_code": 500,
                    "success": "ERROR",
                    "error_message": str(e),
                    "error_type": type(e).__name__,
                    "processing_time_ms": processing_time_ms,
                    "request_end_time": request_end_time,
                }
            )

            # 오류 로그 저장
            await self._save_action_log(log_data)

            # 원본 예외 재발생
            raise


async def get_user_info_from_jwt(request: Request) -> Dict[str, Any]:
    """
    JWT에서 사용자 정보 추출

    TODO: user_service.py 제거됨 - JWT 미들웨어에서 설정한 request.state.user 사용
    """
    user_info = {"user_id": None, "group_id": None, "role_id": None}

    try:
        # JWT 미들웨어에서 설정한 사용자 정보 가져오기
        if hasattr(request.state, "user") and request.state.user:
            jwt_payload = request.state.user
            user_info["user_id"] = jwt_payload.get("user_id")
            user_info["group_id"] = jwt_payload.get("group_id")
            user_info["role_id"] = jwt_payload.get("role_id")
            logger.debug(f"JWT에서 사용자 정보 추출: {user_info}")
    except Exception as e:
        logger.warning(f"JWT에서 사용자 정보 추출 실패: {e}")

    return user_info


async def extract_user_id_from_request(request: Request) -> Optional[int]:
    """요청에서 사용자 ID 추출"""
    try:
        # 1. JWT 토큰에서 사용자 ID 추출 시도
        if hasattr(request.state, "user") and request.state.user:
            user_id = request.state.user.get("user_id")
            if user_id:
                logger.debug(f"JWT에서 사용자 ID 추출: {user_id}")
                return int(user_id)

        # 2. URL 경로에서 사용자 ID 추출 시도
        path_parts = request.url.path.strip("/").split("/")
        for part in path_parts:
            if part.isdigit():
                user_id = int(part)
                logger.debug(f"URL 경로에서 사용자 ID 추출: {user_id}")
                return user_id

        # 3. 쿼리 파라미터에서 사용자 ID 추출 시도
        user_id_param = request.query_params.get("user_id")
        if user_id_param and user_id_param.isdigit():
            user_id = int(user_id_param)
            logger.debug(f"쿼리 파라미터에서 사용자 ID 추출: {user_id}")
            return user_id

        logger.debug("사용자 ID를 추출할 수 없음")
        return None

    except Exception as e:
        logger.warning(f"사용자 ID 추출 중 오류: {e}")
        return None


async def create_base_log_data(
    request: Request, start_time: float, user_info: Dict[str, Any]
) -> Dict[str, Any]:
    """기본 로그 데이터 생성"""
    return {
        "endpoint": str(request.url.path),
        "method": request.method,
        "user_id": user_info["user_id"],
        "group_id": user_info["group_id"],
        "role_id": user_info["role_id"],  # privilege 대신 role_id 사용
        "request_time": start_time,
        "user_agent": request.headers.get("user-agent", ""),
        "remote_addr": (
            getattr(request.client, "host", None) if request.client else None
        ),
    }


async def log_form_data(
    request: Request, log_data: Dict[str, Any], user_info: Dict[str, Any]
) -> None:
    """Form 데이터 요청 로깅 처리"""
    try:
        # TODO: user_service.py 제거됨 - JWT에서 직접 정보 가져오기
        # 기존 로직은 폼 데이터에서 user_id를 추출해서 DB 조회했으나
        # 이제 JWT에서 모든 정보를 가져올 수 있음

        # 폼 데이터 읽기
        form_data = await request.form()
        form_dict = dict(form_data)

        # 사용자 ID 추출 (폼 데이터 우선, 없으면 JWT 사용)
        user_id = None
        if "user_id" in form_dict and form_dict["user_id"]:
            try:
                user_id = int(form_dict["user_id"])
            except ValueError:
                pass

        if not user_id and user_info["user_id"]:
            user_id = user_info["user_id"]

        if user_id:
            log_data["user_id"] = user_id
            # JWT에서 추가 정보 사용
            if user_info["group_id"]:
                log_data["group_id"] = user_info["group_id"]
            if user_info["role_id"]:
                log_data["role_id"] = user_info["role_id"]

            logger.debug(
                f"✅ Form data에서 사용자 정보 업데이트 완료: user_id={user_id}, group_id={user_info.get('group_id')}, role_id={user_info.get('role_id')}"
            )

        # 요청 본문 기록
        log_data["request_body"] = form_dict  # TODO: _sanitize_dict 함수 정의 필요

    except Exception as e:
        logger.warning(f"Form 데이터 로깅 처리 중 오류: {e}")


async def log_json_data(
    request: Request, log_data: Dict[str, Any], user_info: Dict[str, Any]
) -> None:
    """JSON 데이터 요청 로깅 처리"""
    try:
        # TODO: user_service.py 제거됨 - JWT에서 직접 정보 가져오기

        # JSON 데이터 읽기
        json_data = await request.json()

        # 사용자 ID 추출 (JSON 데이터 우선, 없으면 JWT 사용)
        user_id = None
        if "user_id" in json_data and json_data["user_id"]:
            try:
                user_id = int(json_data["user_id"])
            except (ValueError, TypeError):
                pass

        if not user_id and user_info["user_id"]:
            user_id = user_info["user_id"]

        if user_id:
            log_data["user_id"] = user_id
            # JWT에서 추가 정보 사용
            if user_info["group_id"]:
                log_data["group_id"] = user_info["group_id"]
            if user_info["role_id"]:
                log_data["role_id"] = user_info["role_id"]

        # 요청 본문 기록
        log_data["request_body"] = json_data  # TODO: _sanitize_dict 함수 정의 필요

    except Exception as e:
        logger.warning(f"JSON 데이터 로깅 처리 중 오류: {e}")
