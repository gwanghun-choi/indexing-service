"""
Passport 파싱 유틸리티

하위 서비스에서 JWT passport 구조를 파싱하고 권한 확인을 위한 유틸리티 함수들을 제공합니다.
Gateway에서 전달받은 x-user-passport 헤더를 파싱하여 인가 처리를 수행합니다.
"""

import json
import logging
import functools
import inspect
from typing import Dict, List, Optional, Union, Any, Callable
from dataclasses import dataclass
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

# 타입 별칭 정의
ActionType = str  # "READ", "WRITE", "DELETE", etc.
ResourceType = str  # "MODEL", "USER", "GROUP", etc.
GroupId = str
RoleId = int
UserId = str


@dataclass
class GlobalRole:
    """글로벌 역할 정보"""
    id: int
    name: str


@dataclass  
class GroupPassport:
    """그룹 passport 정보"""
    group_list: List[str]
    group_roles: Dict[str, List[int]]  # GroupRole entity의 role들
    in_group_role: Dict[str, List[int]]  # UserGroup entity의 role들


@dataclass
class RolePermission:
    """역할별 권한 정보"""
    name: str
    permissions: Dict[str, List[str]]  # {"READ": ["MODEL", "USER"], "WRITE": ["GROUP"]}


@dataclass
class PassportData:
    """정규화된 passport 데이터 구조"""
    user_id: str
    global_role: GlobalRole
    group_passport: GroupPassport
    total_role: List[int]
    role_permission: Dict[str, RolePermission]


# =============================================================================
# 1. 파싱 함수들
# =============================================================================
def parse_passport_from_headers(headers: Union[Dict[str, str], Request]) -> PassportData:
    """
    HTTP 헤더에서 passport 정보를 파싱합니다.
    
    Args:
        headers: HTTP 헤더 dict 또는 FastAPI Request 객체
        
    Returns:
        PassportData: 파싱된 passport 데이터
        
    Raises:
        HTTPException: passport 헤더가 없거나 파싱 실패 시
        
    Example:
        >>> passport = parse_passport_from_headers(request.headers)
        >>> print(passport.user_id)
        "12345"
    """
    try:
        # Request 객체인 경우 headers 추출
        if hasattr(headers, 'headers'):
            headers = headers.headers
            
        passport_header = headers.get("x-user-passport")
        if not passport_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing x-user-passport header"
            )
            
        passport_data = json.loads(passport_header)
        return _parse_passport_dict(passport_data)
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse passport JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid passport format"
        )
    except Exception as e:
        logger.error(f"Unexpected error parsing passport: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse passport"
        )

def parse_passport_from_dict(passport_data: Union[Dict[str, Any], str]) -> PassportData:
    """
    일반 dict 또는 JSON 문자열에서 passport 정보를 파싱합니다.
    
    Args:
        passport_data: passport 데이터 dict 또는 JSON 문자열
        
    Returns:
        PassportData: 파싱된 passport 데이터
        
    Raises:
        HTTPException: passport 데이터가 유효하지 않거나 파싱 실패 시
        
    Example:
        >>> passport_dict = {"user_id": "12345", "global_role": {"id": 1, "name": "admin"}, ...}
        >>> passport = parse_passport_from_dict(passport_dict)
        >>> print(passport.user_id)
        "12345"
        
        >>> passport_json = '{"user_id": "12345", "global_role": {"id": 1, "name": "admin"}, ...}'
        >>> passport = parse_passport_from_dict(passport_json)
        >>> print(passport.user_id)
        "12345"
    """
    try:
        # 문자열인 경우 JSON 파싱
        if isinstance(passport_data, str):
            passport_data = json.loads(passport_data)
        
        # dict가 아닌 경우 오류
        if not isinstance(passport_data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passport data must be a dictionary or JSON string"
            )
            
        return _parse_passport_dict(passport_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse passport JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format in passport data"
        )
    except Exception as e:
        logger.error(f"Unexpected error parsing passport dict: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse passport data"
        )



