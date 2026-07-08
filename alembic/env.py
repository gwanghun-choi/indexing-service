from sqlalchemy import pool, text
from sqlalchemy.engine import engine_from_config
from alembic import context
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# app.config.settings에서 Settings 클래스 가져오기
from app.config.settings import settings


# 데이터베이스 존재 확인 및 생성 함수 추가
def ensure_database_exists():
    """데이터베이스가 존재하는지 확인하고, 없으면 생성"""
    try:
        # PostgreSQL 서버에 연결 (postgres 데이터베이스 사용)
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database="postgres",
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        # 커서 생성
        cursor = conn.cursor()

        # 데이터베이스가 존재하는지 확인
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (settings.POSTGRES_DB,),
        )
        exists = cursor.fetchone()

        # 데이터베이스가 존재하지 않으면 생성
        if not exists:
            cursor.execute(f"CREATE DATABASE {settings.POSTGRES_DB}")

        # 연결 종료
        cursor.close()
        conn.close()

    except Exception:
        # 오류가 발생해도 계속 진행 (Alembic이 적절한 오류 메시지 출력)
        pass


# 데이터베이스 생성 시도
ensure_database_exists()

# Alembic Config 객체
config = context.config

# app.config.database에 정의된 Base 사용
from app.config.database import Base  # noqa: E402

# 모든 indexing 엔티티를 import하여 Alembic이 인식할 수 있도록 함
from app.entity.postgres import *  # noqa: E402,F403

# settings 객체에서 데이터베이스 URL 가져오기
DATABASE_URL_SYNC = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

# config에 데이터베이스 URL 설정
config.set_main_option("sqlalchemy.url", DATABASE_URL_SYNC)

# target metadata 설정
target_metadata = Base.metadata


# 스키마 필터링을 위한 함수
def include_object(object, name, type_, reflected, compare_to):
    # indexing 스키마에 속한 테이블만 포함
    if type_ == "table" and object.schema != "indexing":
        return False
    return True


def run_migrations_offline() -> None:
    """Offline 모드에서 마이그레이션 실행"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="idx_alembic_version",
    )

    with context.begin_transaction():
        # indexing 스키마 생성 (없는 경우)
        context.execute(text("CREATE SCHEMA IF NOT EXISTS indexing"))

        # 스키마 필터링 설정 추가
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            version_table="idx_alembic_version",
            version_table_schema="indexing",
            include_schemas=True,
            include_object=include_object,
        )
        context.run_migrations()


def run_migrations_online() -> None:
    """Online 모드에서 마이그레이션 실행"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        try:
            # AUTOCOMMIT 모드로 변경
            conn = connection.execution_options(isolation_level="AUTOCOMMIT")
            # 스키마 생성
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS indexing"))
        except Exception:
            # 에러가 발생해도 마이그레이션은 시도
            pass

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,
            version_table="idx_alembic_version",
            version_table_schema="indexing",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
