"""
문서 처리 유틸리티 함수
파싱된 문서 내용 변환 및 처리를 위한 헬퍼 함수 모음
"""

import logging
from typing import Dict, List, Union

logger = logging.getLogger(__name__)

# 타입 정의
ParsedContent = List[Dict[str, Union[int, str]]]


def merge_parsed_content_to_text(parsed_content: ParsedContent) -> str:
    """
    파싱된 문서 내용을 하나의 문자열로 합치는 유틸리티 함수

    embedding_task.py에서 생성된 parsed_contents를 기존 요약 서비스에서
    사용할 수 있는 문자열 형태로 변환합니다.

    Args:
        parsed_content: 파싱된 문서 내용 [{"page_number": int, "text": str}, ...]

    Returns:
        str: 합쳐진 전체 문서 텍스트

    Raises:
        ValueError: parsed_content가 유효하지 않은 경우

    Example:
        >>> parsed_content = [
        ...     {"page_number": 1, "text": "첫 번째 페이지"},
        ...     {"page_number": 2, "text": "두 번째 페이지"}
        ... ]
        >>> merged_text = merge_parsed_content_to_text(parsed_content)
        >>> # 이제 기존 서비스 사용 가능
        >>> summary = await service.generate_summary(merged_text)
    """
    if not parsed_content:
        raise ValueError("파싱된 문서 내용이 비어있습니다")

    if not isinstance(parsed_content, list):
        raise ValueError("parsed_content는 리스트 타입이어야 합니다")

    # 페이지 번호 순으로 정렬
    sorted_pages = sorted(parsed_content, key=lambda page: page.get("page_number", 0))

    # 각 페이지의 텍스트를 개행으로 구분하여 합치기
    merged_text = "\n\n".join(
        page.get("text", "").strip()
        for page in sorted_pages
        if page.get("text", "").strip()
    )

    logger.debug(
        f"페이지 합치기 완료 - 페이지 수: {len(sorted_pages)}, 전체 길이: {len(merged_text)} 문자"
    )

    return merged_text
