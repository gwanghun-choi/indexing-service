import gc
import os
import logging

logger = logging.getLogger(__name__)


def cleanup_params(params: dict) -> None:
    """
    파이프라인 완료 후 메모리 해제.

    Args:
        params: 파이프라인에서 사용된 딕셔너리
    """
    params.clear()
    gc.collect()
    logger.info("✅ 파이프라인 메모리 정리 완료")


def cleanup_temp_file(params: dict) -> None:
    """
    임시 파일을 안전하게 삭제합니다.

    Args:
        params: temp_file_path 키를 포함할 수 있는 딕셔너리
    """
    try:
        temp_file_path = params["temp_file_path"]
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"[pipeline] 🗑️ 임시 파일 삭제 완료: {temp_file_path}")
    except KeyError:
        pass  # temp_file_path 키가 없으면 무시
    except Exception as e:
        logger.warning(f"[pipeline] ⚠️ 임시 파일 삭제 실패: {e}")
