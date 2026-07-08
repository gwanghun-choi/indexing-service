"""
파서 어댑터 모듈

각 파서를 공통 인터페이스로 래핑하는 어댑터들을 제공합니다.
"""

from app.parser.adapters.default_adapter import DefaultParserAdapter
from app.parser.adapters.ktc_adapter import KTCParserAdapter

__all__ = ["DefaultParserAdapter", "KTCParserAdapter"]
