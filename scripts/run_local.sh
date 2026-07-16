#!/bin/bash
# =============================================================================
# 로컬 개발 서버 실행 스크립트
# .env 값을 기본으로 사용하되, 인프라 접속 정보만 로컬용으로 오버라이드
#
# 원격 인프라에 붙으려면 INFRA_HOST를 지정하세요.
#   INFRA_HOST=my-dev-server ./scripts/run_local.sh
# 개별 서비스만 다른 호스트에 있으면 해당 변수를 직접 지정하면 됩니다.
#   POSTGRES_HOST=db.internal INFRA_HOST=my-dev-server ./scripts/run_local.sh
# =============================================================================

# 인프라 호스트 (미지정 시 localhost)
: "${INFRA_HOST:=localhost}"

# 애플리케이션 설정
export APP_ENV="dev"
export SKIP_AUTH="true"

# 데이터베이스
export POSTGRES_HOST="${POSTGRES_HOST:-$INFRA_HOST}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export MILVUS_HOST="${MILVUS_HOST:-$INFRA_HOST}"
export MILVUS_PORT="${MILVUS_PORT:-19530}"
export OPENSEARCH_HOST="${OPENSEARCH_HOST:-$INFRA_HOST}"
export OPENSEARCH_PORT="${OPENSEARCH_PORT:-19200}"

# Redis
export REDIS_PORT="${REDIS_PORT:-6379}"
export REDIS_URL="${REDIS_URL:-redis://$INFRA_HOST:$REDIS_PORT/0}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-$REDIS_URL}"

# RabbitMQ (자격증명은 환경변수로 주입)
export RABBITMQ_PORT="${RABBITMQ_PORT:-5672}"
export RABBITMQ_USER="${RABBITMQ_USER:-guest}"
export RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-guest}"
export RABBITMQ_URL="${RABBITMQ_URL:-amqp://$RABBITMQ_USER:$RABBITMQ_PASSWORD@$INFRA_HOST:$RABBITMQ_PORT/}"

# Cloud Storage
export CLOUD_STORAGE_HOST="${CLOUD_STORAGE_HOST:-$INFRA_HOST}"

# MCP Tools / Reranker
export MCP_TOOLS_BASE_URL="${MCP_TOOLS_BASE_URL:-http://$INFRA_HOST:8007}"
export RERANKER_SERVICE_URL="${RERANKER_SERVICE_URL:-http://$INFRA_HOST:8009}"

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
