from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("api_gateway")


async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ [ERROR] {request.url} {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )
