from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ParserConfig:
    """
    파서 설정 데이터 클래스

    Attributes:
        parser_name: 파서 식별자 (예: 'ktc_parser')
        api_endpoint: API 엔드포인트 URL
        api_key: API 인증 키
        timeout_seconds: 타임아웃 (초)
        extra_config: 추가 설정 (OCR 옵션 등)
    """

    parser_name: str
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: int = 300
    extra_config: Optional[Dict[str, Any]] = None


@dataclass
class ParseResult:
    """
    파싱 결과 데이터 클래스

    Attributes:
        content: 파싱된 텍스트 내용
        metadata: 메타데이터 (파서 정보, 카테고리 등)
        page_number: 페이지 번호 (선택)
    """

    content: str
    metadata: Dict[str, Any]
    page_number: Optional[int] = None


class ParserInterface(ABC):
    """
    문서 파서 공통 인터페이스 (Adapter Pattern의 Target Interface)

    모든 파서 어댑터는 이 인터페이스를 구현해야 합니다.
    새로운 파서 추가 시 이 인터페이스만 구현하면 됩니다.
    """

    @abstractmethod
    async def parsing(
        self, file_path: str, filename: str = None
    ) -> List[Dict]:
        """
        파일을 파싱합니다. (기존 호환성 유지)

        Args:
            file_path: 파일 경로
            filename: 원본 파일 이름 (선택사항)

        Returns:
            List[Dict]: 파싱된 내용
        """
        pass

    async def parse(self, file_path: str, **kwargs) -> List[ParseResult]:
        """
        문서를 파싱합니다. (새 인터페이스, 선택적 오버라이드)

        기본 구현은 parsing() 메서드를 호출하여 결과를 변환합니다.
        필요 시 서브클래스에서 오버라이드할 수 있습니다.

        Args:
            file_path: 파싱할 파일 경로
            **kwargs: 추가 옵션 (filename 등)

        Returns:
            List[ParseResult]: 파싱 결과 리스트
        """
        filename = kwargs.get("filename")
        raw_results = await self.parsing(file_path, filename)
        return [
            ParseResult(
                content=r.get("text", ""),
                metadata={"parser": self.get_parser_name()},
                page_number=r.get("page_number"),
            )
            for r in raw_results
        ]

    def get_supported_extensions(self) -> List[str]:
        """
        지원하는 파일 확장자 목록을 반환합니다. (선택적 오버라이드)

        기본 구현은 빈 리스트를 반환합니다.

        Returns:
            List[str]: 지원 확장자 목록 (예: ['.pdf', '.docx'])
        """
        return []

    def get_parser_name(self) -> str:
        """
        파서 식별자를 반환합니다. (선택적 오버라이드)

        기본 구현은 클래스명에서 파서 이름을 자동 생성합니다.
        예: PdfParser -> pdf_parser

        Returns:
            str: 파서 이름 (예: 'default', 'ktc_parser')
        """
        return self.__class__.__name__.lower().replace("parser", "_parser")
