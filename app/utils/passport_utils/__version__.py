"""
Passport Parser 모듈 버전 관리
"""

__version__ = "1.1.0"
__author__ = "indexing-service"
__description__ = "JWT passport 구조를 파싱하고 권한 확인을 위한 유틸리티"

# 버전 히스토리
VERSION_HISTORY = {
    "1.1.0": {
        "date": "2025-08-22",
        "changes": [
            "2단계 인가 플로우 추가 (authorize_request, authorize_request_with_exception)",
            "관리자 권한 우선 검증 함수 추가 (is_admin_role)",
            "새로운 데코레이터 함수들 (require_authorization, require_admin)",
            "기존 주석 처리된 함수들 활성화 및 개선",
            "인가_flow.md 기반 인가 시스템 구현",
            "완전한 하위 호환성 유지"
        ]
    },
    "1.0.0": {
        "date": "2025-07-01",
        "changes": [
            "초기 버전 릴리즈",
            "JWT passport 파싱 기능",
            "권한 확인 함수들",
            "그룹 관련 함수들",
            "편의 함수들"
        ]
    }
} 