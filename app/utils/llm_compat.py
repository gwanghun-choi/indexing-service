"""LLM 모델 호환성 유틸리티"""


def needs_max_completion_tokens(model_name: str) -> bool:
    """gpt-5.x, o-series 등 max_completion_tokens이 필요한 모델인지 판별

    OpenAI 신규 모델(gpt-5.x, o1, o3 등)은 max_tokens 대신
    max_completion_tokens 파라미터를 사용합니다.

    Args:
        model_name: LLM 모델명 (예: "gpt-5.4-mini", "o3-mini")

    Returns:
        True이면 max_completion_tokens 사용, False이면 max_tokens 사용
    """
    model_lower = model_name.lower()

    # o-series (o1, o3, o4-mini 등)
    if len(model_lower) >= 2 and model_lower[0] == "o" and model_lower[1] in "123456789":
        if len(model_lower) == 2 or model_lower[2] in ("-", "_"):
            return True

    # gpt-5.x 이상 (gpt-5, gpt-5.4-mini 등)
    if model_lower.startswith("gpt-"):
        version_str = model_lower[4:].split("-")[0].split("_")[0]
        try:
            version = float(version_str)
            if version >= 5:
                return True
        except ValueError:
            pass

    return False
