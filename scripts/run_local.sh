#!/bin/bash
# =============================================================================
# 로컬 개발 서버 실행 스크립트
# .env 값을 기본으로 사용하되, 인프라 접속 정보만 로컬용으로 오버라이드
# =============================================================================

# 애플리케이션 설정
export APP_ENV="dev"
export SKIP_AUTH="true"

# 데이터베이스 (서버 직접 연결)
export POSTGRES_HOST="211.188.60.43"
export POSTGRES_PORT=5432
export MILVUS_HOST="211.188.60.43"
export MILVUS_PORT=19530
export OPENSEARCH_HOST="211.188.60.43"
export OPENSEARCH_PORT=19200

# Redis
export REDIS_URL="redis://211.188.60.43:16379/0"
export CELERY_BROKER_URL="redis://211.188.60.43:16379/0"

# RabbitMQ
export RABBITMQ_URL="amqp://guest:guest@211.188.60.43:5672/"

# Cloud Storage
export CLOUD_STORAGE_HOST="211.188.60.43"

# MCP Tools / Reranker
export MCP_TOOLS_BASE_URL="http://211.188.60.43:8007"
export RERANKER_SERVICE_URL="http://211.188.60.43:8009"

# 종료 시 모든 자식 프로세스 함께 종료
cleanup() {
    echo "Stopping all processes..."
    pkill -P $$ 2>/dev/null
    wait 2>/dev/null
    echo "All processes stopped."
}
trap cleanup INT TERM

# Celery Beat 실행 (백그라운드)
uv run celery -A app.worker beat --loglevel=info &
BEAT_PID=$!

# Celery Worker 실행 (백그라운드)
uv run celery -A app.worker worker --loglevel=info &
WORKER_PID=$!

# FastAPI 실행 (포그라운드)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
