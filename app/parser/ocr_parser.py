"""Naver Cloud OCR 기반 이미지 PDF 폴백 파서

기존 PdfParser가 텍스트 추출 불가(스캔 이미지형)로 판정한 PDF에 대해서만
보조(fallback)로 동작한다. 일반 텍스트 PDF는 이 파서를 거치지 않는다.

설계 원칙 (Celery 워커 OOM 이력 반영, 보수적 처리):
- 페이지 단위 순차 처리 (전체 페이지 일괄 이미지 변환 금지)
- 페이지마다 렌더→OCR 호출→텍스트만 보관→이미지/bytes 즉시 해제
- DPI 상한 적용 (settings.OCR_RENDER_DPI, 하드 캡 200)
- 페이지 수 상한 초과 시 OCR 미수행 (limit_exceeded)
- 외부 API timeout/retry 제한 (transient 오류만 재시도)
- OCR_SECRET_KEY 등 민감정보는 절대 로깅하지 않음

URL은 settings.OCR_APIGW_INVOKE_URL(URL1)만 사용한다.
URL2(OCR_APIGW_INVOKE_URL2)는 Secret validate failed로 사용하지 않는다.
"""

import asyncio
import base64
import logging
import time
from typing import Dict, List

import fitz
import requests

from app.config.settings import settings
from app.parser.base import ParserInterface

logger = logging.getLogger(__name__)

# DPI 하드 캡 (설정이 더 크더라도 이 값을 넘기지 않음 - 메모리/payload 방어)
OCR_DPI_HARD_MAX = 200

# 렌더된 PNG가 이 크기를 넘으면 DPI를 한 단계 낮춰 1회 재렌더 (단일 초대형 페이지 방어)
OCR_PNG_SOFT_LIMIT_BYTES = 8_000_000

# 페이지 평균 신뢰도가 이 값 미만이면 해당 페이지 텍스트를 신뢰하지 않음
OCR_MIN_CONFIDENCE = 0.3

# 재시도 대상(transient) HTTP 상태 코드
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# 즉시 중단(설정/인증 오류) 대상 HTTP 상태 코드
_FATAL_STATUS = {400, 401, 403, 404}


class OcrUnavailableError(Exception):
    """OCR 폴백을 수행할 수 없거나 결과가 비어 ocr_required 유지가 필요한 경우.

    Attributes:
        reason: "limit_exceeded" | "empty" | "api_error" | "config_missing"
    """

    def __init__(self, reason: str, message: str = "") -> None:
        self.reason = reason
        super().__init__(message or reason)


