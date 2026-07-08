import re
from typing import List
from collections import defaultdict
from app.parser.utils.pii_detector import PIIMatch, PIIType


class AnonymizationStrategy:
    """비식별화 전략 열거형"""
    MASKING = "masking"  # 마스킹
    PSEUDONYMIZATION = "pseudonymization"  # 가명화
    GENERALIZATION = "generalization"  # 일반화


class PIIAnonymizer:
    """개인정보 비식별화 클래스"""
    
    def __init__(self, strategy: str = AnonymizationStrategy.MASKING):
        """
        PII 비식별화기 초기화
        
        Args:
            strategy: 비식별화 전략 (masking, pseudonymization, generalization)
        """
        self.strategy = strategy
        self.pseudonym_counter = defaultdict(int)  # 가명화 카운터
        self.pseudonym_map = {}  # 원본 값과 가명 매핑
        
    def anonymize(self, text: str, pii_matches: List[PIIMatch]) -> str:
        """
        탐지된 개인정보 비식별화
        
        Args:
            text: 원본 텍스트
            pii_matches: PII 매칭 결과 리스트
            
        Returns:
            비식별화된 텍스트
        """
        if not pii_matches:
            return text
        
        # 역순으로 처리 (인덱스 변경 방지)
        sorted_matches = sorted(pii_matches, key=lambda match: match.start, reverse=True)
        
        result = text
        for match in sorted_matches:
            if self.strategy == AnonymizationStrategy.MASKING:
                replacement = self.mask(match.value, match.pii_type)
            elif self.strategy == AnonymizationStrategy.PSEUDONYMIZATION:
                replacement = self.pseudonymize(match.value, match.pii_type)
            elif self.strategy == AnonymizationStrategy.GENERALIZATION:
                replacement = self.generalize(match.value, match.pii_type)
            else:
                replacement = self.mask(match.value, match.pii_type)  # 기본값
            
            result = result[:match.start] + replacement + result[match.end:]
        
        return result
    
    def mask(self, value: str, pii_type: PIIType) -> str:
        """
        마스킹 처리
        
        Args:
            value: 원본 값
            pii_type: PII 유형
            
        Returns:
            마스킹된 값
        """
        if pii_type == PIIType.RESIDENT_ID:
            # 123456-1234567 → ******-*******
            if '-' in value:
                return "******-*******"
            else:
                return "*************"
                
        elif pii_type == PIIType.PHONE:
            # 010-1234-5678 → 010-****-****
            parts = re.split(r'[-\s]', value)
            if len(parts) == 3:
                return f"{parts[0]}-****-****"
            else:
                # 구분자 없는 경우
                if len(value) >= 11:
                    return value[:3] + "*" * (len(value) - 3)
                return "*" * len(value)
                
        elif pii_type == PIIType.EMAIL:
            # user@domain.com → u***@*******.com
            if '@' in value:
                local, domain = value.split('@', 1)
                if '.' in domain:
                    domain_parts = domain.rsplit('.', 1)
                    masked_local = local[0] + '*' * (len(local) - 1) if local else ''
                    masked_domain = '*' * len(domain_parts[0]) + '.' + domain_parts[1]
                    return f"{masked_local}@{masked_domain}"
            return '*' * len(value)
            
        elif pii_type == PIIType.CREDIT_CARD:
            # 1234-5678-9012-3456 → ****-****-****-3456
            parts = re.split(r'[-\s]', value)
            if len(parts) == 4:
                return f"****-****-****-{parts[3]}"
            else:
                # 구분자 없는 경우, 마지막 4자리만 표시
                if len(value) >= 16:
                    return "*" * (len(value) - 4) + value[-4:]
                return "*" * len(value)
                
        elif pii_type == PIIType.ACCOUNT:
            # 계좌번호 - 앞 3자리와 뒤 2자리만 표시
            if len(value) >= 10:
                return value[:3] + "*" * (len(value) - 5) + value[-2:]
            return "*" * len(value)
            
        elif pii_type == PIIType.BUSINESS_ID:
            # 123-45-67890 → ***-**-*****
            if '-' in value:
                return "***-**-*****"
            return "*" * len(value)
            
        elif pii_type == PIIType.PASSPORT:
            # M12345678 → M********
            if value and value[0].isalpha():
                return value[0] + "*" * (len(value) - 1)
            return "*" * len(value)
            
        elif pii_type == PIIType.DRIVER_LICENSE:
            # 11-22-333333-44 → **-**-******-**
            if '-' in value:
                return "**-**-******-**"
            return "*" * len(value)
            
        elif pii_type == PIIType.IP_ADDRESS:
            # 192.168.1.1 → ***.***.***.***
            parts = value.split('.')
            if len(parts) == 4:
                return ".".join(["***"] * 4)
            return "*" * len(value)
            
        elif pii_type == PIIType.MAC_ADDRESS:
            # AA:BB:CC:DD:EE:FF → **:**:**:**:**:**
            separator = ':' if ':' in value else '-'
            parts = value.split(separator)
            if len(parts) == 6:
                return separator.join(["**"] * 6)
            return "*" * len(value)
            
        else:
            # 기본 마스킹 - 전체를 *로 치환
            return "*" * len(value)
    
    def pseudonymize(self, value: str, pii_type: PIIType) -> str:
        """
        가명화 처리
        
        Args:
            value: 원본 값
            pii_type: PII 유형
            
        Returns:
            가명화된 값
        """
        # 이미 가명화된 값이 있으면 재사용
        key = f"{pii_type.value}:{value}"
        if key in self.pseudonym_map:
            return self.pseudonym_map[key]
        
        # 새로운 가명 생성
        self.pseudonym_counter[pii_type] += 1
        counter = self.pseudonym_counter[pii_type]
        
        # PII 유형별 가명 형식
        pseudonym_formats = {
            PIIType.RESIDENT_ID: f"RRN_{counter:03d}",
            PIIType.PHONE: f"PHONE_{counter:03d}",
            PIIType.EMAIL: f"EMAIL_{counter:03d}",
            PIIType.CREDIT_CARD: f"CARD_{counter:03d}",
            PIIType.ACCOUNT: f"ACCOUNT_{counter:03d}",
            PIIType.BUSINESS_ID: f"BIZ_{counter:03d}",
            PIIType.PASSPORT: f"PASSPORT_{counter:03d}",
            PIIType.DRIVER_LICENSE: f"LICENSE_{counter:03d}",
            PIIType.FOREIGN_ID: f"FOREIGN_{counter:03d}",
            PIIType.IP_ADDRESS: f"IP_{counter:03d}",
            PIIType.MAC_ADDRESS: f"MAC_{counter:03d}",
            PIIType.POSTAL_CODE: f"POSTAL_{counter:03d}",
            PIIType.TELEPHONE: f"TEL_{counter:03d}"
        }
        
        pseudonym = pseudonym_formats.get(pii_type, f"PII_{counter:03d}")
        self.pseudonym_map[key] = pseudonym
        
        return pseudonym
    
    def generalize(self, value: str, pii_type: PIIType) -> str:
        """
        일반화 처리
        
        Args:
            value: 원본 값
            pii_type: PII 유형
            
        Returns:
            일반화된 값
        """
        if pii_type == PIIType.RESIDENT_ID:
            # 생년월일만 추출하여 연령대로 변환
            if len(value) >= 6:
                year_prefix = value[:2]
                # 1900년대 또는 2000년대 판별
                gender_digit = value[7] if len(value) > 7 and '-' in value else value[6] if len(value) > 6 else '1'
                if gender_digit in '1256':
                    year = 1900 + int(year_prefix)
                elif gender_digit in '3478':
                    year = 2000 + int(year_prefix)
                else:
                    year = 1900 + int(year_prefix)
                
                # 연령대 계산 (현재 2025년 기준)
                age = 2025 - year
                if age < 20:
                    return "10대"
                elif age < 30:
                    return "20대"
                elif age < 40:
                    return "30대"
                elif age < 50:
                    return "40대"
                elif age < 60:
                    return "50대"
                elif age < 70:
                    return "60대"
                else:
                    return "70대 이상"
            return "연령 정보"
            
        elif pii_type == PIIType.PHONE:
            # 통신사 정보만 유지
            if value.startswith('010'):
                return "010-****-****"
            elif value.startswith('011'):
                return "011-****-****"
            elif value.startswith('016'):
                return "016-****-****"
            elif value.startswith('017'):
                return "017-****-****"
            elif value.startswith('018'):
                return "018-****-****"
            elif value.startswith('019'):
                return "019-****-****"
            return "휴대전화"
            
        elif pii_type == PIIType.EMAIL:
            # 도메인만 유지
            if '@' in value:
                _, domain = value.split('@', 1)
                return f"****@{domain}"
            return "이메일"
            
        elif pii_type == PIIType.IP_ADDRESS:
            # C클래스까지만 표시
            parts = value.split('.')
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
            return "IP주소"
            
        elif pii_type == PIIType.POSTAL_CODE:
            # 시/도 수준으로 일반화
            if value.startswith('0'):
                return "서울"
            elif value.startswith('1'):
                return "경기"
            elif value.startswith('2'):
                return "인천"
            elif value.startswith('3'):
                return "강원"
            elif value.startswith('4'):
                return "충남/충북"
            elif value.startswith('5'):
                return "전남/전북"
            elif value.startswith('6'):
                return "경남/경북"
            elif value.startswith('7'):
                return "제주"
            return "우편번호"
            
        elif pii_type == PIIType.CREDIT_CARD:
            # 카드사 정보만 유지 (BIN 기반)
            if len(value) >= 6:
                bin_code = value[:6].replace('-', '').replace(' ', '')
                if bin_code.startswith('4'):
                    return "VISA카드"
                elif bin_code.startswith('5'):
                    return "MasterCard"
                elif bin_code.startswith('3'):
                    return "AMEX/Diners"
                elif bin_code.startswith('9'):
                    return "국내카드"
            return "신용카드"
            
        else:
            # 기본 일반화 - PII 유형명으로 대체
            type_names = {
                PIIType.BUSINESS_ID: "사업자번호",
                PIIType.ACCOUNT: "계좌번호",
                PIIType.PASSPORT: "여권번호",
                PIIType.DRIVER_LICENSE: "운전면허",
                PIIType.FOREIGN_ID: "외국인등록번호",
                PIIType.MAC_ADDRESS: "MAC주소",
                PIIType.TELEPHONE: "전화번호"
            }
            return type_names.get(pii_type, "개인정보")
    
    def reset_pseudonyms(self):
        """가명화 카운터 및 매핑 초기화"""
        self.pseudonym_counter.clear()
        self.pseudonym_map.clear()