def _parse_passport_dict(data: Dict[str, Any]) -> PassportData:
    """
    딕셔너리 형태의 passport 데이터를 PassportData 객체로 변환합니다.
    
    Args:
        data: passport 딕셔너리 데이터
        
    Returns:
        PassportData: 파싱된 passport 객체
    """
    # Global role 파싱
    global_role_data = data.get("global_role", {})
    global_role = GlobalRole(
        id=global_role_data.get("id", 0),
        name=global_role_data.get("name", "")
    )
    
    # Group passport 파싱
    group_data = data.get("group_passport", {})
    group_passport = GroupPassport(
        group_list=group_data.get("group_list", []),
        group_roles=group_data.get("group_roles", {}),
        in_group_role=group_data.get("in_group_role", {})
    )
    
    # Role permission 파싱
    role_permissions = {}
    for role_id, role_data in data.get("role_permission", {}).items():
        role_permissions[role_id] = RolePermission(
            name=role_data.get("name", ""),
            permissions=role_data.get("permissions", {})
        )
    
    return PassportData(
        user_id=str(data.get("user_id", "")),
        global_role=global_role,
        group_passport=group_passport,
        total_role=data.get("total_role", []),
        role_permission=role_permissions
    )


# =============================================================================
# 2. 권한 확인 함수들
# =============================================================================

def is_admin_role(passport: PassportData) -> bool:
    """
    관리자 권한을 가지고 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        
    Returns:
        bool: 관리자 여부
        
    Example:
        >>> is_admin_role(passport)
        True
    """
    # 글로벌 ADMIN 역할 확인
    return passport.global_role.name == "ADMIN"


def authorize_request(passport: PassportData, action: ActionType, resource: ResourceType) -> bool:
    """
    2단계 인가 플로우를 통해 요청을 인가합니다.
    
    1단계: 관리자 권한 검증 (passport_role >= Admin인가?)
    - 예 → PASS (즉시 통과)
    - 아니요 → 2단계로 진행
    
    2단계: 리소스별 권한 검증
    - passport가 가진 resource_type, action_type으로 해당 API 접근 가능한가?
    - 예 → PASS
    - 아니요 → 인가 실패
    
    Args:
        passport: passport 데이터
        action: 액션 타입 ("READ", "WRITE", "DELETE" 등)
        resource: 리소스 타입 ("MODEL", "USER", "GROUP" 등)
        
    Returns:
        bool: 인가 성공 여부
        
    Example:
        >>> authorize_request(passport, "WRITE", "MODEL")
        True
    """
    # 1단계: 관리자 권한 우선 검증
    if is_admin_role(passport):
        logger.info(f"Authorization PASSED - Admin role detected for user {passport.user_id}")
        return True
    
    # 2단계: 세밀한 권한 검증
    if has_permission(passport, action, resource):
        logger.info(f"Authorization PASSED - User {passport.user_id} has {action} permission for {resource}")
        return True
    
    # 인가 실패
    logger.warning(f"Authorization FAILED - User {passport.user_id} lacks {action} permission for {resource}")
    return False


def authorize_request_with_exception(passport: PassportData, action: ActionType, resource: ResourceType) -> None:
    """
    2단계 인가 플로우를 통해 요청을 인가하며, 실패 시 HTTPException을 발생시킵니다.
    
    Args:
        passport: passport 데이터
        action: 액션 타입 ("READ", "WRITE", "DELETE" 등)
        resource: 리소스 타입 ("MODEL", "USER", "GROUP" 등)
        
    Raises:
        HTTPException: 인가 실패 시 403 Forbidden
        
    Example:
        >>> authorize_request_with_exception(passport, "WRITE", "MODEL")
        # 성공 시 아무것도 반환하지 않음, 실패 시 HTTPException 발생
    """
    if not authorize_request(passport, action, resource):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions: {action} access to {resource} denied"
        )

def has_permission(passport: PassportData, action: ActionType, resource: ResourceType) -> bool:
    """
    특정 액션과 리소스에 대한 권한이 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        action: 액션 타입 ("READ", "WRITE", "DELETE" 등)
        resource: 리소스 타입 ("MODEL", "USER", "GROUP" 등)
        
    Returns:
        bool: 권한 보유 여부
        
    Example:
        >>> has_permission(passport, "WRITE", "MODEL")
        True
    """
    for role_id in passport.total_role:
        role_str = str(role_id)
        if role_str in passport.role_permission:
            role_perms = passport.role_permission[role_str].permissions
            if action in role_perms and resource in role_perms[action]:
                return True
    return False


def has_role(passport: PassportData, role_id: RoleId) -> bool:
    """
    특정 역할을 보유하고 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        role_id: 확인할 역할 ID
        
    Returns:
        bool: 역할 보유 여부
        
    Example:
        >>> has_role(passport, 1)  # ADMIN 역할 확인
        True
    """
    return role_id in passport.total_role


