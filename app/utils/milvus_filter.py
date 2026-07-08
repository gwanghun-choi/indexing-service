"""Milvus 필터 표현식 유틸리티"""


def escape_milvus_value(value: str) -> str:
    """Milvus == 연산자용 작은따옴표 escape

    Args:
        value: escape 처리할 문자열

    Returns:
        str: 작은따옴표가 escape 처리된 문자열
    """
    return value.replace("'", r"\'")


def escape_milvus_like(value: str) -> str:
    """Milvus like 연산자용 특수문자 escape

    Args:
        value: escape 처리할 문자열

    Returns:
        str: escape 처리된 문자열
    """
    return value.replace("'", r"\'").replace("%", r"\%").replace("_", r"\_")
