# Milvus 컬렉션 스키마
from app.entity.milvus.meta_info_entity import meta_fields
from app.entity.milvus.embedding_info_entity import vector_fileds
from app.entity.milvus.entity_info_entity import entity_fields
from app.entity.milvus.relation_info_entity import relation_fields

__all__ = [
    "meta_fields",
    "vector_fileds",
    "entity_fields",
    "relation_fields",
]