def get_global_role(passport: PassportData) -> int:
    """
    특정 글로벌 역할을 보유하고 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        role_id: 확인할 글로벌 역할 ID
        
    Returns:
        bool: 글로벌 역할 보유 여부
        
    Example:
        >>> has_global_role(passport, 1)  # ADMIN 역할 확인
        True
    """
    return passport.global_role.id


def has_group_role(passport: PassportData, group_id: GroupId, role_id: RoleId) -> bool:
    """
    특정 그룹 내에서 특정 역할을 보유하고 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        group_id: 그룹 ID
        role_id: 확인할 역할 ID
        
    Returns:
        bool: 그룹 내 역할 보유 여부
        
    Example:
        >>> has_group_role(passport, "Group_id_3", 101)  # GROUP_MEMBER 역할 확인
        True
    """
    # GroupRole entity 역할 확인
    group_roles = passport.group_passport.group_roles.get(group_id, [])
    if role_id in group_roles:
        return True
        
    # UserGroup entity 역할 확인
    in_group_roles = passport.group_passport.in_group_role.get(group_id, [])
    return role_id in in_group_roles


# =============================================================================
# 3. 그룹 관련 함수들
# =============================================================================

def get_user_groups(passport: PassportData) -> List[str]:
    """
    사용자가 소속된 모든 그룹 ID를 반환합니다.
    
    Args:
        passport: passport 데이터
        
    Returns:
        List[str]: 그룹 ID 목록
        
    Example:
        >>> get_user_groups(passport)
        ["Group_id_3", "Group_id_4"]
    """
    return passport.group_passport.group_list.copy()


def get_user_roles_in_group(passport: PassportData, group_id: GroupId) -> List[int]:
    """
    특정 그룹 내에서 사용자가 가진 역할들을 반환합니다.
    
    Args:
        passport: passport 데이터
        group_id: 그룹 ID
        
    Returns:
        List[int]: 그룹 내 사용자 역할 ID 목록
        
    Example:
        >>> get_user_roles_in_group(passport, "Group_id_3")
        [101]  # GROUP_MEMBER
    """
    return passport.group_passport.in_group_role.get(group_id, []).copy()


def get_group_roles(passport: PassportData, group_id: GroupId) -> List[int]:
    """
    특정 그룹 자체가 가진 역할들을 반환합니다.
    
    Args:
        passport: passport 데이터
        group_id: 그룹 ID
        
    Returns:
        List[int]: 그룹 역할 ID 목록
        
    Example:
        >>> get_group_roles(passport, "Group_id_3")
        [100, 102]  # GROUP_ADMIN, GROUP_VIEWER
    """
    return passport.group_passport.group_roles.get(group_id, []).copy()


def is_group_member(passport: PassportData, group_id: GroupId) -> bool:
    """
    특정 그룹의 멤버인지 확인합니다.
    
    Args:
        passport: passport 데이터
        group_id: 그룹 ID
        
    Returns:
        bool: 그룹 멤버 여부
        
    Example:
        >>> is_group_member(passport, "Group_id_3")
        True
    """
    return group_id in passport.group_passport.group_list


# =============================================================================
# 4. 편의 함수들
# =============================================================================
def get_user_id(passport: PassportData) -> str:
    """
    사용자 ID를 반환합니다.
    """
    return passport.user_id


def is_admin(passport: PassportData) -> bool:
    """
    관리자 권한을 가지고 있는지 확인합니다. (is_admin_role의 별칭)
    
    Args:
        passport: passport 데이터
        
    Returns:
        bool: 관리자 여부
        
    Example:
        >>> is_admin(passport)
        True
    """
    return is_admin_role(passport)


def can_read(passport: PassportData, resource: ResourceType) -> bool:
    """
    특정 리소스에 대한 읽기 권한이 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        resource: 리소스 타입
        
    Returns:
        bool: 읽기 권한 여부
        
    Example:
        >>> can_read(passport, "MODEL")
        True
    """
    return has_permission(passport, "READ", resource)


def can_write(passport: PassportData, resource: ResourceType) -> bool:
    """
    특정 리소스에 대한 쓰기 권한이 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        resource: 리소스 타입
        
    Returns:
        bool: 쓰기 권한 여부
        
    Example:
        >>> can_write(passport, "MODEL")
        True
    """
    return has_permission(passport, "WRITE", resource)


def can_delete(passport: PassportData, resource: ResourceType) -> bool:
    """
    특정 리소스에 대한 삭제 권한이 있는지 확인합니다.
    
    Args:
        passport: passport 데이터
        resource: 리소스 타입
        
    Returns:
        bool: 삭제 권한 여부
        
    Example:
        >>> can_delete(passport, "MODEL")
        False
    """
    return has_permission(passport, "DELETE", resource)


