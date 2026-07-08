"""
파서 팩토리 모듈

팩토리 패턴을 사용하여 파서 인스턴스를 생성합니다.
"""

import logging
from typing import Dict, List, Optional, Type

from app.parser.base import ParserConfig, ParserInterface
from app.parser.pdf_parser import PdfParser
from app.parser.excel_parser import ExcelParser
from app.parser.docx_parser import DocxParser
from app.parser.web_parser import WebParser
from app.parser.ppt_parser import PptParser
from app.parser.utils.cleansing_adapter import CleansingAdapter

logger = logging.getLogger(__name__)


# 파서 모델 매핑 (기존 호환성 유지)
_PARSER_MAP = {
    "pdf": PdfParser,
    "xlsx": ExcelParser,
    "xls": ExcelParser,
    "docx": DocxParser,
    "web": WebParser,
    "ppt": PptParser,
    "pptx": PptParser,
}


async def create_parser(
    file_type: str,
    enable_pii_anonymization: bool = False,
    pii_strategy: str = "masking",
    pii_types: Optional[List[str]] = None,
) -> ParserInterface:
    """
    파일 유형에 맞는 파서 생성 (기존 호환성 유지)

    Args:
        file_type: 파일 확장자
        enable_pii_anonymization: PII 비식별화 활성화 여부
        pii_strategy: PII 비식별화 전략 (masking, pseudonymization, generalization)
        pii_types: 처리할 PII 유형 리스트

    Returns:
        ParserInterface: 클렌징 어댑터로 래핑된 파서 인스턴스
    """
    try:
        logger.info(f"[create_parser] 파서 생성 시작: file_type={file_type}")

        parser_class: Type[ParserInterface] = _PARSER_MAP[file_type]
        logger.info(f"[create_parser] 파서 클래스 찾음: {parser_class.__name__}")

        parser_instance: ParserInterface = parser_class()
        logger.info(
            f"[create_parser] 파서 인스턴스 생성 완료: {type(parser_instance).__name__}"
        )

        cleansing_adapter = CleansingAdapter(
            parser_instance,
            enable_pii_anonymization=enable_pii_anonymization,
            pii_strategy=pii_strategy,
            pii_types=pii_types,
        )
        logger.info("[create_parser] CleansingAdapter 래핑 완료")

        return cleansing_adapter
    except KeyError:
        logger.error(f"[create_parser] 지원하지 않는 파일 유형: {file_type}")
        raise ValueError(f"지원하지 않는 파일 유형: {file_type}")
    except Exception as e:
        logger.error(f"[create_parser] 파서 생성 중 오류: {e}")
        raise


class ParserFactory:
    """
    문서 파서 팩토리 (Factory Pattern)

    파서 이름을 기반으로 적절한 파서 인스턴스를 생성합니다.
    새로운 파서 추가 시 register_adapter로 등록하면 됩니다.
    """

    # 어댑터 레지스트리 (지연 임포트를 위해 문자열로 저장)
    _adapters: Dict[str, Type[ParserInterface]] = {}
    _initialized: bool = False

    @classmethod
    def _initialize_adapters(cls) -> None:
        """기본 어댑터들을 등록합니다."""
        if cls._initialized:
            return

        # NOTE: 순환 참조 방지를 위한 Lazy import (factory ↔ adapters)
        from app.parser.adapters.default_adapter import DefaultParserAdapter
        from app.parser.adapters.ktc_adapter import KTCParserAdapter

        cls._adapters = {
            "default": DefaultParserAdapter,
            "ktc_parser": KTCParserAdapter,
        }
        cls._initialized = True
        logger.info("[ParserFactory] 기본 어댑터 등록 완료")

    @classmethod
    def register_adapter(
        cls, parser_name: str, adapter_class: Type[ParserInterface]
    ) -> None:
        """
        새로운 파서 어댑터를 등록합니다.

        Args:
            parser_name: 파서 식별자
            adapter_class: ParserInterface를 구현한 어댑터 클래스
        """
        cls._initialize_adapters()
        cls._adapters[parser_name] = adapter_class
        logger.info(f"[ParserFactory] 어댑터 등록: {parser_name}")

    @classmethod
    async def create(
        cls,
        parser_name: Optional[str] = None,
        file_type: Optional[str] = None,
        enable_pii_anonymization: bool = False,
        pii_strategy: str = "masking",
        pii_types: Optional[List[str]] = None,
        use_worker_context: bool = False,
    ) -> ParserInterface:
        """
        파서 인스턴스를 생성합니다.

        Args:
            parser_name: 파서 식별자 (None이면 기본 파서)
            file_type: 파일 유형 (기본 파서 사용 시 필요)
            enable_pii_anonymization: PII 비식별화 활성화 여부
            pii_strategy: PII 비식별화 전략
            pii_types: 처리할 PII 유형 리스트
            use_worker_context: Celery 워커에서 호출 시 True

        Returns:
            ParserInterface: 파서 인스턴스

        Raises:
            ValueError: 지원하지 않는 파서이거나 비활성화된 경우
        """
        cls._initialize_adapters()

        # 기본 파서 처리
        if parser_name is None:
            # NOTE: 순환 참조 방지를 위한 Lazy import
            from app.parser.adapters.default_adapter import DefaultParserAdapter

            return DefaultParserAdapter(
                file_type=file_type,
                enable_pii_anonymization=enable_pii_anonymization,
                pii_strategy=pii_strategy,
                pii_types=pii_types,
            )

        # 등록된 어댑터 확인
        if parser_name not in cls._adapters:
            raise ValueError(f"지원하지 않는 파서입니다: {parser_name}")

        # DB에서 파서 설정 조회
        from app.crud.postgres.parser_config_crud import select_parser_config

        config_entity = await select_parser_config(parser_name, use_worker_context)
        config = ParserConfig(
            parser_name=config_entity.parser_name,
            api_endpoint=config_entity.api_endpoint,
            api_key=config_entity.api_key,
            timeout_seconds=config_entity.timeout_seconds,
            extra_config=config_entity.extra_config,
        )

        # 어댑터 인스턴스 생성
        adapter_class = cls._adapters[parser_name]
        parser_instance = adapter_class(config)

        logger.info(
            f"[ParserFactory] 외부 파서 생성 완료: {parser_name}, "
            f"PII={enable_pii_anonymization}"
        )

        # CleansingAdapter로 래핑하여 반환 (텍스트 클렌징 + PII 비식별화 적용)
        return CleansingAdapter(
            parser_instance,
            enable_pii_anonymization=enable_pii_anonymization,
            pii_strategy=pii_strategy,
            pii_types=pii_types,
        )

    @classmethod
    def get_registered_parsers(cls) -> List[str]:
        """등록된 파서 목록을 반환합니다."""
        cls._initialize_adapters()
        return list(cls._adapters.keys())
