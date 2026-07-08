"""
환경 설정 관리
Pydantic의 BaseSettings를 사용하여 환경 변수에서 설정 로드
"""

import os
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env 파일에서 환경 변수 로드
load_dotenv()


class Settings(BaseSettings):
    """
    애플리케이션 환경 설정 클래스
    환경 변수에서 로드하며, 각 변수에 대한 형식과 기본값을 정의합니다.
    """

    # =============================================================================
    # 애플리케이션 기본 설정
    # =============================================================================
    APP_NAME: str = os.getenv("APP_NAME")  # 애플리케이션 이름
    APP_PORT: str = os.getenv("APP_PORT")  # 애플리케이션 포트
    APP_ENV: str = os.getenv("APP_ENV")  # 환경 설정 (dev/prd)
    DEBUG: bool = APP_ENV == "dev"  # 디버그 모드 (개발환경에서만 활성화)
    _ALLOWED_URLS: Optional[List[str]] = None  # CORS 허용 URL (내부 사용)

    # CORS 설정
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS")  # 허용할 origin 목록 (콤마로 구분)

    # =============================================================================
    # 데이터베이스 설정
    # =============================================================================

    # PostgreSQL 메인 데이터베이스
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST")  # PostgreSQL 호스트
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT"))  # PostgreSQL 포트
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")  # PostgreSQL 사용자명
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")  # PostgreSQL 비밀번호
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")  # PostgreSQL 데이터베이스명

    # PostgreSQL 연결 URI (자동 생성)
    POSTGRES_URI: str = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    ASYNC_POSTGRES_URI: str = (
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )

    # Milvus 벡터 데이터베이스
    MILVUS_HOST: str = os.getenv("MILVUS_HOST")  # Milvus 호스트
    MILVUS_PORT: str = os.getenv("MILVUS_PORT")  # Milvus 포트

    # OpenSearch BM25 검색
    OPENSEARCH_HOST: str = os.getenv("OPENSEARCH_HOST")  # OpenSearch 호스트
    OPENSEARCH_PORT: int = int(os.getenv("OPENSEARCH_PORT"))  # OpenSearch 포트

    # Redis 캐시 및 큐
    REDIS_URL: str = os.getenv("REDIS_URL")  # Redis 연결 URL
    REDIS_DEFAULT_TIMEOUT: str = os.getenv(
        "REDIS_DEFAULT_TIMEOUT"
    )  # Redis 기본 타임아웃
    REDIS_USER: str = os.getenv("REDIS_USER")  # Redis 사용자명
    REDIS_PW: str = os.getenv("REDIS_PW")  # Redis 비밀번호
    REDIS_QUEUE_ROUTER_URL: str = os.getenv(
        "REDIS_QUEUE_ROUTER_URL"
    )  # Redis 큐 라우터 URL
    REDIS_QUEUE_NAME: str = os.getenv("REDIS_QUEUE_NAME")  # Redis 큐 이름
    REDIS_QUEUE_USE: bool = (
        os.getenv("REDIS_QUEUE_USE").lower() == "true"
    )  # Redis 큐 사용 여부

    # =============================================================================
    # 메시지 큐 설정 (Celery with Redis)
    # =============================================================================
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL")  # Celery 브로커 URL

    # RabbitMQ 설정
    RABBITMQ_URL: str = os.getenv("RABBITMQ_URL")
    RABBITMQ_EXCHANGE: str = os.getenv("RABBITMQ_EXCHANGE")
    RABBITMQ_QUEUE: str = os.getenv("RABBITMQ_QUEUE")
    RABBITMQ_ROUTING_KEY: str = os.getenv("RABBITMQ_ROUTING_KEY")

    # =============================================================================
    # 임베딩 모델 설정
    # =============================================================================
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL")  # 기본 임베딩 모델
    NCP_API_KEY: str = os.getenv("NCP_API_KEY")  # NCP API 키

    # Naver Cloud 임베딩 API (키 1)
    EMB_API_BASE: str = os.getenv("EMB_API_BASE")
    EMB_CLOVASTUDIO_API_KEY: str = os.getenv("EMB_CLOVASTUDIO_API_KEY")
    EMB_APIGW_API_KEY: str = os.getenv("EMB_APIGW_API_KEY")
    EMB_APP_ID: str = os.getenv("EMB_APP_ID")

    # Naver Cloud 임베딩 API (키 2)
    EMB_API_BASE_2: str = os.getenv("EMB_API_BASE_2")
    EMB_CLOVASTUDIO_API_KEY_2: str = os.getenv("EMB_CLOVASTUDIO_API_KEY_2")
    EMB_APIGW_API_KEY_2: str = os.getenv("EMB_APIGW_API_KEY_2")
    EMB_APP_ID_2: str = os.getenv("EMB_APP_ID_2")

    # Naver Cloud 임베딩 API (키 3)
    EMB_API_BASE_3: str = os.getenv("EMB_API_BASE_3")
    EMB_CLOVASTUDIO_API_KEY_3: str = os.getenv("EMB_CLOVASTUDIO_API_KEY_3")
    EMB_APIGW_API_KEY_3: str = os.getenv("EMB_APIGW_API_KEY_3")
    EMB_APP_ID_3: str = os.getenv("EMB_APP_ID_3")

    # HuggingFace 임베딩 API
    HUGGINGFACE_API_TOKEN: str = os.getenv("HUGGINGFACE_API_TOKEN")

    # Mistral 임베딩 API
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY")

    # Cohere 임베딩 API
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY")

    # =============================================================================
    # 채팅 완료 모델 설정
    # =============================================================================

    # Naver Cloud HyperCLOVA X (키 1)
    HCX_API_BASE: str = os.getenv("HCX_API_BASE")
    HCX_CLOVASTUDIO_API_KEY: str = os.getenv("HCX_CLOVASTUDIO_API_KEY")
    HCX_APIGW_API_KEY: str = os.getenv("HCX_APIGW_API_KEY")
    HCX_MAX_OUTPUT_TOKENS: str = os.getenv("HCX_MAX_OUTPUT_TOKENS")

    # Naver Cloud HyperCLOVA X (키 2)
    HCX_API_BASE_2: str = os.getenv("HCX_API_BASE_2")
    HCX_CLOVASTUDIO_API_KEY_2: str = os.getenv("HCX_CLOVASTUDIO_API_KEY_2")
    HCX_APIGW_API_KEY_2: str = os.getenv("HCX_APIGW_API_KEY_2")
    HCX_MAX_OUTPUT_TOKENS_2: str = os.getenv("HCX_MAX_OUTPUT_TOKENS_2")

    # Naver Cloud HyperCLOVA X (키 3)
    HCX_API_BASE_3: str = os.getenv("HCX_API_BASE_3")
    HCX_CLOVASTUDIO_API_KEY_3: str = os.getenv("HCX_CLOVASTUDIO_API_KEY_3")
    HCX_APIGW_API_KEY_3: str = os.getenv("HCX_APIGW_API_KEY_3")
    HCX_MAX_OUTPUT_TOKENS_3: str = os.getenv("HCX_MAX_OUTPUT_TOKENS_3")

    # OpenAI API
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_API_KEY1: str = os.getenv("OPENAI_API_KEY1")
    OPENAI_API_KEY2: str = os.getenv("OPENAI_API_KEY2")

    # Cohere API
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY")

    # Anthropic API
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY")

    # Perplexity API
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY")

    # Google Cloud API
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # =============================================================================
    # 인증 및 보안 설정
    # =============================================================================
    SKIP_AUTH: bool = os.getenv("SKIP_AUTH").lower() == "true"  # 로컬 테스트용 인증 우회
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")  # JWT 서명 검증용 비밀키
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM")  # JWT 서명 알고리즘

    # 암호화 설정
    CRYPT_KEY: str = os.getenv("CRYPT_KEY")  # 암호화/복호화용 비밀키

    # =============================================================================
    # 파일 저장소 설정 (NCP Object Storage)
    # =============================================================================
    NCP_ACCESS_KEY: str = os.getenv("NCP_ACCESS_KEY")  # NCP 액세스 키
    NCP_SECRET_KEY: str = os.getenv("NCP_SECRET_KEY")  # NCP 시크릿 키
    NCP_ENDPOINT_URL: str = os.getenv("NCP_ENDPOINT_URL")  # NCP 엔드포인트 URL
    NCP_BUCKET_NAME: str = os.getenv("NCP_BUCKET_NAME")  # NCP S3 버킷명

    # =============================================================================
    # 클라우드 스토리지 설정
    # =============================================================================
    CLOUD_STORAGE_HOST: str = os.getenv(
        "CLOUD_STORAGE_HOST"
    )  # 클라우드 스토리지 호스트
    CLOUD_STORAGE_PORT: int = int(
        os.getenv("CLOUD_STORAGE_PORT")
    )  # 클라우드 스토리지 포트
    CLOUD_STORAGE_TIMEOUT: int = int(
        os.getenv("CLOUD_STORAGE_TIMEOUT")
    )  # API 타임아웃(초)
    CLOUD_STORAGE_CONTAINER_NAME: str = os.getenv(
        "CLOUD_STORAGE_CONTAINER_NAME"
    )  # 클라우드 스토리지 컨테이너 이름
    CLOUD_STORAGE_USER: str = os.getenv("CLOUD_STORAGE_USER")  # 유저 이름
    CLOUD_STORAGE_PW: str = os.getenv("CLOUD_STORAGE_PW")  # 비밀번호

    # =============================================================================
    # 파일 업로드 설정
    # =============================================================================
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR")  # 업로드 디렉토리
    MAX_UPLOAD_SIZE: int = int(
        os.getenv("MAX_UPLOAD_SIZE")
    )  # 최대 업로드 크기 (바이트)

    # =============================================================================
    # MCP Tools 설정
    # =============================================================================
    MCP_TOOLS_BASE_URL: str = os.getenv("MCP_TOOLS_BASE_URL")  # MCP Tools 서버 URL

    # =============================================================================
    # Reranker 서비스 설정
    # =============================================================================
    RERANKER_SERVICE_URL: str = os.getenv("RERANKER_SERVICE_URL")  # Reranker 서비스 URL

    # =============================================================================
    # 문서 파싱 서비스 설정
    # =============================================================================

    # LlamaCloud 문서 파싱 API
    LLAMACLOUD_API_KEY: str = os.getenv("LLAMACLOUD_API_KEY")

    # Naver Cloud OCR API
    OCR_APIGW_INVOKE_URL: str = os.getenv("OCR_APIGW_INVOKE_URL")
    OCR_APIGW_INVOKE_URL2: str = os.getenv("OCR_APIGW_INVOKE_URL2")
    OCR_SECRET_KEY: str = os.getenv("OCR_SECRET_KEY")

    # Naver Cloud OCR fallback 제한값 (이미지 PDF OCR 보수 처리용)
    OCR_MAX_PAGES: int = int(os.getenv("OCR_MAX_PAGES"))  # OCR 최대 페이지 수
    OCR_RENDER_DPI: int = int(os.getenv("OCR_RENDER_DPI"))  # PDF→이미지 렌더 DPI
    OCR_TIMEOUT_SECONDS: int = int(os.getenv("OCR_TIMEOUT_SECONDS"))  # OCR API 타임아웃(초)
    OCR_MAX_RETRIES: int = int(os.getenv("OCR_MAX_RETRIES"))  # OCR API 재시도 횟수(transient만)

    # RAGAS 평가 stale 정리(reaper) 임계값 (분) - 무한 로딩 방지
    RAGAS_PENDING_TIMEOUT_MINUTES: int = int(os.getenv("RAGAS_PENDING_TIMEOUT_MINUTES"))
    RAGAS_RUNNING_TIMEOUT_MINUTES: int = int(os.getenv("RAGAS_RUNNING_TIMEOUT_MINUTES"))

    # RAGAS generation 평가 - agent(/v1/invoke) 연동 설정
    AGENT_INVOKE_URL: str = os.getenv("AGENT_INVOKE_URL")  # agent /v1/invoke 전체 URL
    RAGAS_AGENT_SCENARIO_ID: int = int(os.getenv("RAGAS_AGENT_SCENARIO_ID"))  # 평가용 시나리오 ID
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT"))  # invoke 호출 타임아웃(초)
    RAGAS_AGENT_MAX_CONCURRENCY: int = int(os.getenv("RAGAS_AGENT_MAX_CONCURRENCY"))  # invoke 동시 호출 수

    # =============================================================================
    # 계산된 속성 (Computed Properties)
    # =============================================================================

    @computed_field
    @property
    def allowed_origins(self) -> List[str]:
        """CORS 허용 출처를 반환합니다."""
        if self._ALLOWED_URLS is None:
            allowed_urls = os.getenv("ALLOWED_URLS")
            return allowed_urls.split(",") if allowed_urls else ["*"]
        return self._ALLOWED_URLS

    @computed_field
    @property
    def allowed_methods(self) -> List[str]:
        """CORS 허용 메서드를 반환합니다."""
        return ["*"]

    @computed_field
    @property
    def allowed_headers(self) -> List[str]:
        """CORS 허용 헤더를 반환합니다."""
        return ["*"]

    @property
    def is_development(self) -> bool:
        """개발 환경 여부를 반환합니다."""
        return self.APP_ENV.lower() in ["dev", "development"]

    @property
    def is_production(self) -> bool:
        """프로덕션 환경 여부를 반환합니다."""
        return self.APP_ENV.lower() in ["prd", "production"]

    @property
    def cloud_storage_base_url(self) -> str:
        """클라우드 스토리지 기본 URL을 반환합니다."""
        return f"http://{self.CLOUD_STORAGE_HOST}:{self.CLOUD_STORAGE_PORT}"

    # =============================================================================
    # Pydantic 모델 설정
    # =============================================================================
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """
    설정 인스턴스의 캐시된 인스턴스를 반환합니다.
    """
    return Settings()


# 전역 설정 인스턴스 생성
settings = get_settings()