def get_all_permissions(passport: PassportData) -> Dict[str, List[str]]:
    """
    사용자가 가진 모든 권한을 반환합니다.
    
    Args:
        passport: passport 데이터
        
    Returns:
        Dict[str, List[str]]: 액션별 리소스 목록
        
    Example:
        >>> get_all_permissions(passport)
        {
            "READ": ["MODEL", "USER", "GROUP"],
            "WRITE": ["MODEL", "USER"]
        }
    """
    all_permissions = {}
    
    for role_id in passport.total_role:
        role_str = str(role_id)
        if role_str in passport.role_permission:
            role_perms = passport.role_permission[role_str].permissions
            
            for action, resources in role_perms.items():
                if action not in all_permissions:
                    all_permissions[action] = []
                
                for resource in resources:
                    if resource not in all_permissions[action]:
                        all_permissions[action].append(resource)
    
    return all_permissions


def get_role_name(passport: PassportData, role_id: RoleId) -> Optional[str]:
    """
    역할 ID에 해당하는 역할 이름을 반환합니다.
    
    Args:
        passport: passport 데이터
        role_id: 역할 ID
        
    Returns:
        Optional[str]: 역할 이름 (없으면 None)
        
    Example:
        >>> get_role_name(passport, 1)
        "ADMIN"
    """
    role_str = str(role_id)
    if role_str in passport.role_permission:
        return passport.role_permission[role_str].name
    return None

def get_total_role(passport: PassportData) -> List[int]:
    """
    사용자가 가진 모든 역할을 반환합니다.
    
    Args:
        passport: passport 데이터
        
    Returns:
        List[int]: 사용자가 가진 모든 역할 ID 목록
        
    Example:
        >>> get_total_role(passport)
        [1, 100, 101, 102]
    """
    return passport.total_role


def get_user_info(passport: PassportData) -> Dict[str, Any]:
    """
    사용자 기본 정보를 반환합니다.
    
    Args:
        passport: passport 데이터
        
    Returns:
        Dict[str, Any]: 사용자 정보
        
    Example:
        >>> get_user_info(passport)
        {
            "user_id": "12345",
            "global_role": {"id": 1, "name": "ADMIN"},
            "groups": ["Group_id_3", "Group_id_4"],
            "total_roles": [1, 100, 101, 102]
        }
    """
    return {
        "user_id": passport.user_id,
        "global_role": {
            "id": passport.global_role.id,
            "name": passport.global_role.name
        },
        "groups": get_user_groups(passport),
        "total_roles": passport.total_role.copy()
    }


# =============================================================================
# 5. 데코레이터 함수들 (FastAPI 호환 개선 버전)
# =============================================================================

def _extract_request_object(func: Callable, args: tuple, kwargs: dict) -> Request:
    """
    함수 인자에서 Request 객체를 추출합니다.
    
    Args:
        func: 원본 함수
        args: 위치 인자들
        kwargs: 키워드 인자들
        
    Returns:
        Request: Request 객체
        
    Raises:
        HTTPException: Request 객체를 찾을 수 없는 경우
    """
    # 1. args에서 Request 객체 찾기
    for arg in args:
        if isinstance(arg, Request):
            return arg
    
    # 2. kwargs에서 Request 객체 찾기
    for value in kwargs.values():
        if isinstance(value, Request):
            return value
    
    # 3. 함수 시그니처를 분석해서 Request 타입 파라미터 찾기
    try:
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())
        
        # 파라미터 이름으로 찾기
        for param_name, param in sig.parameters.items():
            # 타입 힌트가 Request인 경우
            if param.annotation == Request:
                if param_name in kwargs:
                    value = kwargs[param_name]
                    if isinstance(value, Request):
                        return value
                # 위치 인자에서 찾기
                try:
                    param_index = param_names.index(param_name)
                    if param_index < len(args):
                        value = args[param_index]
                        if isinstance(value, Request):
                            return value
                except (ValueError, IndexError):
                    continue
            
            # 파라미터 이름이 'request'인 경우
            if param_name.lower() == 'request':
                if param_name in kwargs:
                    value = kwargs[param_name]
                    if isinstance(value, Request):
                        return value
                # 위치 인자에서 찾기
                try:
                    param_index = param_names.index(param_name)
                    if param_index < len(args):
                        value = args[param_index]
                        if isinstance(value, Request):
                            return value
                except (ValueError, IndexError):
                    continue
                    
    except Exception as e:
        logger.debug(f"Failed to analyze function signature: {e}")
    
    # 4. 최후의 수단: 'request' 키워드로 찾기
    for key in ['request', 'req']:
        if key in kwargs and isinstance(kwargs[key], Request):
            return kwargs[key]
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Request object not found in function arguments. Available kwargs: {list(kwargs.keys())}"
    )


