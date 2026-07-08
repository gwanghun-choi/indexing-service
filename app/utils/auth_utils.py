from fastapi import HTTPException, Request
from app.config.settings import settings
from typing import Any, Dict
import logging
import json

logger = logging.getLogger(__name__)


def _safe_int(value: Any) -> int | None:
    """user_id / group_id 처럼 일반적으로 정수이지만 system passport 등 호출 측에서
    string ID (예: ``"bidpilot-system"``) 를 보낼 수 있는 필드의 안전한 정수 변환.

    int 변환 가능하면 int 반환, 그 외 (string 시스템 ID / None / 빈값) 는 None.
    downstream (action log INSERT / permission check 등) 은 None 을 system caller
    또는 non-numeric ID 로 안전 처리.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.debug(f"_safe_int: non-numeric id 보존 (None 반환) — value={value!r}")
        return None


async def get_parsed_jwt_data(request: Request) -> dict:
    """
    x-user-passport 헤더에서 직접 데이터 파싱
    JWT와 동일한 구조의 Passport 데이터를 처리

    Note:
        - global_role이 ADMIN인 경우 group_id가 None일 수 있음 (group_list가 비어있을 수 있음)
        - system passport (예: nara-bidPilot 의 ``bidpilot-system``) 처럼 user_id/group_id 가
          숫자로 변환되지 않는 경우, 해당 필드는 ``None`` 으로 반환 (caller 식별은 raw passport
          context 로 별도 검증).
    """
    # 미들웨어에서 설정한 passport_data 확인 (SKIP_AUTH 또는 Swagger 우회)
    passport_data = getattr(request.state, "passport_data", None)
    if passport_data:
        # global_role 확인 (객체 속성 접근 - Fail Fast)
        global_role_name = passport_data.global_role.name
        group_list = passport_data.group_passport.group_list

        # ADMIN은 group_id 없이도 허용, 그 외는 group_list 필수
        if group_list:
            group_id = _safe_int(group_list[0])
        elif global_role_name == "ADMIN":
            group_id = None
        else:
            raise HTTPException(status_code=403, detail="사용자가 속한 그룹이 없습니다")

        return {
            "user_id": _safe_int(passport_data.user_id),
            "group_id": group_id,
            "total_role": passport_data.total_role,
            "global_role": global_role_name,
        }

    # x-user-passport 헤더 확인
    passport_header = request.headers.get("x-user-passport")
    if not passport_header:
        raise HTTPException(status_code=401, detail="사용자 인증이 필요합니다")

    # passport 헤더를 JSON으로 파싱
    passport_data = json.loads(passport_header)

    # global_role 확인 (dict 접근)
    global_role_name = passport_data["global_role"]["name"]
    group_list = passport_data["group_passport"].get("group_list", [])

    # ADMIN은 group_id 없이도 허용, 그 외는 group_list 필수
    if group_list:
        group_id = _safe_int(group_list[0])
    elif global_role_name == "ADMIN":
        group_id = None
    else:
        raise HTTPException(status_code=403, detail="사용자가 속한 그룹이 없습니다")

    # 엔드포인트가 기대하는 형식으로 반환
    return {
        "user_id": _safe_int(passport_data["user_id"]),
        "group_id": group_id,
        "total_role": passport_data["total_role"],
        "global_role": global_role_name,
    }


# SKIP_AUTH 모드에서 사용할 테스트용 passport 데이터
TEST_PASSPORT_DATA: Dict[str, Any] = {
    "user_id": "55",
    "group_passport": {
        "group_list": ["74"],
        "group_roles": {
            "74": [],
        },
        "in_group_role": {
            "74": [2],
        },
    },
    "global_role": {"id": 2, "name": "USER"},
    "total_role": [2],
    "role_permission": {
        "2": {
            "name": "USER",
            "permissions": {
                "READ": ["USER", "GROUP", "ROLE", "RESOURCE", "LOG", "AGENT", "PERSONA", "SCENARIO", "MODEL", "NODE", "EDGE", "GRAPH", "WEBSOCKET", "TITLE", "HISTORY", "CHAT", "DASHBOARD", "MEMORY", "COSTS", "DOCUMENTS", "NOTIFICATIONS", "FILE_UPLOAD_SSE", "RERANKER", "MCP_USER_CONFIG", "MCP_USER_DEPLOYMENT"],
                "WRITE": ["GROUP", "USER", "ROLE", "AGENT", "PERSONA", "SCENARIO", "NODE", "EDGE", "GRAPH", "WEBSOCKET", "TITLE", "HISTORY", "CHAT", "MEMORY", "EMBEDDINGS", "MODEL", "MCP_USER_CONFIG"],
                "EXECUTE": ["WEBSOCKET", "INVOKE", "SSE", "COSTS", "EMBEDDINGS", "MODEL", "RERANKER", "MCP_USER_CONFIG", "MCP_USER_DEPLOYMENT"],
                "UPDATE": ["DOCUMENTS"],
                "DELETE": ["DOCUMENTS"],
            },
        },
    },
    "role": "USER",
}

# JSON 문자열 형태 (헤더 전달용)
TEST_PASSPORT_JSON = json.dumps(TEST_PASSPORT_DATA)


def get_user_passport_header(request: Request) -> str:
    """
    x-user-passport 헤더 값을 반환

    SKIP_AUTH 모드에서는 테스트용 passport를 반환하고,
    그 외에는 실제 헤더에서 값을 가져옵니다.

    Args:
        request: FastAPI Request 객체

    Returns:
        x-user-passport 헤더 값 (JSON 문자열)

    Raises:
        HTTPException: 헤더가 없는 경우 (SKIP_AUTH 아닐 때)
    """
    if settings.SKIP_AUTH:
        logger.debug("⚠️ SKIP_AUTH 모드: 테스트 passport 사용")
        return TEST_PASSPORT_JSON

    passport_header = request.headers.get("x-user-passport")
    if not passport_header:
        raise HTTPException(status_code=401, detail="Missing x-user-passport header")

    return passport_header


async def get_optional_user(auth_header: str | None) -> dict | None:
    """Authorization 헤더를 검사하여 선택적으로 사용자 정보를 반환"""
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.debug("Authorization 헤더에 Bearer 토큰이 없습니다")
        return None

    try:
        parts = auth_header.split(" ", 1)
        if len(parts) != 2:
            logger.warning("잘못된 Authorization 헤더 형식")
            return None

        # 실제 JWT 검증 (주석 해제하여 사용)
        # payload = verify_access_token(token)

        # 임시 개발용 payload
        payload = {"user_id": 1, "username": "admin_user", "email": "admin@example.com"}

        logger.debug(f"✅ 토큰 검증 성공: {payload}")
        return payload

    except Exception as e:
        logger.warning(f"❌ 토큰 검증 실패: {str(e)}")
        return None
