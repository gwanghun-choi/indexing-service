import logging
from pymilvus import Collection, utility
from pymilvus.exceptions import MilvusException

from app.config.database import (
    connect_to_milvus,
    get_meta_schema,
    get_vector_schema,
)
from app.config.database.async_milvus import (
    async_create_collection,
    async_create_index,
    async_list_collections,
    async_list_indexes,
    async_load_collection,
    get_milvus_client,
)

logger = logging.getLogger(__name__)

# ------------------------------------------
# Collection Cache
# ------------------------------------------
# 워커 프로세스 수명 동안 로드된 컬렉션 객체를 캐싱하여
# 매번 collection.load() 호출을 방지합니다.
# worker_max_tasks_per_child 설정으로 주기적으로 캐시가 초기화됩니다.
_collection_cache: dict = {}

# ------------------------------------------
# Milvus Index
# ------------------------------------------


async def create_index(collection: Collection) -> None:
    """
    기본 인덱스 생성

    컬렉션에 embedding_value 필드에 대한 인덱스를 생성합니다.
    이미 인덱스가 있는 경우에는 생성하지 않습니다.

    메타 컬렉션(문서 레벨): FLAT 인덱스 사용 (정확도 우선)
    벡터 컬렉션(청크 레벨): IVF_FLAT 인덱스 사용 (속도 최적화)

    Args:
        collection: 인덱스를 생성할 Milvus 컬렉션 객체

    Raises:
        MilvusException: 인덱스 생성 중 오류 발생 시 (중복 제외)
    """
    index_name = "embedding_value"

    # 이미 해당 인덱스가 있는지 확인
    if collection.has_index(index_name=index_name):
        logger.info(f"✅ 컬렉션 {collection.name}에 이미 인덱스가 있습니다.")
        return

    # 컬렉션 타입에 따라 인덱스 타입 선택
    is_meta_collection = "_meta" in collection.name

    if is_meta_collection:
        index_params = {
            "index_type": "FLAT",
            "metric_type": "COSINE",
        }
        logger.debug(f"📋 메타 컬렉션 '{collection.name}': FLAT 인덱스 사용")
    else:
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        }
        logger.debug(f"📦 벡터 컬렉션 '{collection.name}': IVF_FLAT 인덱스 사용")

    try:
        collection.create_index(
            field_name="embedding_value",
            index_params=index_params,
            index_name=index_name,
        )
        logger.info(f"✅ 컬렉션 {collection.name}에 인덱스가 생성되었습니다.")
    except MilvusException as e:
        # race condition: 다른 워커가 먼저 인덱스를 생성한 경우 무시
        if "already" in str(e).lower() or "exist" in str(e).lower():
            logger.info(f"✅ 컬렉션 {collection.name}에 이미 인덱스가 있습니다.")
            return
        logger.error(f"❌ 컬렉션 '{collection.name}' 인덱스 생성 오류: {e}")
        raise


# ------------------------------------------
# Milvus Connection
# ------------------------------------------


async def ensure_collection_loaded(collection_name: str, collection_type: str) -> None:
    """
    컬렉션이 존재하고 로드된 상태인지 확인 (MilvusClient + asyncio.to_thread용)

    MilvusClient와 함께 사용하기 위한 유틸리티 함수입니다.
    컬렉션이 없으면 생성하고, 인덱스가 없으면 인덱스를 생성합니다.

    Args:
        collection_name: 컬렉션 이름
        collection_type: 'meta' 또는 'vector'

    Raises:
        ValueError: 유효하지 않은 collection_type이 제공된 경우
    """
    # Fail Fast: collection_type 유효성 검사
    if collection_type not in ("meta", "vector"):
        raise ValueError("collection_type은 'meta' 또는 'vector'만 가능합니다.")

    # 1. 컬렉션 존재 확인 (set 변환: O(1) 멤버십 체크)
    collections = set(await async_list_collections())
    if collection_name not in collections:
        # 스키마 선택 (이미 검증됨)
        schema = get_meta_schema() if collection_type == "meta" else get_vector_schema()

        await async_create_collection(
            collection_name=collection_name,
            schema=schema,
        )
        logger.info(f"✅ 컬렉션 '{collection_name}' 생성 완료 (MilvusClient)")

    # 2. 인덱스 존재 확인 (컬렉션 존재 여부와 독립적으로 확인)
    indexes = await async_list_indexes(collection_name)
    if not indexes:
        await _create_index_async(collection_name, collection_type)

    # 3. 컬렉션 로드
    await async_load_collection(collection_name=collection_name)
    logger.debug(f"✅ 컬렉션 '{collection_name}' 로드 완료 (MilvusClient)")


