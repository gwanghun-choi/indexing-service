import time
import logging
import psutil
import traceback
from typing import Dict, Optional, Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


logger = logging.getLogger("app.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    요청 및 응답 로깅 미들웨어
    """

    SENSITIVE_HEADERS = {"authorization", "cookie", "proxy-authorization"}
    SENSITIVE_FIELDS = {"password", "token", "secret", "api_key"}

    def __init__(self, app):
        super().__init__(app)
        self.process = psutil.Process()

    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        return {
            k: v if k.lower() not in self.SENSITIVE_HEADERS else "[FILTERED]"
            for k, v in headers.items()
        }

    async def _get_request_body(self, request: Request) -> Optional[Dict[Any, Any]]:
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                return self._sanitize_dict(body)
            except Exception:
                return None
        return None

    def _sanitize_dict(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        if not isinstance(data, dict):
            return data

        return {
            k: "[FILTERED]"
            if k.lower() in self.SENSITIVE_FIELDS
            else self._sanitize_dict(v)
            if isinstance(v, dict)
            else v
            for k, v in data.items()
        }

    def _get_system_metrics(self) -> Dict[str, float]:
        return {
            "cpu_percent": self.process.cpu_percent(),
            "memory_percent": self.process.memory_percent(),
            "open_files": len(self.process.open_files()),
            "threads": len(self.process.threads()),
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", "")

        # Request logging
        request_body = await self._get_request_body(request)
        logger.info(
            "Request received",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host,
                "headers": self._sanitize_headers(dict(request.headers)),
                "body": request_body,
                "system_metrics_start": self._get_system_metrics(),
            },
        )

        try:
            response = await call_next(request)

            # Response logging
            process_time = time.time() - start_time
            logger.info(
                "Response sent",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.3f}s",
                    "system_metrics_end": self._get_system_metrics(),
                },
            )

            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "process_time": f"{process_time:.3f}s",
                    "system_metrics": self._get_system_metrics(),
                },
            )
            raise
