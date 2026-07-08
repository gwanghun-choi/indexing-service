"""
KTC Parser 어댑터

KT Cloud Document Parse API를 ParserInterface에 맞게 래핑합니다.
"""

import logging
from typing import Dict, List

from app.parser.base import ParserConfig, ParserInterface, ParseResult

logger = logging.getLogger(__name__)


class KTCParserAdapter(ParserInterface):
    """
    KT Cloud Document Parser 어댑터 (Adapter Pattern)

    외부 KTC API를 ParserInterface에 맞게 래핑합니다.

    특징:
        - 모든 문서를 LLM이 이해할 수 있는 구조화된 텍스트로 변환
        - OCR 과정 없이도 복잡한 문서의 레이아웃을 정확하게 분석
        - 표와 텍스트를 논리적인 순서대로 정렬하여 출력
    """

    # 지원 확장자 목록
    # - 문서: PDF, DOCX, PPTX, XLSX
    # - 이미지: JPEG, PNG, BMP, TIFF, HEIC
    SUPPORTED_EXTENSIONS = [
        ".pdf", ".docx", ".pptx", ".xlsx",
        ".jpeg", ".jpg", ".png", ".bmp", ".tiff", ".heic"
    ]

    def __init__(self, config: ParserConfig) -> None:
        """
        KTCParserAdapter 초기화

        Args:
            config: 파서 설정 (api_endpoint, api_key 필수)

        Raises:
            ValueError: api_endpoint 또는 api_key가 누락된 경우
        """
        if not config.api_endpoint:
            raise ValueError("KTC Parser requires api_endpoint")
        if not config.api_key:
            raise ValueError("KTC Parser requires api_key")

        self.config = config

    async def parsing(self, file_path: str, filename: str = None) -> List[Dict]:
        """
        파일을 파싱합니다. (기존 호환성 유지)

        Args:
            file_path: 파일 경로
            filename: 원본 파일 이름 (확장자 포함, API 파일 타입 인식용)

        Returns:
            List[Dict]: 파싱된 내용 (page_number, text 포함)
        """
        # NOTE: 의존성 분리를 위한 Lazy import
        from app.parser.ktc_parser import parse_document

        return parse_document(
            file_path=file_path,
            endpoint=self.config.api_endpoint,
            api_key=self.config.api_key,
            filename=filename,
        )

    async def parse(self, file_path: str, **kwargs) -> List[ParseResult]:
        """
        문서를 파싱합니다. (새 인터페이스)

        Args:
            file_path: 파싱할 파일 경로
            **kwargs: 추가 옵션

        Returns:
            List[ParseResult]: 파싱 결과 리스트
        """
        raw_results = await self.parsing(file_path, kwargs["filename"])

        # 공통 형식으로 변환
        return [
            ParseResult(
                content=result["text"],
                metadata={"parser": "ktc_parser"},
                page_number=result["page_number"],
            )
            for result in raw_results
        ]

    def get_supported_extensions(self) -> List[str]:
        """지원하는 파일 확장자 목록을 반환합니다."""
        return self.SUPPORTED_EXTENSIONS

    def get_parser_name(self) -> str:
        """파서 식별자를 반환합니다."""
        return "ktc_parser"
