FROM python:3.12-slim

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 시스템 패키지 설치 (최소화)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 설치 (캐시 레이어 활용)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 애플리케이션 코드 복사
COPY . .

# 포트 설정
EXPOSE 8002

# 애플리케이션 실행 (Celery Worker + FastAPI)
CMD ["sh", "-c", "uv run alembic upgrade head && uv run celery -A app.worker.celery worker --loglevel=info --concurrency=5 & uv run uvicorn app.main:app --host 0.0.0.0 --port 8002"]