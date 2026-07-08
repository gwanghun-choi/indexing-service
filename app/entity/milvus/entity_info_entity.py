"""
Entity 컬렉션 스키마 (Milvus)

엔티티별 개별 저장 + 벡터 임베딩
"""

from pymilvus import FieldSchema, DataType


# Entity 컬렉션 필드 스키마
entity_fields = [
    FieldSchema(
        name="id",
        dtype=DataType.INT64,
        is_primary=True,
        auto_id=True,
        description="고유 식별자",
    ),
    FieldSchema(
        name="entity_name",
        dtype=DataType.VARCHAR,
        max_length=255,
        description="엔티티 이름 (김철수, 개발팀, ...)",
    ),
    FieldSchema(
        name="entity_type",
        dtype=DataType.VARCHAR,
        max_length=50,
        description="엔티티 타입 (person, organization, ...)",
    ),
    FieldSchema(
        name="source_hashes",
        dtype=DataType.ARRAY,
        element_type=DataType.VARCHAR,
        max_capacity=1000,
        max_length=64,
        description="이 엔티티가 등장한 문서들의 hash_sha256 배열",
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
        description="엔티티를 생성한 사용자 ID",
    ),
    FieldSchema(
        name="embedding_value",
        dtype=DataType.FLOAT_VECTOR,
        dim=1536,
        description="엔티티명 벡터 임베딩",
    ),
]
