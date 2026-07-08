"""
OpenSearch BM25 인덱스 설정
Nori 분석기를 사용한 한국어 토큰화 지원
"""

# Standard Library
from typing import Any, Dict

# 인덱스 설정: Nori 분석기 구성
INDEX_SETTINGS: Dict[str, Any] = {
    "index": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "analysis": {
        "tokenizer": {
            "nori_user_dict": {
                "type": "nori_tokenizer",
                "decompound_mode": "mixed",
                "discard_punctuation": "true"
            }
        },
        "analyzer": {
            "korean_analyzer": {
                "type": "custom",
                "tokenizer": "nori_user_dict",
                "filter": [
                    "nori_readingform",
                    "nori_part_of_speech",
                    "lowercase"
                ]
            }
        },
        "filter": {
            "nori_part_of_speech": {
                "type": "nori_part_of_speech"
            }
        }
    }
}

# 필드 매핑 정의
INDEX_MAPPINGS: Dict[str, Any] = {
    "properties": {
        "page_content": {
            "type": "text",
            "analyzer": "korean_analyzer",
            "search_analyzer": "korean_analyzer"
        },
        "hash_sha256": {
            "type": "keyword"
        },
        "title": {
            "type": "text",
            "analyzer": "korean_analyzer",
            "fields": {
                "keyword": {"type": "keyword"}
            }
        },
        "filename": {
            "type": "keyword"
        },
        "page_number": {
            "type": "integer"
        },
        "chunk_index": {
            "type": "integer"
        },
        "category": {
            "type": "keyword"
        },
        "role_ids": {
            "type": "integer"
        },
        "expiration_date": {
            "type": "long"
        },
        "group_id": {
            "type": "integer"
        },
        "milvus_id": {
            "type": "long"
        },
        "created_at": {
            "type": "date"
        }
    }
}


def get_index_name(group_id: int) -> str:
    """그룹별 인덱스 이름 생성"""
    return f"bm25_{group_id}"


def get_index_body() -> Dict[str, Any]:
    """인덱스 생성용 설정 반환"""
    return {
        "settings": INDEX_SETTINGS,
        "mappings": INDEX_MAPPINGS
    }