async def _create_index_async(collection_name: str, collection_type: str) -> None:
    """
    MilvusClient + asyncio.to_thread용 인덱스 생성

    MilvusClient.create_index()는 IndexParams 객체를 요구합니다.
    prepare_index_params()로 IndexParams 객체를 생성하고,
    add_index()로 인덱스 설정을 추가합니다.

    Args:
        collection_name: 컬렉션 이름
        collection_type: 'meta' 또는 'vector'
    """
    is_meta_collection = collection_type == "meta"

    # MilvusClient.prepare_index_params()로 IndexParams 객체 생성
    client = get_milvus_client()
    index_params = client.prepare_index_params()

    if is_meta_collection:
        index_params.add_index(
            field_name="embedding_value",
            index_type="FLAT",
            metric_type="COSINE",
        )
    else:
        index_params.add_index(
            field_name="embedding_value",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128},
        )

    await async_create_index(
        collection_name=collection_name,
        index_params=index_params,
    )
    logger.info(f"✅ 컬렉션 '{collection_name}'에 인덱스 생성 완료 (MilvusClient)")


async def initialize_milvus(collection_name: str, collection_type: str) -> Collection:
    """
    Milvus 컬렉션 초기화

    캐시된 컬렉션이 있으면 재사용하고, 없으면 새로 로드 후 캐시에 저장합니다.
    이를 통해 매번 collection.load() 호출을 방지하여 성능을 개선합니다.

    Args:
        collection_name: 컬렉션 이름
        collection_type: 'meta' 또는 'vector'

    Returns:
        Collection: 초기화된 Milvus 컬렉션 객체

    Raises:
        ValueError: 유효하지 않은 collection_type이 제공된 경우
    """
    # 캐시에서 컬렉션 확인
    if collection_name in _collection_cache:
        cached_collection = _collection_cache[collection_name]
        # Milvus 서버에서 실제 로드 상태 확인
        # (서버가 메모리 관리를 위해 컬렉션을 release 했을 수 있음)
        try:
            await connect_to_milvus()  # 연결 보장
            load_state = utility.load_state(collection_name)
            # pymilvus 버전에 따라 LoadState가 문자열 또는 enum으로 반환됨
            if str(load_state).lower() in ("loaded", "loadstate.loaded"):
                logger.debug(f"✅ 캐시에서 컬렉션 '{collection_name}' 반환 (로드됨)")
                return cached_collection
            else:
                # 컬렉션이 언로드된 경우 다시 로드
                logger.debug(f"⚠️ 캐시된 컬렉션 '{collection_name}'이 언로드됨 (state={load_state}), 다시 로드")
                cached_collection.load()
                logger.debug(f"✅ 컬렉션 '{collection_name}' 다시 로드 완료")
                return cached_collection
        except MilvusException as e:
            # 로드 상태 확인/로드 실패 시 캐시에서 제거하고 새로 생성
            logger.warning(f"⚠️ 컬렉션 '{collection_name}' 로드 상태 확인 실패: {e}, 캐시 무효화")
            del _collection_cache[collection_name]

    # 우선 Milvus에 연결
    await connect_to_milvus()
    logger.debug("✅ Milvus 연결 시도 중...")

    # 컬렉션 타입별 스키마 선택
    if collection_type == "meta":
        schema = get_meta_schema()
    elif collection_type == "vector":
        schema = get_vector_schema()
    else:
        raise ValueError("❌ collection_type은 'meta' 또는 'vector'만 가능합니다.")

    # 컬렉션 생성
    if not utility.has_collection(collection_name):
        collection = Collection(name=collection_name, schema=schema)
        logger.debug(f"✅ 컬렉션 '{collection_name}' 생성 성공")
    else:
        collection = Collection(name=collection_name)
        logger.debug(f"✅ 컬렉션 '{collection_name}'이 이미 존재함")

    # 인덱스 생성 (index_name 명시로 중복 확인)
    if not collection.has_index(index_name="embedding_value"):
        logger.debug(f"✅ 컬렉션 '{collection_name}'에 인덱스 생성 시작")
        await create_index(collection)

    collection.load()
    logger.debug(f"✅ 컬렉션 '{collection_name}' 메모리에 로드됨")

    # 캐시에 저장
    _collection_cache[collection_name] = collection
    logger.debug(f"✅ 컬렉션 '{collection_name}' 캐시에 저장됨")

    return collection


# ------------------------------------------
# PostgreSQL Connection (Async SQLAlchemy)
# ------------------------------------------

# get_async_db_context는 app/config/database/session.py에서 import 되어 있음
