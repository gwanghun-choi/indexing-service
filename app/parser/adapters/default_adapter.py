"""
기본 파서 어댑터

내장 파서들을 ParserInterface에 맞게 래핑합니다.
"""

import logging
from typing import Dict, List, Optional

from app.parser.base import ParserConfig, ParserInterface, ParseResult

logger = logging.getLogger(__name__)


class DefaultParserAdapter(ParserInterface):
    """
    기본 내장 파서 어댑터 (Adapter Pattern)

    기존 내부 파서 구현을 ParserInterface에 맞게 래핑합니다.
    file_type에 따라 적절한 파서를 선택합니다.
    """

    # 지원 확장자 목록
    SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"]

    def __init__(
        self,
        config: Optional[ParserConfig] = None,
        file_type: Optional[str] = None,
        enable_pii_anonymization: bool = False,
        pii_strategy: str = "masking",
        pii_types: Optional[List[str]] = None,
    ) -> None:
        """
        DefaultParserAdapter 초기화

        Args:
            config: 파서 설정 (선택)
            file_type: 파일 유형 (pdf, docx 등)
            enable_pii_anonymization: PII 비식별화 활성화 여부
            pii_strategy: PII 비식별화 전략
            pii_types: 처리할 PII 유형 리스트
        """
        self.config = config or ParserConfig(parser_name="default")
        self.file_type = file_type
        self.enable_pii_anonymization = enable_pii_anonymization
        self.pii_strategy = pii_strategy
        self.pii_types = pii_types
        self._parser = None

    async def _get_parser(self):
        """내부 파서 인스턴스를 가져옵니다."""
        if self._parser is None and self.file_type:
            # NOTE: 순환 참조 방지를 위한 Lazy import (adapters → factory)
            from app.parser.factory import create_parser

            self._parser = await create_parser(
                file_type=self.file_type,
                enable_pii_anonymization=self.enable_pii_anonymization,
                pii_strategy=self.pii_strategy,
                pii_types=self.pii_types,
            )
        return self._parser

    async def parsing(self, file_path: str, filename: str = None) -> List[Dict]:
        """
        파일을 파싱합니다. (기존 호환성 유지)

        Args:
            file_path: 파일 경로
            filename: 원본 파일 이름

        Returns:
            List[Dict]: 파싱된 내용
        """
        parser = await self._get_parser()
        if parser:
            return await parser.parsing(file_path, filename)
        return []

    async def parse(self, file_path: str, **kwargs) -> List[ParseResult]:
        """
        문서를 파싱합니다. (새 인터페이스)

        Args:
            file_path: 파싱할 파일 경로
            **kwargs: 추가 옵션 (filename 등)

        Returns:
            List[ParseResult]: 파싱 결과 리스트
        """
        filename = kwargs.get("filename")
        raw_results = await self.parsing(file_path, filename)

        # 공통 형식으로 변환
        return [
            ParseResult(
                content=result["text"],
                metadata={"parser": "default"},
                page_number=result["page_number"],
            )
            for result in raw_results
        ]

    def get_supported_extensions(self) -> List[str]:
        """지원하는 파일 확장자 목록을 반환합니다."""
        return self.SUPPORTED_EXTENSIONS

    def get_parser_name(self) -> str:
        """파서 식별자를 반환합니다."""
        return "default"
