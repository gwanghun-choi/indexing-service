import os
import pathlib
import logging.config
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from pymilvus import connections

from app.api.v1.router import api_router
from app.config.database import connect_to_milvus, async_engine
from app.config.settings import settings
from app.middleware.action_log_middleware import ActionLogMiddleware
from app.middleware.auth_middleware import AuthMiddleware
from app.service.rabbitmq_consumer import RabbitMQConsumer
from app.service.permission_service import PermissionService
from app.config.infrastructure.cache.redis_cache import RedisCache, RedisConfig


# 📌 YAML 로깅 설정 적용
def setup_logging():
    """로깅 설정을 초기화합니다."""
    try:
        # 로그 디렉토리 생성
        os.makedirs("logs", exist_ok=True)

        # YAML 설정 로드
        with open("logging_config.yml", "r") as file:
            config = yaml.safe_load(file)
            logging.config.dictConfig(config)
        logging.info("✅ 로깅 설정이 성공적으로 로드되었습니다.")
    except Exception as e:
        print(f"❌ 로깅 설정 로드 실패: {e}")
        # 기본 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


# 로깅 초기화
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 생명주기 관리
    시작 시 필요한 리소스를 초기화하고, 종료 시 모든 리소스를 정리합니다.
    """
    # ===== 애플리케이션 시작 시 실행 =====
    logger.info("✅ 애플리케이션 초기화를 시작합니다...")

    # 1. 업로드 디렉토리 생성
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"✅ 업로드 디렉토리 확인: {settings.UPLOAD_DIR}")

    # 2. 데이터베이스 연결 초기화
    try:
        logger.info("✅ 데이터베이스 마이그레이션을 시작합니다...")
        BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
        alembic_cfg = AlembicConfig(os.path.join(BASE_DIR, "alembic.ini"))
        alembic_command.upgrade(alembic_cfg, "head")
        logger.info("✅ 데이터베이스 마이그레이션이 완료되었습니다.")
    except Exception as e:
        logger.warning(f"⚠️ 데이터베이스 마이그레이션 진행 중 오류 발생: {str(e)}")
        logger.warning(
            "⚠️ 마이그레이션 오류는 테이블이 이미 존재해서 발생할 수 있으므로 애플리케이션이 계속 실행됩니다."
        )

    # 3. Redis 캐시 초기화
    redis_cache = None
    try:
        redis_config = RedisConfig()
        redis_cache = RedisCache(redis_config)
        await redis_cache.connect()
        logger.info("✅ Redis cache initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Redis cache initialization failed: {str(e)}")
        logger.warning("⚠️ Redis cache will be disabled, but application will continue")

    # Milvus 연결
    milvus_connected = await connect_to_milvus()
    if not milvus_connected:
        logger.warning(
            "⚠️ Milvus 연결에 실패했습니다. 벡터 검색 기능이 제한될 수 있습니다."
        )

    # 3. SSE 매니저 초기화 (싱글톤이므로 별도 초기화 불필요)
    logger.info("✅ SSE 매니저가 준비되었습니다.")

    # 4. RabbitMQ Consumer 시작
    rabbitmq_consumer = RabbitMQConsumer()
    await rabbitmq_consumer.start()
    logger.info("✅ RabbitMQ Consumer가 시작되었습니다.")

    # 6. Permission 서비스 초기화
    permission_service_instance = PermissionService(redis_cache=redis_cache, db=None)
    app.state.permission_service = permission_service_instance
    logger.info("✅ Permission service initialized successfully")

    logger.info("✅ 애플리케이션이 성공적으로 초기화되었습니다.")

    yield

    # ===== 애플리케이션 종료 시 실행 =====
    logger.info("⏳ 애플리케이션 종료 절차를 시작합니다...")

    # 1. RabbitMQ Consumer 종료
    await rabbitmq_consumer.stop()
    logger.info("✅ RabbitMQ Consumer가 종료되었습니다.")

    # 2. 데이터베이스 연결 종료
    # PostgreSQL 연결 풀 종료
    await async_engine.dispose()
    logger.info("✅ PostgreSQL 연결 풀이 정리되었습니다.")

    # Milvus 연결 종료
    try:
        connections.disconnect("default")
        logger.info("✅ Milvus 연결이 종료되었습니다.")
    except Exception as e:
        logger.error(f"❌ Milvus 연결 종료 중 오류 발생: {e}")

    logger.info("✅ 애플리케이션이 정상적으로 종료되었습니다.")


SWAGGER_HEADERS = {
    "title": "Indexing Service 통합 API",
    "version": "0.2.2",
    "description": (
        "문서를 업로드하고 AI로 분석하여 스마트한 검색이 가능한 통합 플랫폼입니다.\n"
        "문서 처리, 벡터 검색, 비용 계산, 실시간 알림 등의 기능을 제공합니다."
    ),
}

tags_metadata = [
    # ===== 일반 사용자 기능 =====
    {
        "name": "문서 관리",
        "description": "문서 업로드, 조회, 삭제 등 기본 문서 관리 기능",
    },
    {
        "name": "카테고리 관리",
        "description": "사용자 정의 카테고리 생성, 조회, 수정, 삭제",
    },
    {
        "name": "임베딩 스케줄",
        "description": "문서 임베딩 자동 스케줄링 및 관리",
    },
    {
        "name": "AI 문서 처리",
        "description": "문서 임베딩, 벡터화, AI 분석 처리",
    },
    {
        "name": "RAGAS 검색품질 평가",
        "description": "RAGAS 기반 검색 파이프라인 품질 평가 (실행, 조회, 삭제)",
    },
    {
        "name": "MCP 도구 관리",
        "description": "MCP 도구 개인 인스턴스 배포 및 관리",
    },
    {
        "name": "Graph RAG",
        "description": "엔티티/관계 관리 및 Dual-Level 그래프 검색",
    },
    {
        "name": "비용 계산",
        "description": "AI 처리 비용 계산 및 통계",
    },
    {
        "name": "SSE 진행 상태",
        "description": "Server-Sent Events를 통한 처리 진행 상태",
    },
    {
        "name": "사용자 활동 로그",
        "description": "사용자 활동 기록 및 조회",
    },
    # ===== 관리자 전용 기능 =====
    {
        "name": "파서 설정 관리 (관리자)",
        "description": "외부 문서 파서 설정 관리 (관리자 권한 필요)",
    },
    {
        "name": "관리자 (컬렉션 관리)",
        "description": (
            "**관리자 전용** Milvus 컬렉션 직접 관리 기능\n\n"
            "- 모든 컬렉션 목록/상세 조회\n"
            "- 컬렉션 데이터 페이지네이션 조회\n"
            "- 데이터 삭제 (미리보기 지원)\n\n"
            "⚠️ **주의**: Admin 권한(`global_role.name == 'ADMIN'`)이 필요합니다."
        ),
    },
    # ===== 기본 엔드포인트 =====
    {
        "name": "default",
        "description": "헬스체크 등 기본 엔드포인트",
    },
]

app = FastAPI(
    **SWAGGER_HEADERS,
    openapi_tags=tags_metadata,
    swagger_ui_parameters={"docExpansion": "list"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# 미들웨어 등록 (순서 중요: 먼저 등록된 것이 나중에 실행됨)
app.add_middleware(ActionLogMiddleware)  # 가장 나중에 실행 (응답 로깅)
# 인증/인가 미들웨어 (permission_service 주입)
permission_service = getattr(app.state, "permission_service", None)
app.add_middleware(AuthMiddleware, permission_service=permission_service)

# CORS 미들웨어 추가 (환경변수에서 설정)
cors_origins = [
    origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["*"],  # SSE 스트리밍을 위해 필요
)

logger.info("🚀 Auth middleware registered successfully!")
logger.info(f"🚀 CORS middleware registered with origins: {cors_origins}")


@app.get("/", tags=["default"])
def root():
    return {"message": "Indexing is running!"}


@app.get("/health", tags=["default"])
async def health_check():
    return {"status": "ok"}


# 라우터 등록
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="localhost",
        port=7000,
        reload=True,
        log_config="logging_config.yml",
    )
