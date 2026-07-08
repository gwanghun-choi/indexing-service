"""
KT Cloud Document Parse API 통합 모듈

DB의 indexing_parser_config 테이블에서 설정을 조회하여 사용합니다.
"""

import json
import logging
import os
from typing import Any, Dict, List

import requests

from app.utils.retries import retry_with_backoff

logger = logging.getLogger(__name__)


@retry_with_backoff(
    max_retries=3,
    base_delay=5.0,
    max_delay=30.0,
    backoff_factor=2.0,
    retryable_exceptions=(
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    ),
)
def parse_document(
    file_path: str, endpoint: str, api_key: str, filename: str = None
) -> List[Dict[str, Any]]:
    """
    KT Cloud Document Parse API를 호출하여 문서를 파싱합니다.

    Args:
        file_path: 파싱할 문서의 파일 경로
        endpoint: API 엔드포인트 URL (DB에서 조회)
        api_key: API 인증 키 (DB에서 조회)
        filename: 원본 파일 이름 (확장자 포함, API에 파일 타입 전달용)

    Returns:
        파싱된 문서 내용 (parsed_contents 포맷)

    Raises:
        ValueError: API 키 또는 엔드포인트가 누락된 경우
        Exception: API 호출 실패 시
    """
    # 파라미터 검증
    if not api_key or not endpoint:
        logger.error("❌ 파서 API 설정 누락")
        raise ValueError(
            "파서 API 설정이 누락되었습니다. "
            "DB의 indexing_parser_config 테이블에서 파서 설정을 확인하세요."
        )

    logger.info(f"📄 KT Cloud Document Parse API 호출 시작: {file_path}")

    try:
        # 파일 열기
        with open(file_path, "rb") as file:
            # API 요청 파라미터
            headers = {"Authorization": f"Bearer {api_key}"}

            data = {
                "model": "document-parse",
                "ocr": "auto",
                "output_formats": '["markdown"]',
                "coordinates": "false",
            }

            # 원본 파일명을 포함하여 API가 파일 타입을 인식할 수 있도록 함
            # curl -F 'document=@/path/test.docx' 와 동일하게 동작
            upload_filename = filename if filename else os.path.basename(file_path)
            files = {"document": (upload_filename, file)}

            # API 호출
            response = requests.post(
                endpoint,
                headers=headers,
                data=data,
                files=files,
                timeout=300,  # 5분 타임아웃
            )

            # 응답 확인 및 파싱 (NDJSON: 줄바꿈으로 구분된 복수 JSON 객체)
            if response.status_code == 200:
                first_line = response.text.split("\n")[0]
                response_json = json.loads(first_line)
                logger.info("✅ KT Cloud Document Parse API 호출 성공")
            else:
                error_message = (
                    f"KT Cloud Document Parse API 호출 실패: "
                    f"status_code={response.status_code}, "
                    f"response={response.text}"
                )
                logger.error(f"❌ {error_message}")
                raise Exception(error_message)

            # parsed_contents 포맷으로 변환
            parsed_contents = convert_response_to_contents(response_json)

            logger.info(f"✅ 문서 파싱 완료: {len(parsed_contents)}페이지")
            return parsed_contents

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ KT Cloud Document Parse API 네트워크 오류: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ KT Cloud Document Parse API 호출 중 오류: {e}")
        raise


def convert_response_to_contents(
    response: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    KT Cloud Document Parse API 응답을 parsed_contents 포맷으로 변환합니다.

    Args:
        response: API 응답 JSON

    Returns:
        parsed_contents 포맷의 리스트
        [{"page_number": 1, "text": "..."}, ...]
    """
    elements = response["elements"]

    # 페이지별로 텍스트 그룹화
    page_texts: Dict[int, List[str]] = {}

    for element in elements:
        page_number = element["page"]
        markdown_text = element["content"]["markdown"]

        if page_number not in page_texts:
            page_texts[page_number] = []

        page_texts[page_number].append(markdown_text)

    # parsed_contents 포맷으로 변환
    parsed_contents = []
    for page_number in sorted(page_texts.keys()):
        parsed_contents.append(
            {
                "page_number": page_number,
                "text": "\n".join(page_texts[page_number]),
            }
        )

    return parsed_contents
