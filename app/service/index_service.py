import logging
from typing import List, Dict, Any

from pymilvus import connections, Collection, utility

logger = logging.getLogger(__name__)


def update_index(input: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    인덱스 업데이트를 수행하는 서비스 함수

    Milvus 컬렉션의 벡터 검색 인덱스를 업데이트합니다.

    Args:
        input: 인덱스 파라미터를 포함하는 딕셔너리
            - index_type (str): 인덱스 타입 (예: 'IVF_FLAT', 'HNSW')
            - metric_type (str): 거리 측정 방식 (예: 'IP', 'L2')
            - params (Dict): 인덱스 파라미터 (index_type에 따라 다름)

    Returns:
        List[Dict[str, Any]]: 각 컬렉션의 업데이트 결과를 담은 딕셔너리 리스트
            - collection_name (str): 컬렉션 이름
            - status (str): 성공/실패 상태
            - error (str, optional): 실패 시 오류 메시지

    Raises:
        ConnectionError: Milvus 서버 연결 실패 시
    """
    logger.info("인덱스 업데이트 작업 시작 ✅")

    # Milvus 서버에 연결 및 컬렉션 목록 조회
    try:
        connections.connect(alias="default", host="standalone", port="19530")
        collection_names = utility.list_collections()
        logger.info(f"Milvus 서버 연결 성공: {len(collection_names)}개 컬렉션 발견 ✅")
    except Exception as e:
        logger.error(f"Milvus 서버 연결 실패: {e} ❌")
        raise ConnectionError(f"Milvus 서버 연결 실패: {e}") from e

    update_results = []

    # 필수 파라미터 확인
    required_params = ["index_type", "metric_type", "params"]
    for param in required_params:
        if param not in input:
            error_msg = f"필수 파라미터 '{param}'가 없습니다. ❌"
            logger.error(error_msg)
            return [{"status": "failed", "error": error_msg}]

    logger.info(
        f"인덱스 업데이트 시작: 타입={input['index_type']}, 메트릭={input['metric_type']} ✅"
    )

    # 각 컬렉션에 대해 인덱스 업데이트 수행
    for collection_name in collection_names:
        try:
            logger.debug(f"컬렉션 '{collection_name}' 처리 중...")
            collection = Collection(collection_name)
            collection.release()  # 컬렉션 메모리 해제
            logger.debug(f"컬렉션 '{collection_name}' 메모리 해제됨")

            collection.drop_index()  # 기존 인덱스 삭제
            logger.debug(f"컬렉션 '{collection_name}'의 기존 인덱스 삭제됨")

            # 새로운 인덱스 생성에 필요한 파라미터 설정
            index_params = {
                "index_type": input["index_type"],
                "metric_type": input["metric_type"],
                "params": input["params"],
            }
            logger.info(f"인덱스 파라미터: {index_params} ✅")
            collection.create_index(
                field_name="embedding_value",
                index_params=index_params,
            )
            logger.debug(f"컬렉션 '{collection_name}'에 인덱스 생성됨")

            collection.load()  # 컬렉션 메모리 로드
            logger.debug(f"컬렉션 '{collection_name}' 메모리에 로드됨")

            update_results.append(
                {
                    "collection_name": collection_name,
                    "status": "success",
                }
            )
            logger.info(
                f"컬렉션 '{collection_name}'의 인덱스 업데이트가 완료되었습니다. ✅"
            )
        except Exception as e:
            logger.error(f"컬렉션 '{collection_name}'의 인덱스 업데이트 실패: {e} ❌")
            update_results.append(
                {
                    "collection_name": collection_name,
                    "status": "failed",
                    "error": str(e),
                }
            )

    success_count = sum(1 for result in update_results if result["status"] == "success")
    failed_count = len(update_results) - success_count
    logger.info(
        f"인덱스 업데이트 작업 완료: 성공={success_count}, 실패={failed_count} ✅"
    )

    return update_results
