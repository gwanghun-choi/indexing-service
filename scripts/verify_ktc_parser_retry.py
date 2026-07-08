"""Phase 3: KTC Parser retry 로컬 검증 스크립트

검증 1: parse_document() 직접 호출 → 정상 파싱 결과 반환 확인
검증 2: ConnectionError mock으로 retry 로그 출력 확인
"""

import asyncio
import json
import logging
import os
import sys
from unittest.mock import MagicMock, patch

import requests

# 로컬 실행 시 Docker 호스트명(db) → 실제 서버 IP로 오버라이드
# .env의 POSTGRES_HOST="db"는 Docker 내부 DNS이므로 로컬에서 접속 불가
os.environ["POSTGRES_HOST"] = "211.188.60.43"

# 로깅 설정 (retry 로그 확인용)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# 프로젝트 루트를 path에 추가
sys.path.insert(0, "/root/indexing-service")

from app.crud.postgres.parser_config_crud import select_parser_config  # noqa: E402
from app.parser.ktc_parser import parse_document  # noqa: E402

TEST_FILE = "/root/indexing-service/docs/붙임2. 재단 정보화 매뉴얼_2025년 개정.pdf"


def get_ktc_config() -> tuple:
    """DB에서 KTC Parser 설정을 조회합니다."""
    config = asyncio.run(select_parser_config("ktc_parser"))
    if config is None:
        raise RuntimeError("KTC Parser 설정이 DB에 없습니다")
    return config.api_endpoint, config.api_key


def verify_1_direct_call():
    """검증 1: parse_document() 직접 호출 → 정상 파싱 결과 반환 확인"""
    logger.info("=" * 60)
    logger.info("검증 1: parse_document() 직접 호출")
    logger.info("=" * 60)

    try:
        endpoint, api_key = get_ktc_config()
        result = parse_document(
            file_path=TEST_FILE,
            endpoint=endpoint,
            api_key=api_key,
            filename="붙임2. 재단 정보화 매뉴얼_2025년 개정.pdf",
        )

        logger.info(f"파싱 결과: {len(result)}페이지")
        for page in result[:3]:  # 처음 3페이지만 출력
            text_preview = page["text"][:100] + "..." if len(page["text"]) > 100 else page["text"]
            logger.info(f"  페이지 {page['page_number']}: {text_preview}")

        assert len(result) > 0, "파싱 결과가 비어있습니다"
        assert all("page_number" in p and "text" in p for p in result), "포맷 불일치"

        logger.info("검증 1 PASSED: 정상 파싱 결과 반환")
        return True

    except Exception as e:
        logger.error(f"검증 1 FAILED: {type(e).__name__}: {e}")
        return False


def verify_2_retry_log():
    """검증 2: ConnectionError mock으로 retry 로그 출력 확인"""
    logger.info("=" * 60)
    logger.info("검증 2: ConnectionError mock → retry 로그 확인")
    logger.info("=" * 60)

    # 실제 API 응답을 미리 저장
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = json.dumps({
        "elements": [
            {"page": 1, "content": {"markdown": "retry 검증용 테스트 텍스트"}},
        ]
    })

    try:
        with patch("app.parser.ktc_parser.requests.post") as mock_post, \
             patch("time.sleep") as mock_sleep:
            # 1회 ConnectionError → 2회차 성공
            mock_post.side_effect = [
                requests.exceptions.ConnectionError("connection reset by peer"),
                mock_response,
            ]

            result = parse_document(
                file_path=TEST_FILE,
                endpoint="https://example.com/parse",
                api_key="test-key",
                filename="test.pdf",
            )

            assert mock_post.call_count == 2, f"예상 2회 호출, 실제 {mock_post.call_count}회"
            assert mock_sleep.call_count == 1, f"예상 1회 sleep, 실제 {mock_sleep.call_count}회"
            assert len(result) == 1, "파싱 결과 불일치"

        logger.info(f"retry 후 성공: requests.post {mock_post.call_count}회, sleep {mock_sleep.call_count}회")
        logger.info("검증 2 PASSED: retry 동작 정상")
        return True

    except Exception as e:
        logger.error(f"검증 2 FAILED: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    results = {}

    results["검증 1: 직접 호출"] = verify_1_direct_call()
    print()
    results["검증 2: retry 로그"] = verify_2_retry_log()

    print()
    logger.info("=" * 60)
    logger.info("검증 결과 요약")
    logger.info("=" * 60)
    for name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        logger.info(f"  {name}: {status}")

    all_passed = all(results.values())
    logger.info(f"최종 결과: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    sys.exit(0 if all_passed else 1)
