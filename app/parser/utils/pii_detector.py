import re
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum


class PIIType(Enum):
    """PII 유형 정의"""
    RESIDENT_ID = "resident_id"  # 주민등록번호
    PASSPORT = "passport"  # 여권번호
    DRIVER_LICENSE = "driver_license"  # 운전면허번호
    FOREIGN_ID = "foreign_id"  # 외국인등록번호
    PHONE = "phone"  # 휴대전화
    TELEPHONE = "telephone"  # 일반전화
    CREDIT_CARD = "credit_card"  # 신용카드
    ACCOUNT = "account"  # 계좌번호
    BUSINESS_ID = "business_id"  # 사업자등록번호
    EMAIL = "email"  # 이메일
    IP_ADDRESS = "ip_address"  # IP 주소
    MAC_ADDRESS = "mac_address"  # MAC 주소
    POSTAL_CODE = "postal_code"  # 우편번호


@dataclass
class PIIMatch:
    """PII 매칭 결과"""
    pii_type: PIIType
    value: str
    start: int
    end: int
    risk_level: str  # high, medium, low


class PIIDetector:
    """개인정보 탐지 클래스"""
    
    def __init__(self):
        """PII 탐지기 초기화"""
        self.patterns = self._compile_patterns()
        
    def _compile_patterns(self) -> Dict[PIIType, Dict[str, any]]:
        """정규식 패턴 컴파일"""
        patterns = {
            PIIType.RESIDENT_ID: {
                "pattern": re.compile(r'\d{6}[-\s]?[1-4]\d{6}'),
                "risk_level": "high",
                "description": "주민등록번호"
            },
            PIIType.PASSPORT: {
                "pattern": re.compile(r'[A-Z]{1}[0-9]{8}|[A-Z]{2}[0-9]{7}'),
                "risk_level": "high",
                "description": "여권번호"
            },
            PIIType.DRIVER_LICENSE: {
                "pattern": re.compile(r'\d{2}-\d{2}-\d{6}-\d{2}'),
                "risk_level": "high",
                "description": "운전면허번호"
            },
            PIIType.FOREIGN_ID: {
                "pattern": re.compile(r'\d{6}[-\s]?[5-8]\d{6}'),
                "risk_level": "high",
                "description": "외국인등록번호"
            },
            PIIType.PHONE: {
                "pattern": re.compile(r'01[0-9][-\s]?\d{3,4}[-\s]?\d{4}'),
                "risk_level": "medium",
                "description": "휴대전화번호"
            },
            PIIType.TELEPHONE: {
                "pattern": re.compile(r'0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}'),
                "risk_level": "medium",
                "description": "일반전화번호"
            },
            PIIType.CREDIT_CARD: {
                "pattern": re.compile(r'\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}'),
                "risk_level": "high",
                "description": "신용카드번호"
            },
            PIIType.ACCOUNT: {
                "pattern": re.compile(r'\d{6,14}'),  # 간단한 패턴, 실제로는 은행별 검증 필요
                "risk_level": "high",
                "description": "계좌번호"
            },
            PIIType.BUSINESS_ID: {
                "pattern": re.compile(r'\d{3}-\d{2}-\d{5}'),
                "risk_level": "medium",
                "description": "사업자등록번호"
            },
            PIIType.EMAIL: {
                "pattern": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
                "risk_level": "low",
                "description": "이메일주소"
            },
            PIIType.IP_ADDRESS: {
                "pattern": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
                "risk_level": "low",
                "description": "IP주소"
            },
            PIIType.MAC_ADDRESS: {
                "pattern": re.compile(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'),
                "risk_level": "low",
                "description": "MAC주소"
            },
            PIIType.POSTAL_CODE: {
                "pattern": re.compile(r'\b\d{5}\b'),
                "risk_level": "low",
                "description": "우편번호"
            }
        }
        return patterns
    
    def detect(self, text: str, pii_types: List[PIIType] = None) -> List[PIIMatch]:
        """
        텍스트에서 개인정보 패턴 탐지
        
        Args:
            text: 탐지할 텍스트
            pii_types: 탐지할 PII 유형 리스트 (None이면 모든 유형)
            
        Returns:
            PIIMatch 리스트
        """
        matches = []
        
        # 탐지할 PII 유형 결정
        types_to_detect = pii_types if pii_types else list(PIIType)
        
        for pii_type in types_to_detect:
            if pii_type not in self.patterns:
                continue
                
            pattern_info = self.patterns[pii_type]
            pattern = pattern_info["pattern"]
            risk_level = pattern_info["risk_level"]
            
            # 패턴 매칭
            for match in pattern.finditer(text):
                # 중복 방지 (이미 탐지된 범위와 겹치는지 확인)
                overlap = False
                for existing in matches:
                    if (match.start() >= existing.start and match.start() < existing.end) or \
                       (match.end() > existing.start and match.end() <= existing.end):
                        overlap = True
                        break
                
                if not overlap:
                    matches.append(PIIMatch(
                        pii_type=pii_type,
                        value=match.group(),
                        start=match.start(),
                        end=match.end(),
                        risk_level=risk_level
                    ))
        
        # 시작 위치로 정렬
        matches.sort(key=lambda match: match.start)
        return matches
    
    def validate_resident_id(self, value: str) -> bool:
        """
        주민등록번호 유효성 검증
        
        Args:
            value: 검증할 주민등록번호
            
        Returns:
            유효한 경우 True
        """
        # 하이픈 제거
        value = value.replace("-", "").replace(" ", "")
        
        if len(value) != 13:
            return False
        
        # 기본 형식 체크
        if not value.isdigit():
            return False
        
        # 생년월일 유효성 체크
        month = int(value[2:4])
        day = int(value[4:6])
        
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        
        # 체크섬 검증 (선택적)
        # 실제 서비스에서는 보안상 체크섬 검증을 하지 않을 수도 있음
        
        return True
    
    def validate_credit_card(self, value: str) -> bool:
        """
        신용카드번호 유효성 검증 (Luhn 알고리즘)
        
        Args:
            value: 검증할 신용카드번호
            
        Returns:
            유효한 경우 True
        """
        # 공백과 하이픈 제거
        value = value.replace("-", "").replace(" ", "")
        
        if not value.isdigit() or len(value) < 13 or len(value) > 19:
            return False
        
        # Luhn 알고리즘
        total = 0
        reverse_digits = value[::-1]
        
        for i, digit in enumerate(reverse_digits):
            digit_value = int(digit)
            if i % 2 == 1:
                digit_value *= 2
                if digit_value > 9:
                    digit_value -= 9
            total += digit_value
        
        return total % 10 == 0
    
    def get_statistics(self, matches: List[PIIMatch]) -> Dict[str, int]:
        """
        탐지 결과 통계
        
        Args:
            matches: PIIMatch 리스트
            
        Returns:
            PII 유형별 개수
        """
        stats = {}
        for match in matches:
            pii_type_name = match.pii_type.value
            stats[pii_type_name] = stats.get(pii_type_name, 0) + 1
        return stats
