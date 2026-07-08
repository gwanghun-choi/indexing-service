from pymilvus import FieldSchema, DataType


# 필드스키마 정의
vector_fileds = [
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
        name="embedding_value",
        dtype=DataType.FLOAT_VECTOR,
        dim=1536,
        description="벡터 값",
    ),
    FieldSchema(
        name="filename",
        dtype=DataType.VARCHAR,
        max_length=255,
        description="지식 문서 이름",
    ),
    FieldSchema(
        name="parsed_text",
        dtype=DataType.VARCHAR,
        max_length=5000,
        description="파싱된 텍스트",
    ),
    FieldSchema(
        name="page_number",
        dtype=DataType.INT64,
        description="페이지 번호",
    ),
    FieldSchema(
        name="chunk_index",
        dtype=DataType.INT64,
        description="단락 번호",
    ),
    FieldSchema(
        name="token",
        dtype=DataType.INT64,
        description="추출된 텍스트의 토큰량",
    ),
    FieldSchema(
        name="cost",
        dtype=DataType.DOUBLE,
        description="텍스트 임베딩에 소모된 비용 (달러 단위)",
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
        name="role_ids",
        dtype=DataType.ARRAY,
        element_type=DataType.INT64,
        max_capacity=100,
        description="접근 가능한 역할 ID 리스트",
    ),
    FieldSchema(
        name="hash_sha256",
        dtype=DataType.VARCHAR,
        max_length=64,
        description="문서의 고유 해시값(sha256)",
    ),
    FieldSchema(
        name="date",
        dtype=DataType.INT64,
        description="날짜",
    ),
]
