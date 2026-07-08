"""
Relation 컬렉션 스키마 (Milvus)

관계 타입별 저장 + 벡터 임베딩 (High-level 키워드 매칭용)
"""

from pymilvus import FieldSchema, DataType


# Relation 컬렉션 필드 스키마
relation_fields = [
    FieldSchema(
        name="id",
        dtype=DataType.INT64,
        is_primary=True,
        auto_id=True,
        description="고유 식별자",
    ),
    FieldSchema(
        name="relation_type",
        dtype=DataType.VARCHAR,
        max_length=100,
        description="관계 타입 (담당함, 소속됨, ...)",
    ),
    FieldSchema(
        name="description",
        dtype=DataType.VARCHAR,
        max_length=500,
        description="관계 타입 설명",
    ),
    FieldSchema(
        name="synonyms",
        dtype=DataType.ARRAY,
        element_type=DataType.VARCHAR,
        max_capacity=20,
        max_length=50,
        description="동의어 배열 (맡다, 책임지다, ...)",
    ),
    FieldSchema(
        name="role_ids",
        dtype=DataType.ARRAY,
        element_type=DataType.INT64,
        max_capacity=100,
        description="접근 가능한 역할 ID 리스트",
    ),
    FieldSchema(
        name="user_id",
        dtype=DataType.INT64,
        description="관계 타입을 생성한 사용자 ID",
    ),
    FieldSchema(
        name="embedding_value",
        dtype=DataType.FLOAT_VECTOR,
        dim=1536,
        description="관계 설명 벡터 임베딩 (High-level 키워드 매칭용)",
    ),
]
