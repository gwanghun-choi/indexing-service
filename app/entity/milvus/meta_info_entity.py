from pymilvus import FieldSchema, DataType


# 필드스키마 정의
meta_fields = [
    FieldSchema(
        name="id",
        dtype=DataType.INT64,
        is_primary=True,
        auto_id=True,
        description="고유 식별자",
    ),
    FieldSchema(
        name="category",
        dtype=DataType.VARCHAR,
        max_length=100,
        description="문서 카테고리",
    ),
    FieldSchema(
        name="title",
        dtype=DataType.VARCHAR,
        max_length=255,
        description="제목",
    ),
    FieldSchema(
        name="filename",
        dtype=DataType.VARCHAR,
        max_length=255,
        description="파일 이름",
    ),
    FieldSchema(
        name="summary",
        dtype=DataType.VARCHAR,
        max_length=5000,
        description="문서 요약",
    ),
    FieldSchema(
        name="file_type",
        dtype=DataType.VARCHAR,
        max_length=30,
        description="파일 타입",
    ),
    FieldSchema(
        name="file_size",
        dtype=DataType.INT64,
        description="파일 크기",
    ),
    FieldSchema(
        name="status",
        dtype=DataType.VARCHAR,
        max_length=30,
        description="업로드 상태 정보",
    ),
    FieldSchema(
        name="role_ids",
        dtype=DataType.ARRAY,
        element_type=DataType.INT64,
        max_capacity=100,
        description="접근 가능한 역할 ID 리스트",
    ),
    FieldSchema(
        name="persona_id",
        dtype=DataType.INT64,
        description="페르소나 ID (역할 기반 청크 필터링에 사용)",
    ),
    FieldSchema(
        name="file_path",
        dtype=DataType.VARCHAR,
        max_length=500,
        description="파일 경로",
    ),
    FieldSchema(
        name="download_url",
        dtype=DataType.VARCHAR,
        max_length=1000,
        description="다운로드 URL",
    ),
    FieldSchema(
        name="chunk_count",
        dtype=DataType.INT64,
        description="문서 청크 개수",
    ),
    FieldSchema(
        name="token",
        dtype=DataType.INT64,
        description="지식 등록에 발생된 토큰량",
    ),
    FieldSchema(
        name="cost",
        dtype=DataType.DOUBLE,
        description="지식 등록에 소모된 비용 (달러 단위)",
    ),
    FieldSchema(
        name="summary_token",
        dtype=DataType.INT64,
        description="문서 요약 시 발생된 토큰량",
    ),
    FieldSchema(
        name="summary_cost",
        dtype=DataType.DOUBLE,
        description="문서 요약시 소모된 비용 (달러 단위)",
    ),
    FieldSchema(
        name="group_id",
        dtype=DataType.INT64,
        description="그룹 ID",
    ),
    FieldSchema(
        name="user_id",
        dtype=DataType.INT64,
        description="사용자 ID",
    ),
    FieldSchema(
        name="hash_sha256",
        dtype=DataType.VARCHAR,
        max_length=64,
        description="문서의 고유 해시값(sha256)",
    ),
    FieldSchema(
        name="start_date",
        dtype=DataType.INT64,
        description="작업 시작일",
    ),
    FieldSchema(
        name="end_date",
        dtype=DataType.INT64,
        description="작업 종료일",
    ),
    FieldSchema(
        name="expiration_date",
        dtype=DataType.INT64,
        description="문서 만료일",
    ),
    FieldSchema(
        name="embedding_value",
        dtype=DataType.FLOAT_VECTOR,
        dim=1536,
        description="문서 임베딩 값",
    ),
    # 참조 카운터 필드 추가 - 검색 시 문서가 반환된 횟수를 추적
    FieldSchema(
        name="ref_count",
        dtype=DataType.INT64,
        default_value=0,
        description="문서 참조 횟수",
    ),
    FieldSchema(
        name="anonymization_strategy",
        dtype=DataType.VARCHAR,
        max_length=50,
        nullable=True,
        description="PII 비식별화 전략 (none, masking, pseudonymization, generalization, 비활성화 시 NULL)",
    ),
    # 청킹 설정 (2개)
    FieldSchema(
        name="chunk_size",
        dtype=DataType.INT64,
        description="청크 크기 (예: 500)",
    ),
    FieldSchema(
        name="chunk_overlap",
        dtype=DataType.INT64,
        description="청크 오버랩 크기 (예: 50)",
    ),
    # PII 비식별화 설정 (2개)
    FieldSchema(
        name="enable_pii_anonymization",
        dtype=DataType.INT64,  # 0=비활성, 1=활성
        default_value=0,
        description="PII 비식별화 활성화 여부",
    ),
    FieldSchema(
        name="pii_types",
        dtype=DataType.VARCHAR,
        max_length=500,
        nullable=True,
        description="비식별화 대상 PII 유형 (쉼표 구분, 비활성화 시 NULL)",
    ),
    # 페르소나 필터링 결과 (2개)
    FieldSchema(
        name="original_chunk_count",
        dtype=DataType.INT64,
        description="필터링 전 청크 개수",
    ),
    FieldSchema(
        name="filtered_chunk_count",
        dtype=DataType.INT64,
        description="필터링 후 청크 개수 (실제 임베딩된 개수)",
    ),
    # 임베딩 소요 시간 (2개)
    FieldSchema(
        name="embedding_start_date",
        dtype=DataType.INT64,
        description="임베딩 시작 시간 (Unix timestamp)",
    ),
    FieldSchema(
        name="embedding_end_date",
        dtype=DataType.INT64,
        description="임베딩 종료 시간 (Unix timestamp)",
    ),
]
