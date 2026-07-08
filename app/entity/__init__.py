# PostgreSQL 테이블 entity (Alembic 마이그레이션용)
# 주의: 순환 임포트 방지를 위해 postgres 엔티티는 여기서 import하지 않음
# alembic/env.py에서 app.entity.postgres를 직접 import하여 모델 인식
