from fastapi import APIRouter
from app.api.v1.endpoints.documents_api import router as documents_router
from app.api.v1.endpoints.embeddings_api import router as embeddings_router
from app.api.v1.endpoints.schedules_api import router as schedules_router
from app.api.v1.endpoints.costs_api import router as cost_router
from app.api.v1.endpoints.sse_api import router as sse_router
from app.api.v1.endpoints.action_logs_api import router as action_logs_router
from app.api.v1.endpoints.mcp_api import router as mcp_router
from app.api.v1.endpoints.graph_api import router as graph_router
from app.api.v1.endpoints.parser_config_api import router as parser_config_router
from app.api.v1.endpoints.categories_api import router as categories_router
from app.api.v1.endpoints.admin_api import router as admin_router
from app.api.v1.endpoints.ragas_api import router as ragas_router

api_router = APIRouter()

# 라우터 등록 - 논리적 순서로 정렬
# 1. 문서 관리 (기본 기능)
api_router.include_router(documents_router, prefix="/v1/documents", tags=["문서 관리"])

# 1-1. 카테고리 관리 (사용자 정의 카테고리)
api_router.include_router(
    categories_router, prefix="/v1/categories", tags=["카테고리 관리"]
)

# 2. 임베딩 스케줄 (자동화)
api_router.include_router(
    schedules_router, prefix="/v1/schedules", tags=["임베딩 스케줄"]
)

# 3. AI 문서 처리 (문서 업로드 후 처리)
api_router.include_router(
    embeddings_router, prefix="/v1/embeddings", tags=["AI 문서 처리"]
)

# 4. RAGAS 검색품질 평가
api_router.include_router(
    ragas_router, prefix="/v1/ragas", tags=["RAGAS 검색품질 평가"]
)

# 5. MCP 도구 관리
api_router.include_router(mcp_router, prefix="/v1/mcp", tags=["MCP 도구 관리"])

# 6. Graph RAG (엔티티/관계 관리)
api_router.include_router(graph_router, prefix="/v1/graph", tags=["Graph RAG"])

# 7. 비용 계산 (처리 결과)
api_router.include_router(cost_router, prefix="/v1/costs", tags=["비용 계산"])

# 8. 실시간 기능들
api_router.include_router(sse_router, prefix="/v1/sse", tags=["SSE 진행 상태"])

# 9. 로그 및 모니터링
api_router.include_router(
    action_logs_router, prefix="/v1/action-logs", tags=["사용자 활동 로그"]
)

# 10. 관리자 설정 (파서 설정 등)
api_router.include_router(
    parser_config_router, prefix="/v1/parser-config", tags=["파서 설정 관리 (관리자)"]
)

# 11. 관리자 전용 (컬렉션 관리)
api_router.include_router(
    admin_router, prefix="/v1/admin", tags=["관리자 (컬렉션 관리)"]
)
