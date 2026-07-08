import asyncio
import logging
import re
from typing import Dict, List, Optional

from app.parser.base import ParserInterface
from app.parser.utils.anonymization import anonymize_text, export_logs_to_dict

logger = logging.getLogger(__name__)


class CleansingAdapter:
    """
    파서 결과를 클렌징하는 어댑터 클래스

    문서 파싱 후 텍스트 내용을 정제하고 형식을 표준화하는 기능 제공
    PII 자동 비식별화 기능 포함
    """

    def __init__(
        self,
        parser: ParserInterface,
        enable_pii_anonymization: bool,
        pii_strategy: str,
        pii_types: Optional[List[str]]
    ) -> None:
        """
        CleansingAdapter 초기화

        Args:
            parser: 원본 파서 인스턴스
            enable_pii_anonymization: PII 비식별화 활성화 여부
            pii_strategy: PII 비식별화 전략 (masking, pseudonymization, generalization)
            pii_types: 처리할 PII 유형 리스트
        """
        self.parser = parser
        self.enable_pii_anonymization = enable_pii_anonymization
        self.pii_strategy = pii_strategy
        self.pii_types = pii_types

    def get_parser_name(self) -> str:
        """내부 파서의 이름을 반환합니다."""
        return self.parser.get_parser_name()

    def get_supported_extensions(self) -> List[str]:
        """내부 파서가 지원하는 파일 확장자 목록을 반환합니다."""
        return self.parser.get_supported_extensions()

    async def parsing(self, file_path: str, filename: str) -> List[Dict]:
        """
        파일을 파싱하고 결과를 클렌징하여 반환

        Args:
            file_path: 파싱할 파일 경로
            filename: 파일 이름

        Returns:
            List[Dict]: 클렌징된 텍스트가 포함된 페이지 목록
            각 페이지는 {'page_number': int, 'text': str, 'pii_log': List[Dict]} 형태
            (PII 비식별화 활성화 시 pii_log 포함)
        """
        logger.info(f"[CleansingAdapter] 파싱 시작: file_path={file_path}, filename={filename}")
        logger.info(f"[CleansingAdapter] 원본 파서 타입: {type(self.parser).__name__}")

        # 원본 파서에서 List[Dict] 형태로 받아옴
        raw_pages = await self.parser.parsing(file_path, filename)
        logger.info(f"[CleansingAdapter] 원본 파서 결과: {len(raw_pages)} 페이지")

        # OCR이 필요한 문서인지 확인
        if raw_pages and len(raw_pages) > 0:
            first_page = raw_pages[0]
            if isinstance(first_page, dict) and first_page.get("needs_ocr", False):  # Optional 필드
                logger.info("[CleansingAdapter] OCR이 필요한 문서 감지 - 클렌징 생략")
                return raw_pages  # OCR이 필요한 경우 그대로 반환

        # 클렌징 적용
        cleansed_pages: List[Dict] = []
        for page in raw_pages:
            text = page["text"]
            # 기본 클렌징
            cleansed_text = await self.cleansing(text)
            
            # PII 비식별화 적용
            page_data = {"page_number": page["page_number"]}
            if self.enable_pii_anonymization:
                anonymized_text, pii_logs = await anonymize_text(
                    cleansed_text, 
                    strategy=self.pii_strategy,
                    pii_types=self.pii_types
                )
                page_data["text"] = anonymized_text
                # PII 로그를 딕셔너리 형태로 변환
                page_data["pii_log"] = export_logs_to_dict(pii_logs)
            else:
                page_data["text"] = cleansed_text
                
            cleansed_pages.append(page_data)
        return cleansed_pages

    @staticmethod
    async def cleansing(text: str) -> str:
        """
        텍스트 클렌징 작업 수행

        Args:
            text: 클렌징할 원본 텍스트

        Returns:
            str: 클렌징된 텍스트
        """
        # 텍스트 클렌징 작업을 비동기 스레드에서 실행
        return await asyncio.to_thread(CleansingAdapter._cleansing_sync, text)

    @staticmethod
    def _cleansing_sync(text: str) -> str:
        """
        동기식 텍스트 클렌징 작업 구현

        Args:
            text: 클렌징할 원본 텍스트

        Returns:
            str: 클렌징된 텍스트
        """
        # 1. 허용할 문자 세트
        allowed_chars = r"[^가-힣a-zA-Z0-9\s!@#\$%\^&\*\(\)_\-\+=\[\]\{\}\|\\:;\"'<>,\.\?/`~\n\rㅇ·]"
        text = re.sub(allowed_chars, "", text)

        # 2. 불필요한 공백 정리
        text = re.sub(r"[ \t]+", " ", text)  # 여러 공백 -> 단일 공백
        text = re.sub(r"\n{3,}", "\n\n", text)  # 3개 이상의 줄바꿈 -> 2개로 축소
        text = text.strip()  # 양쪽 공백 제거

        # 3. RAG용 노이즈 제거
        text = re.sub(r"\n?\s*-\s*\d+\s*-\s*\n?", "\n", text)  # 페이지 번호 (- 1 -, - 45 -)
        text = re.sub(r"!\[image\]\(/image/placeholder\)", "", text)  # 이미지 플레이스홀더

        return text
