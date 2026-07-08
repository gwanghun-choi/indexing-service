"""
Passport Parser 모듈

JWT passport 구조를 파싱하고 권한 확인을 위한 유틸리티 함수들을 제공합니다.

사용 예시:
    from utils.passport import parse_passport_from_headers, has_permission
    
    passport = parse_passport_from_headers(request.headers)
    if has_permission(passport, "READ", "MODEL"):
        # 권한이 있는 경우
        pass
"""

from .__version__ import __version__, __author__, __description__
from .parser import (
    # Core data structures
    PassportData,
    GlobalRole, 
    GroupPassport,
    RolePermission,
    
    # Parsing functions
    parse_passport_from_headers,
    parse_passport_from_dict,
    
    # Permission checking
    has_permission,
    has_role,
    get_global_role,
    has_group_role,
    
    # Group functions
    get_user_groups,
    get_user_roles_in_group,
    get_group_roles,
    
    # Convenience functions
    get_user_id,
    can_read,
    can_write,
    can_delete,
    get_all_permissions,
    get_role_name,
    get_total_role,
    validate_passport,
    
    # FastAPI 호환 데코레이터들
    require_authorization,
    require_permission,
    require_role,
    require_admin,
)

__all__ = [
    # Version info
    "__version__",
    "__author__", 
    "__description__",
    
    # Data structures
    "PassportData",
    "GlobalRole",
    "GroupPassport", 
    "RolePermission",
    
    # Parsing
    "parse_passport_from_headers",
    "parse_passport_from_dict",
    
    # Permission checking
    "has_permission",
    "has_role", 
    "get_global_role",
    "has_group_role",
    
    # Group functions
    "get_user_groups",
    "get_user_roles_in_group",
    "get_group_roles",
    
    # Convenience functions
    "get_user_id",
    "can_read",
    "can_write", 
    "can_delete",
    "get_all_permissions",
    "get_role_name",
    "get_total_role",
    "validate_passport",
    
    # FastAPI 호환 데코레이터들
    "require_authorization",
    "require_permission",
    "require_role",
    "require_admin",
] 