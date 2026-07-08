"""
PII 비식별화 유틸리티 함수
"""

import logging
from typing import List, Optional

from app.parser.utils.pii_anonymizer import PIIAnonymizer
from app.parser.utils.pii_detector import PIIDetector, PIIType

logger = logging.getLogger(__name__)


def apply_pii_to_text(
    text: str,
    strategy: str = "masking",
    pii_types: Optional[List[str]] = None,
) -> str:
    """
    텍스트에 PII 비식별화를 적용합니다.

    Args:
        text: 원본 텍스트
        strategy: 비식별화 전략 (masking, pseudonymization, generalization)
        pii_types: 비식별화할 PII 유형 리스트 (None이면 모든 유형)

    Returns:
        비식별화된 텍스트
    """
    if not text:
        return text

    # PII 탐지
    detector = PIIDetector()
    all_matches = detector.detect(text)

    # pii_types 필터링
    if pii_types:
        # 문자열을 PIIType enum으로 변환
        allowed_types = set()
        for pii_type_str in pii_types:
            try:
                # "EMAIL" -> PIIType.EMAIL
                pii_type_enum = PIIType[pii_type_str.upper()]
                allowed_types.add(pii_type_enum)
            except KeyError:
                logger.warning(f"알 수 없는 PII 유형: {pii_type_str}")

        # 필터링된 매칭만 사용
        filtered_matches = [m for m in all_matches if m.pii_type in allowed_types]
    else:
        filtered_matches = all_matches

    if not filtered_matches:
        return text

    # PII 비식별화
    anonymizer = PIIAnonymizer(strategy=strategy)
    anonymized_text = anonymizer.anonymize(text, filtered_matches)

    return anonymized_text