def require_authorization(action: ActionType, resource: ResourceType):
    """
    2단계 인가 플로우를 사용하여 특정 권한을 요구하는 데코레이터입니다.
    (FastAPI 호환 개선 버전)
    
    Args:
        action: 필요한 액션 ("READ", "WRITE", "DELETE" 등)
        resource: 필요한 리소스 ("MODEL", "USER", "GROUP" 등)
        
    Example:
        @require_authorization("WRITE", "MODEL")
        async def create_model(request: Request):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Request 객체 추출
            request = _extract_request_object(func, args, kwargs)
            
            # 권한 검증 수행
            passport = parse_passport_from_headers(request.headers)
            authorize_request_with_exception(passport, action, resource)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(action: ActionType, resource: ResourceType):
    """
    특정 권한을 요구하는 데코레이터입니다. (FastAPI 호환 개선 버전)
    
    Args:
        action: 필요한 액션
        resource: 필요한 리소스
        
    Example:
        @require_permission("WRITE", "MODEL")
        async def create_model(request: Request):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Request 객체 추출
            request = _extract_request_object(func, args, kwargs)
            
            # 권한 검증 수행
            passport = parse_passport_from_headers(request.headers)
            if not has_permission(passport, action, resource):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: {action} {resource}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role_id: RoleId):
    """
    특정 역할을 요구하는 데코레이터입니다. (FastAPI 호환 개선 버전)
    
    Args:
        role_id: 필요한 역할 ID
        
    Example:
        @require_role(1)  # ADMIN 역할 필요
        async def admin_only_function(request: Request):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Request 객체 추출
            request = _extract_request_object(func, args, kwargs)
            
            # 역할 검증 수행
            passport = parse_passport_from_headers(request.headers)
            if not has_role(passport, role_id):
                role_name = get_role_name(passport, role_id)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required role: {role_name or role_id}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_admin():
    """
    관리자 권한을 요구하는 데코레이터입니다. (FastAPI 호환 개선 버전)
    
    Example:
        @require_admin()
        async def admin_function(request: Request):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Request 객체 추출
            request = _extract_request_object(func, args, kwargs)
            
            # 관리자 권한 검증 수행
            passport = parse_passport_from_headers(request.headers)
            if not is_admin_role(passport):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# 6. 유틸리티 함수들
# =============================================================================

def debug_passport(passport: PassportData) -> str:
    """
    디버깅용 passport 정보를 문자열로 반환합니다.
    
    Args:
        passport: passport 데이터
        
    Returns:
        str: 포맷된 passport 정보
    """
    lines = [
        f"User ID: {passport.user_id}",
        f"Global Role: {passport.global_role.name} (ID: {passport.global_role.id})",
        f"Groups: {', '.join(passport.group_passport.group_list)}",
        f"Total Roles: {passport.total_role}",
        "Permissions:"
    ]
    
    for role_id in passport.total_role:
        role_str = str(role_id)
        if role_str in passport.role_permission:
            role_perm = passport.role_permission[role_str]
            lines.append(f"  {role_perm.name} (ID: {role_id}):")
            for action, resources in role_perm.permissions.items():
                lines.append(f"    {action}: {', '.join(resources)}")
    
    return "\n".join(lines)


def validate_passport(passport: PassportData) -> List[str]:
    """
    passport 데이터의 유효성을 검증합니다.
    
    Args:
        passport: passport 데이터
        
    Returns:
        List[str]: 발견된 문제들 (빈 리스트면 유효)
    """
    issues = []
    
    if not passport.user_id:
        issues.append("Missing user_id")
    
    if not passport.global_role.id:
        issues.append("Missing global role ID")
        
    if not passport.global_role.name:
        issues.append("Missing global role name")
    
    if not passport.total_role:
        issues.append("Empty total_role")
    
    # 모든 total_role의 역할이 role_permission에 있는지 확인
    for role_id in passport.total_role:
        role_str = str(role_id)
        if role_str not in passport.role_permission:
            issues.append(f"Role {role_id} not found in role_permission")
    
    return issues 