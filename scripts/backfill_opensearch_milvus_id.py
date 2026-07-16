"""OpenSearch 기존 문서에 milvus_id(Milvus PK) 필드를 backfill하는 스크립트

Milvus vector 컬렉션에서 id, hash_sha256, chunk_index를 조회한 뒤,
OpenSearch 문서를 partial update하여 milvus_id를 추가합니다.

접속 정보는 .env(MILVUS_HOST/PORT, OPENSEARCH_HOST/PORT)를 따릅니다.
.env 값이 Docker 내부 DNS 이름이면 로컬 실행 시 접속할 수 없으므로,
아래처럼 대상 호스트를 함께 지정하세요.

사용법:
    uv run python scripts/backfill_opensearch_milvus_id.py
    uv run python scripts/backfill_opensearch_milvus_id.py --dry-run
    MILVUS_HOST=localhost OPENSEARCH_HOST=localhost \
        uv run python scripts/backfill_opensearch_milvus_id.py --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.database.async_milvus import (
    async_list_collections,
    async_query,
)  # noqa: E402
from app.config.opensearch_config import get_index_name  # noqa: E402
from app.service.opensearch_bm25_service import create_opensearch_client  # noqa: E402
from app.utils.initialization import ensure_collection_loaded  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 500
MILVUS_MAX_OFFSET = 16384


async def fetch_milvus_chunks(collection_name: str) -> List[Dict]:
    """Milvus vector 컬렉션에서 id, hash_sha256, chunk_index를 페이징 조회"""
    await ensure_collection_loaded(collection_name, "vector")

    all_results: List[Dict] = []
    offset = 0

    while offset < MILVUS_MAX_OFFSET:
        results = await async_query(
            collection_name=collection_name,
            filter="id >= 0",
            output_fields=["id", "hash_sha256", "chunk_index"],
            limit=BATCH_SIZE,
            offset=offset,
            consistency_level="Strong",
        )

        if not results:
            break

        all_results.extend(results)
        logger.info(f"  {collection_name}: {len(all_results)}건 조회 (offset={offset})")

        if len(results) < BATCH_SIZE:
            break

        offset += BATCH_SIZE

    return all_results


def build_bulk_update_actions(index_name: str, chunks: List[Dict]) -> List[Dict]:
    """OpenSearch bulk partial update 액션 생성"""
    actions = []
    for chunk in chunks:
        doc_id = f"{chunk['hash_sha256']}_{chunk['chunk_index']}"
        actions.append({"update": {"_index": index_name, "_id": doc_id}})
        actions.append({"doc": {"milvus_id": chunk["id"]}})
    return actions


def execute_bulk_update(
    os_client, index_name: str, chunks: List[Dict], dry_run: bool
) -> Tuple[int, int]:
    """OpenSearch bulk update 실행"""
    if not chunks:
        return 0, 0

    if not os_client.indices.exists(index=index_name):
        logger.warning(f"  인덱스 {index_name} 없음 — 건너뜀")
        return 0, 0

    actions = build_bulk_update_actions(index_name, chunks)

    if dry_run:
        logger.info(f"  [DRY-RUN] {index_name}: {len(chunks)}건 업데이트 예정")
        return len(chunks), 0

    response = os_client.bulk(body=actions, request_timeout=120)

    success = 0
    failed = 0
    for item in response["items"]:
        if item["update"].get("error"):
            failed += 1
        else:
            success += 1

    return success, failed


def ensure_milvus_id_mapping(os_client, index_name: str) -> None:
    """기존 인덱스에 milvus_id 매핑이 없으면 추가"""
    if not os_client.indices.exists(index=index_name):
        return

    mapping = os_client.indices.get_mapping(index=index_name)
    properties = mapping[index_name]["mappings"].get("properties", {})

    if "milvus_id" not in properties:
        os_client.indices.put_mapping(
            index=index_name,
            body={"properties": {"milvus_id": {"type": "long"}}},
        )
        logger.info(f"  {index_name}: milvus_id 매핑 추가 완료")


async def backfill(dry_run: bool) -> None:
    """전체 backfill 실행"""
    collections = await async_list_collections()
    vector_collections = sorted([c for c in collections if c.endswith("_vector")])

    if not vector_collections:
        logger.info("vector 컬렉션이 없습니다.")
        return

    logger.info(f"대상 컬렉션: {len(vector_collections)}개")

    os_client = create_opensearch_client()
    total_success = 0
    total_failed = 0

    try:
        for collection_name in vector_collections:
            # TB_{group_id}_vector → group_id 추출
            group_id = int(collection_name.split("_")[1])
            index_name = get_index_name(group_id)

            logger.info(f"[{collection_name}] → {index_name}")

            # 기존 인덱스에 milvus_id 매핑 추가
            if not dry_run:
                ensure_milvus_id_mapping(os_client, index_name)

            chunks = await fetch_milvus_chunks(collection_name)
            if not chunks:
                logger.info("  청크 없음 — 건너뜀")
                continue

            # 배치 단위로 bulk update
            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i : i + BATCH_SIZE]
                success, failed = execute_bulk_update(
                    os_client, index_name, batch, dry_run
                )
                total_success += success
                total_failed += failed

            logger.info(f"  완료: {len(chunks)}건 처리")

    finally:
        os_client.close()

    logger.info(f"전체 완료: success={total_success}, failed={total_failed}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OpenSearch 기존 문서에 milvus_id 필드 backfill"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 업데이트 없이 대상 건수만 확인",
    )
    args = parser.parse_args()

    asyncio.run(backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
