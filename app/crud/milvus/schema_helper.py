"""스키마 헬퍼 함수

db_type에 따른 output_fields 목록을 반환하는 유틸리티 함수를 제공합니다.
AsyncMilvusClient는 collection.schema.fields에 접근할 수 없으므로
이 헬퍼를 통해 필드 목록을 가져옵니다.
"""
from typing import List

from app.entity.milvus.meta_info_entity import meta_fields
from app.entity.milvus.embedding_info_entity import vector_fileds


def get_output_fields(db_type: str, exclude_embedding: bool = True) -> List[str]:
    """
    db_type에 따른 output_fields 목록 반환

    Args:
        db_type: 데이터베이스 타입 ("meta" 또는 "vector")
        exclude_embedding: embedding_value 필드 제외 여부 (기본값: True)

    Returns:
        List[str]: 출력 필드 이름 목록
    """
    fields = meta_fields if db_type == "meta" else vector_fileds
    field_names = [f.name for f in fields]

    if exclude_embedding:
        field_names = [f for f in field_names if f != "embedding_value"]

    return field_names


def get_all_field_names(db_type: str) -> List[str]:
    """
    db_type에 따른 모든 필드 이름 목록 반환 (embedding 포함)

    Args:
        db_type: 데이터베이스 타입 ("meta" 또는 "vector")

    Returns:
        List[str]: 모든 필드 이름 목록
    """
    return get_output_fields(db_type, exclude_embedding=False)
