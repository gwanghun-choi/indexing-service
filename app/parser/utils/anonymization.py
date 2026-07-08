import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import yaml

from app.parser.utils.pii_anonymizer import AnonymizationStrategy, PIIAnonymizer
from app.parser.utils.pii_detector import PIIDetector, PIIType

logger = logging.getLogger(__name__)


@dataclass
class PIILog:
    """PII 처리 로그"""
    pii_type: str
    original_value: str
    anonymized_value: str
    strategy: str
    risk_level: str
    position: Tuple[int, int]  # (start, end)
    timestamp: str


async def anonymize_text(
    text: str,
    strategy: str = AnonymizationStrategy.MASKING,
    pii_types: Optional[List[str]] = None,
    config: Optional[Dict] = None
) -> Tuple[str, List[PIILog]]:
    """
    텍스트 비식별화 메인 함수
    
    Args:
        text: 원본 텍스트
        strategy: 비식별화 전략 (masking, pseudonymization, generalization)
        pii_types: 처리할 PII 유형 리스트 (None이면 모든 유형)
        config: 추가 설정 (선택적)
    
    Returns:
        Tuple[str, List[PIILog]]: (비식별화된 텍스트, PII 처리 로그)
    """
    if not text:
        return text, []
    
    # PII 유형 변환
    selected_types = None
    if pii_types:
        selected_types = []
        for type_str in pii_types:
            try:
                selected_types.append(PIIType(type_str))
            except ValueError:
                # 잘못된 PII 유형은 무시
                continue
    
    # PII 탐지
    detector = PIIDetector()
    matches = detector.detect(text, selected_types)
    
    if not matches:
        return text, []
    
    # PII 비식별화
    anonymizer = PIIAnonymizer(strategy=strategy)
    
    # 로그 생성 (비식별화 전)
    logs = []
    for match in matches:
        # 비식별화된 값 미리 계산
        if strategy == AnonymizationStrategy.MASKING:
            anonymized_value = anonymizer.mask(match.value, match.pii_type)
        elif strategy == AnonymizationStrategy.PSEUDONYMIZATION:
            anonymized_value = anonymizer.pseudonymize(match.value, match.pii_type)
        elif strategy == AnonymizationStrategy.GENERALIZATION:
            anonymized_value = anonymizer.generalize(match.value, match.pii_type)
        else:
            anonymized_value = anonymizer.mask(match.value, match.pii_type)
        
        log = PIILog(
            pii_type=match.pii_type.value,
            original_value=match.value,
            anonymized_value=anonymized_value,
            strategy=strategy,
            risk_level=match.risk_level,
            position=(match.start, match.end),
            timestamp=datetime.now().isoformat()
        )
        logs.append(log)
    
    # 텍스트 비식별화
    anonymized_text = anonymizer.anonymize(text, matches)
    
    return anonymized_text, logs


async def anonymize_with_config(
    text: str,
    config_path: str = None
) -> Tuple[str, List[PIILog]]:
    """
    설정 파일 기반 텍스트 비식별화
    
    Args:
        text: 원본 텍스트
        config_path: 설정 파일 경로
    
    Returns:
        Tuple[str, List[PIILog]]: (비식별화된 텍스트, PII 처리 로그)
    """
    # 기본 설정
    strategy = AnonymizationStrategy.MASKING
    pii_types = None
    
    # 설정 파일이 있으면 로드
    if config_path:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # 전략 설정
            if 'strategies' in config and 'default' in config['strategies']:
                strategy = config['strategies']['default']

            # PII 유형 필터링
            if 'enabled_types' in config:
                pii_types = config['enabled_types']

        except Exception as e:
            # 설정 파일 로드 실패 시 기본값 사용
            logger.error(f"설정 파일 로드 실패: {e}")
    
    return await anonymize_text(text, strategy=strategy, pii_types=pii_types)


def get_anonymization_summary(logs: List[PIILog]) -> Dict:
    """
    비식별화 처리 요약 정보 생성
    
    Args:
        logs: PII 처리 로그 리스트
    
    Returns:
        Dict: 요약 정보
    """
    if not logs:
        return {
            "total_count": 0,
            "by_type": {},
            "by_risk_level": {},
            "strategy_used": None
        }
    
    summary = {
        "total_count": len(logs),
        "by_type": {},
        "by_risk_level": {"high": 0, "medium": 0, "low": 0},
        "strategy_used": logs[0].strategy if logs else None
    }
    
    for log in logs:
        # PII 유형별 집계
        if log.pii_type not in summary["by_type"]:
            summary["by_type"][log.pii_type] = 0
        summary["by_type"][log.pii_type] += 1
        
        # 위험 수준별 집계
        if log.risk_level in summary["by_risk_level"]:
            summary["by_risk_level"][log.risk_level] += 1
    
    return summary


def export_logs_to_dict(logs: List[PIILog]) -> List[Dict]:
    """
    로그를 딕셔너리 형태로 변환
    
    Args:
        logs: PII 처리 로그 리스트
    
    Returns:
        List[Dict]: 딕셔너리 형태의 로그
    """
    return [asdict(log) for log in logs]