class OcrParser(ParserInterface):
    """Naver Cloud OCR 폴백 파서.

    반환 구조는 기존 파서와 동일한 List[{"page_number": int, "text": str}] 이다.
    """

    async def parsing(self, file_path: str, filename: str = None) -> List[Dict]:
        """이미지 PDF를 페이지 단위로 OCR 처리하여 텍스트를 반환한다.

        Args:
            file_path: 임시 PDF 파일 경로
            filename: 원본 파일명 (로깅용)

        Returns:
            List[Dict]: [{"page_number": int, "text": str}, ...]

        Raises:
            OcrUnavailableError: 페이지 초과 / 결과 없음 / API 오류 / 설정 누락
        """
        return await asyncio.to_thread(self._parsing_sync, file_path, filename)

    def get_parser_name(self) -> str:
        return "ocr_parser"

    def get_supported_extensions(self) -> List[str]:
        return [".pdf"]

    def _parsing_sync(self, file_path: str, filename: str) -> List[Dict]:
        url = settings.OCR_APIGW_INVOKE_URL
        secret = settings.OCR_SECRET_KEY
        if not url or not secret:
            logger.error("[OCR] 설정 누락: OCR_APIGW_INVOKE_URL/OCR_SECRET_KEY 없음")
            raise OcrUnavailableError("config_missing", "OCR 설정이 없습니다.")

        max_pages = settings.OCR_MAX_PAGES
        dpi = min(settings.OCR_RENDER_DPI, OCR_DPI_HARD_MAX)

        doc = fitz.open(file_path)
        try:
            total_pages = doc.page_count
            if total_pages > max_pages:
                logger.info(
                    f"[OCR] OCR skipped: page_count exceeded limit "
                    f"(pages={total_pages}, limit={max_pages}, filename={filename})"
                )
                raise OcrUnavailableError(
                    "limit_exceeded",
                    f"페이지 수 {total_pages} > 한도 {max_pages}",
                )

            logger.info(
                f"[OCR] OCR fallback started: filename={filename}, "
                f"pages={total_pages}, dpi={dpi}"
            )

            pages: List[Dict] = []
            total_text_length = 0

            for index in range(total_pages):
                page_no = index + 1
                page_text = self._ocr_single_page(
                    doc=doc,
                    index=index,
                    page_no=page_no,
                    total_pages=total_pages,
                    dpi=dpi,
                    url=url,
                    secret=secret,
                )
                pages.append({"page_number": page_no, "text": page_text})
                total_text_length += len(page_text)

            if total_text_length == 0:
                logger.info(
                    f"[OCR] OCR 결과 비어 있음 - 임베딩 미진행: filename={filename}"
                )
                raise OcrUnavailableError("empty", "OCR 결과 텍스트가 비어 있습니다.")

            logger.info(
                f"[OCR] OCR completed: total_text_length={total_text_length}, "
                f"pages_processed={len(pages)}"
            )
            return pages
        finally:
            doc.close()

    def _ocr_single_page(
        self,
        doc: "fitz.Document",
        index: int,
        page_no: int,
        total_pages: int,
        dpi: int,
        url: str,
        secret: str,
    ) -> str:
        """페이지 1장을 렌더링하여 OCR 호출 후 텍스트를 반환한다.

        transient 오류는 재시도 후에도 실패하면 빈 문자열을 반환(해당 페이지 skip).
        설정/인증 오류(_FATAL_STATUS)는 OcrUnavailableError로 즉시 중단한다.
        """
        logger.info(f"[OCR] page {page_no}/{total_pages} render started")
        png_b64 = self._render_page_to_png_b64(doc, index, dpi)

        try:
            text = self._call_naver_ocr(
                png_b64=png_b64,
                page_no=page_no,
                total_pages=total_pages,
                url=url,
                secret=secret,
            )
            logger.info(
                f"[OCR] page {page_no}/{total_pages} request success, "
                f"text_length={len(text)}"
            )
            return text
        finally:
            # 페이지 이미지 데이터 즉시 해제
            del png_b64

    @staticmethod
    def _render_page_to_png_b64(doc: "fitz.Document", index: int, dpi: int) -> str:
        """페이지를 PNG로 렌더링하여 base64 문자열로 반환한다.

        렌더 결과가 과대하면 DPI를 한 단계 낮춰 1회 재렌더한다.
        """
        pix = doc[index].get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")
        del pix

        if len(png_bytes) > OCR_PNG_SOFT_LIMIT_BYTES:
            lowered = max(72, dpi // 2)
            logger.info(
                f"[OCR] page render too large ({len(png_bytes)} bytes) - "
                f"re-render at dpi={lowered}"
            )
            del png_bytes
            pix = doc[index].get_pixmap(dpi=lowered)
            png_bytes = pix.tobytes("png")
            del pix

        encoded = base64.b64encode(png_bytes).decode()
        del png_bytes
        return encoded

    def _call_naver_ocr(
        self,
        png_b64: str,
        page_no: int,
        total_pages: int,
        url: str,
        secret: str,
    ) -> str:
        """Naver Cloud OCR(General V2)을 호출하여 인식 텍스트를 반환한다.

        Returns:
            str: 인식 텍스트 (페이지 skip 시 빈 문자열)

        Raises:
            OcrUnavailableError: 설정/인증 오류(_FATAL_STATUS) 시 즉시 중단
        """
        payload = {
            "version": "V2",
            "requestId": f"ocr-p{page_no}-{int(time.time() * 1000)}",
            "timestamp": int(time.time() * 1000),
            "images": [{"format": "png", "name": f"page-{page_no}", "data": png_b64}],
        }
        headers = {"X-OCR-SECRET": secret, "Content-Type": "application/json"}

        max_retries = settings.OCR_MAX_RETRIES
        timeout = settings.OCR_TIMEOUT_SECONDS

        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(
                    url, headers=headers, json=payload, timeout=timeout
                )
            except requests.exceptions.Timeout:
                logger.warning(
                    f"[OCR] page {page_no}/{total_pages} request failed, "
                    f"timeout (attempt={attempt + 1}/{max_retries + 1})"
                )
                continue
            except requests.exceptions.RequestException as exc:
                logger.warning(
                    f"[OCR] page {page_no}/{total_pages} request failed, "
                    f"network error={type(exc).__name__} "
                    f"(attempt={attempt + 1}/{max_retries + 1})"
                )
                continue

            status = resp.status_code
            if status == 200:
                return self._extract_text_from_response(resp.json(), page_no)

            if status in _FATAL_STATUS:
                logger.error(
                    f"[OCR] page {page_no}/{total_pages} request failed, "
                    f"status_code={status} (설정/인증 오류 - 중단)"
                )
                raise OcrUnavailableError(
                    "api_error", f"OCR API 오류 status={status}"
                )

            if status in _RETRYABLE_STATUS:
                logger.warning(
                    f"[OCR] page {page_no}/{total_pages} request failed, "
                    f"status_code={status} (transient - "
                    f"attempt={attempt + 1}/{max_retries + 1})"
                )
                continue

            logger.warning(
                f"[OCR] page {page_no}/{total_pages} request failed, "
                f"status_code={status} (unexpected - skip page)"
            )
            return ""

        logger.warning(
            f"[OCR] page {page_no}/{total_pages} 재시도 소진 - skip page"
        )
        return ""

    @staticmethod
    def _extract_text_from_response(body: Dict, page_no: int) -> str:
        """Naver OCR 응답에서 페이지 텍스트를 재구성한다.

        General OCR은 단어 단위 fields를 반환하므로 inferText를 이어 붙인다.
        평균 신뢰도가 너무 낮으면 빈 문자열로 처리한다.
        """
        images = body.get("images", [])
        if not images:
            return ""

        image = images[0]
        if image.get("inferResult") != "SUCCESS":
            logger.warning(
                f"[OCR] page {page_no} inferResult != SUCCESS: "
                f"{image.get('inferResult')}"
            )
            return ""

        fields = image.get("fields", [])
        if not fields:
            return ""

        parts: List[str] = []
        confidences: List[float] = []
        for field in fields:
            parts.append(field.get("inferText", ""))
            parts.append("\n" if field.get("lineBreak") else " ")
            if "inferConfidence" in field:
                confidences.append(field["inferConfidence"])

        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            if avg_conf < OCR_MIN_CONFIDENCE:
                logger.warning(
                    f"[OCR] page {page_no} 평균 신뢰도 낮음 "
                    f"(avg={avg_conf:.3f}) - 페이지 텍스트 무시"
                )
                return ""

        return "".join(parts).strip()
