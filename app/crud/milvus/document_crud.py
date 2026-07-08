import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from zoneinfo import ZoneInfo

from pymilvus import utility

from app.config.database.async_milvus import (
    async_query,
    async_query_iterate,
    async_insert,
    async_upsert,
    async_delete,
    async_list_collections,
)
from app.crud.milvus.schema_helper import get_output_fields, get_all_field_names
from app.dto.document_status import DocumentStatus
from app.utils.initialization import ensure_collection_loaded

logger = logging.getLogger(__name__)


def _build_vector_filter_expr(
    role_ids: List[int],
    category_option: Optional[str] = None,
    title_option: Optional[str] = None,
    hash_sha256_option: Optional[Any] = None,
    id_option: Optional[int] = None,
    page_number_option: Optional[int] = None,
    chunk_index_option: Optional[int] = None,
    keyword_option: Optional[str] = None,
) -> str:
    """vector 컬렉션용 필터 표현식 구성

    Args:
        role_ids: 접근 가능한 role_id 리스트
        category_option: 카테고리 필터
        title_option: 제목 필터
        hash_sha256_option: 해시 필터
        id_option: Milvus PK 필터
        page_number_option: 페이지 번호 필터
        chunk_index_option: 청크 인덱스 필터
        keyword_option: 텍스트 키워드 필터

    Returns:
        str: Milvus filter 표현식
    """
    role_filter = " || ".join(
        [f"array_contains(role_ids, {role_id})" for role_id in role_ids]
    )
    expr = f"({role_filter})"

    if id_option is not None:
        expr = f"{expr} and id == {id_option}"

    if page_number_option is not None:
        expr = f"{expr} and page_number == {page_number_option}"

    if chunk_index_option is not None:
        expr = f"{expr} and chunk_index == {chunk_index_option}"

    if keyword_option:
        from app.utils.milvus_filter import escape_milvus_like
        escaped = escape_milvus_like(keyword_option)
        expr = f"{expr} and parsed_text like '%{escaped}%'"

    if category_option:
        expr = f"{expr} and category like '%{category_option}%'"

    if title_option:
        expr = f"{expr} and title like '%{title_option.lower()}%'"

    if hash_sha256_option:
        if isinstance(hash_sha256_option, list):
            hash_list_str = ", ".join([f"'{h}'" for h in hash_sha256_option])
            expr = f"{expr} and hash_sha256 in [{hash_list_str}]"
        else:
            expr = f"{expr} and hash_sha256 == '{hash_sha256_option}'"

    return expr


# ------------------------------------------
# READ
# ------------------------------------------


async def count_documents(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    category_option: Optional[str] = None,
    title_option: Optional[str] = None,
    hash_sha256_option: Optional[Any] = None,
    persona_id_option: Optional[int] = None,
    filename_option: Optional[str] = None,
    status_option: Optional[str] = None,
) -> int:
    """
    데이터베이스에서 문서 개수 조회 (페이징용)

    select_documents와 동일한 필터 조건을 사용하여 전체 개수를 반환합니다.
    메모리 효율을 위해 output_fields=["id"]만 조회합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 접근 가능한 role_id 리스트
        category_option: 문서 카테고리 필터링 옵션
        title_option: 문서 제목 필터링 옵션
        hash_sha256_option: 해시 필터링 옵션 (단일 문자열 또는 리스트)
        persona_id_option: 페르소나 ID 필터링 옵션
        filename_option: 파일명 필터링 옵션
        status_option: 문서 상태 필터링 옵션 (uploading, registered, running, uploaded, failed, skipped, ocr_required)

    Returns:
        int: 조건에 맞는 문서 개수
    """
    collection_name = f"TB_{group_id}_meta"
    try:
        await ensure_collection_loaded(collection_name, "meta")

        # role_ids 배열 기반 권한 필터링
        role_filter = " || ".join(
            [f"array_contains(role_ids, {role_id})" for role_id in role_ids]
        )
        expr = f"({role_filter})"

        # 관리자가 아닌 경우 만료된 문서 필터링 추가
        if user_id != 1:
            current_time = int(datetime.now(ZoneInfo("Asia/Seoul")).timestamp())
            expiration_expr = f"expiration_date > {current_time}"
            expr = f"{expr} and {expiration_expr}"

        # 추가 필터링 조건 설정
        if category_option:
            category_expr = f"category like '%{category_option}%'"
            expr = f"{expr} and {category_expr}"

        if title_option:
            title_expr = f"title like '%{title_option.lower()}%'"
            expr = f"{expr} and {title_expr}"

        if hash_sha256_option:
            if isinstance(hash_sha256_option, list):
                hash_list_str = ", ".join([f"'{h}'" for h in hash_sha256_option])
                hash_expr = f"hash_sha256 in [{hash_list_str}]"
            else:
                hash_expr = f"hash_sha256 == '{hash_sha256_option}'"
            expr = f"{expr} and {hash_expr}"

        if persona_id_option is not None:
            persona_expr = f"persona_id == {persona_id_option}"
            expr = f"{expr} and {persona_expr}"

        if filename_option:
            filename_expr = f"filename like '%{filename_option}%'"
            expr = f"{expr} and {filename_expr}"

        if status_option:
            status_expr = f"status == '{status_option}'"
            expr = f"{expr} and {status_expr}"

        # 개수 조회 (output_fields=["id"]만 사용하여 메모리 효율화)
        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=["id"],
            consistency_level="Strong"
        )

        count = len(results)
        logger.debug(f"✅ 문서 개수 조회 완료: {count}개")
        return count

    except Exception as e:
        logger.error(f"❌ 문서 개수 조회 중 오류 발생: {e}")
        raise e


async def count_vector_documents(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    category_option: Optional[str] = None,
    title_option: Optional[str] = None,
    hash_sha256_option: Optional[Any] = None,
    id_option: Optional[int] = None,
    page_number_option: Optional[int] = None,
    chunk_index_option: Optional[int] = None,
    keyword_option: Optional[str] = None,
) -> int:
    """
    벡터 컬렉션 문서 개수 조회 (페이징용)

    output_fields=["id"]만 조회하여 메모리 효율적으로 카운트합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 접근 가능한 role_id 리스트
        category_option: 카테고리 필터
        title_option: 제목 필터
        hash_sha256_option: 해시 필터
        id_option: Milvus PK 필터
        page_number_option: 페이지 번호 필터
        chunk_index_option: 청크 인덱스 필터
        keyword_option: 텍스트 키워드 필터

    Returns:
        int: 조건에 맞는 문서 개수
    """
    collection_name = f"TB_{group_id}_vector"
    try:
        await ensure_collection_loaded(collection_name, "vector")

        expr = _build_vector_filter_expr(
            role_ids=role_ids,
            category_option=category_option,
            title_option=title_option,
            hash_sha256_option=hash_sha256_option,
            id_option=id_option,
            page_number_option=page_number_option,
            chunk_index_option=chunk_index_option,
            keyword_option=keyword_option,
        )

        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=["id"],
            consistency_level="Strong",
        )
        count = len(results)
        logger.debug(f"✅ 벡터 문서 개수 조회 완료: {count}개")
        return count
    except Exception as e:
        logger.error(f"❌ 벡터 문서 개수 조회 중 오류 발생: {e}")
        raise e


async def get_vector_chunk_by_id(group_id: int, chunk_id: int) -> Optional[Dict[str, Any]]:
    """Milvus PK로 벡터 청크 단건 조회

    Args:
        group_id: 그룹 ID
        chunk_id: Milvus PK (id)

    Returns:
        Optional[Dict[str, Any]]: 청크 데이터 (없으면 None)
    """
    collection_name = f"TB_{group_id}_vector"
    try:
        await ensure_collection_loaded(collection_name, "vector")
        output_fields = get_output_fields("vector")
        results = await async_query(
            collection_name=collection_name,
            filter=f"id == {chunk_id}",
            output_fields=output_fields,
        )
        return results[0] if results else None
    except Exception as e:
        logger.error(f"❌ 벡터 청크 단건 조회 실패: chunk_id={chunk_id}, {e}")
        raise e


async def get_meta_doc_by_id(group_id: int, doc_id: int) -> Optional[Dict[str, Any]]:
    """Milvus PK로 메타 문서 단건 조회

    upsert에 필요한 embedding_value를 포함한 전체 필드를 반환합니다.

    Args:
        group_id: 그룹 ID
        doc_id: Milvus PK (id)

    Returns:
        Optional[Dict[str, Any]]: 메타 문서 데이터 (없으면 None)
    """
    collection_name = f"TB_{group_id}_meta"
    try:
        await ensure_collection_loaded(collection_name, "meta")
        output_fields = get_all_field_names("meta")
        results = await async_query(
            collection_name=collection_name,
            filter=f"id == {doc_id}",
            output_fields=output_fields,
        )
        return results[0] if results else None
    except Exception as e:
        logger.error(f"❌ 메타 문서 단건 조회 실패: doc_id={doc_id}, {e}")
        raise e


async def select_documents(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    db_type: str,
    category_option: Optional[str] = None,
    title_option: Optional[str] = None,
    hash_sha256_option: Optional[Any] = None,
    persona_id_option: Optional[int] = None,
    filename_option: Optional[str] = None,
    status_option: Optional[str] = None,
    id_option: Optional[int] = None,
    page_number_option: Optional[int] = None,
    chunk_index_option: Optional[int] = None,
    keyword_option: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    use_iterator: bool = False,
) -> List[Dict[str, Any]]:
    """
    데이터베이스에서 데이터 조회 (페이징 지원)

    사용자 role_id 기반 권한에 따라 데이터를 조회합니다.
    관리자가 아닌 사용자는 만료된 문서를 볼 수 없습니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 접근 가능한 role_id 리스트
        db_type: 데이터베이스 타입 (meta, vector)
        category_option: 문서 카테고리 필터링 옵션
        title_option: 문서 제목 필터링 옵션
        hash_sha256_option: 해시 필터링 옵션 (단일 문자열 또는 리스트)
        persona_id_option: 페르소나 ID 필터링 옵션
        filename_option: 파일명 필터링 옵션
        status_option: 문서 상태 필터링 옵션 (uploading, registered, running, uploaded, failed, skipped, ocr_required)
        limit: 조회할 최대 개수 (기본값: 20, 최대: 50)
        offset: 건너뛸 개수 (기본값: 0)

    Returns:
        List[Dict[str, Any]]: 쿼리 결과

    Raises:
        Exception: 데이터 조회 중 오류 발생 시

    Note:
        Milvus 제한: offset + limit < 16,384
    """
    collection_name = f"TB_{group_id}_{db_type}"
    try:
        # 컬렉션 준비
        await ensure_collection_loaded(collection_name, db_type)

        # output_fields 설정
        output_fields = get_output_fields(db_type)

        # db_type에 따른 조건부 필터링 설정
        expr = ""

        if db_type == "meta":
            # meta 컬렉션: role_ids 배열 기반 권한 필터링
            role_filter = " || ".join(
                [f"array_contains(role_ids, {role_id})" for role_id in role_ids]
            )
            expr = f"({role_filter})"

            logger.info(f"✅ Meta 컬렉션 Role 기반 필터링 조건: {expr}")

            # 관리자가 아닌 경우 만료된 문서 필터링 추가
            if user_id != 1:  # 관리자가 아닌 경우
                current_time = int(datetime.now(ZoneInfo("Asia/Seoul")).timestamp())
                # 만료되지 않은 문서만 조회: 현재 시간보다 큰 경우
                expiration_expr = f"expiration_date > {current_time}"
                expr = f"{expr} and {expiration_expr}" if expr else expiration_expr

        elif db_type == "vector":
            expr = _build_vector_filter_expr(
                role_ids=role_ids,
                category_option=category_option,
                title_option=title_option,
                hash_sha256_option=hash_sha256_option,
                id_option=id_option,
                page_number_option=page_number_option,
                chunk_index_option=chunk_index_option,
                keyword_option=keyword_option,
            )
            logger.info(f"✅ Vector 컬렉션 필터링 조건: {expr}")

        # 추가 필터링 조건 설정 (meta 전용 — vector는 _build_vector_filter_expr()에서 처리)
        if db_type != "vector":
            if category_option:
                category_expr = f"category like '%{category_option}%'"
                expr = f"{expr} and {category_expr}" if expr else category_expr

            if title_option:
                title_expr = f"title like '%{title_option.lower()}%'"
                expr = f"{expr} and {title_expr}" if expr else title_expr

            if hash_sha256_option:
                if isinstance(hash_sha256_option, list):
                    hash_list_str = ", ".join([f"'{h}'" for h in hash_sha256_option])
                    hash_expr = f"hash_sha256 in [{hash_list_str}]"
                else:
                    hash_expr = f"hash_sha256 == '{hash_sha256_option}'"
                expr = f"{expr} and {hash_expr}" if expr else hash_expr

        if persona_id_option is not None:
            persona_expr = f"persona_id == {persona_id_option}"
            expr = f"{expr} and {persona_expr}" if expr else persona_expr

        if filename_option:
            filename_expr = f"filename like '%{filename_option}%'"
            expr = f"{expr} and {filename_expr}" if expr else filename_expr

        if status_option:
            status_expr = f"status == '{status_option}'"
            expr = f"{expr} and {status_expr}" if expr else status_expr

        # 쿼리 실행 (consistency_level="Strong"으로 최신 데이터 보장)
        query_filter = expr if expr else "id >= 0"
        if use_iterator:
            # 전량 조회: query_iterator로 batch 순회 (응답 64MB / 행 16384 한도 우회)
            # 필드/필터/consistency는 기존 query와 동일 → 결과 집합 동일
            logger.info(f"✅ Milvus iterator 조회: filter={query_filter}")
            results = await async_query_iterate(
                collection_name=collection_name,
                filter=query_filter,
                output_fields=output_fields,
                batch_size=1000,
                consistency_level="Strong"
            )
        else:
            logger.info(f"✅ Milvus 쿼리 실행: filter={query_filter}, limit={limit}, offset={offset}")
            results = await async_query(
                collection_name=collection_name,
                filter=query_filter,
                output_fields=output_fields,
                limit=limit,
                offset=offset,
                consistency_level="Strong"
            )

        logger.debug(f"✅ 쿼리 결과: {len(results)}개 항목 조회됨")
        return results
    except Exception as e:
        logger.error(f"❌ 컬렉션 '{collection_name}'에서 데이터 조회 중 오류 발생: {e}")
        raise e


async def select_document_by_task(task_id: str) -> Optional[dict]:
    """
    태스크 ID를 기반으로 문서 메타데이터를 조회합니다.

    모든 메타 컬렉션에서 지정된 태스크 ID와 일치하는 문서를 검색합니다.

    Args:
        task_id: 조회할 태스크 ID

    Returns:
        Optional[Dict[str, Any]]: 문서 메타데이터 정보 (없으면 None)

    Raises:
        Exception: 로깅 후 None 반환
    """
    try:
        logger.info(f"✅ 태스크 ID로 문서 조회: {task_id}")

        # 모든 그룹의 meta 컬렉션 목록 가져오기
        collections = await async_list_collections()
        meta_collections = [coll for coll in collections if coll.endswith("_meta")]

        # output_fields 설정
        output_fields = get_output_fields("meta")

        # 모든 메타 컬렉션에서 태스크 ID로 검색
        for collection_name in meta_collections:
            await ensure_collection_loaded(collection_name, "meta")

            # task_id로 검색
            expr = f"task_id == '{task_id}'"
            results = await async_query(
                collection_name=collection_name,
                filter=expr,
                output_fields=output_fields
            )

            if results:
                logger.info(
                    f"태스크 ID {task_id}에 해당하는 문서를 찾았습니다: {collection_name}"
                )
                return results[0]  # 첫 번째 결과 반환

        # 모든 컬렉션을 검색해도 결과가 없는 경우
        logger.warning(f"⚠️ 태스크 ID {task_id}에 해당하는 문서를 찾을 수 없습니다.")
        return None

    except Exception as e:
        logger.error(f"❌ 태스크 ID로 문서 조회 중 오류 발생: {e}")
        return None


async def select_expiring_documents(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    days_before_expiration: int = 7,
) -> List[Dict[str, Any]]:
    """
    만료 임박 문서 조회

    지정된 기간 내에 만료될 예정인 문서들을 조회합니다.
    사용자 role_id 기반 권한에 따라 필터링합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 접근 가능한 role_id 리스트
        days_before_expiration: 만료 전 일수 (기본값: 7일)

    Returns:
        List[Dict[str, Any]]: 만료 임박 문서 목록

    Raises:
        Exception: 데이터 조회 중 오류 발생 시
    """
    collection_name = f"TB_{group_id}_meta"
    try:
        logger.info(
            f"만료 임박 문서 조회 시작: group_id={group_id}, user_id={user_id}, days={days_before_expiration}"
        )

        await ensure_collection_loaded(collection_name, "meta")

        # output_fields 설정 (embedding_value 제외)
        output_fields = get_output_fields("meta")

        # 현재 시간과 확인할 만료 시간 계산
        current_time = datetime.now(ZoneInfo("Asia/Seoul"))
        expiration_threshold = current_time + timedelta(days=days_before_expiration)

        # 타임스탬프로 변환
        current_timestamp = int(current_time.timestamp())
        expiration_timestamp = int(expiration_threshold.timestamp())

        logger.debug(f"현재 시간: {current_time} ({current_timestamp})")
        logger.debug(f"만료 기준 시간: {expiration_threshold} ({expiration_timestamp})")

        # 만료 임박 조건: 현재 시간보다 크고, 임계값보다 작은 문서들
        expiration_expr = f"expiration_date > {current_timestamp} and expiration_date <= {expiration_timestamp}"

        # role_ids 기반 필터링 조건 설정
        role_filter = " || ".join(
            [f"array_contains(role_ids, {role_id})" for role_id in role_ids]
        )
        expr = f"({role_filter}) and {expiration_expr}"

        logger.info(f"✅ Role 기반 만료 문서 필터링 조건: {expr}")

        # 쿼리 실행
        logger.info(f"✅ Milvus 만료 임박 문서 쿼리 실행: filter={expr}")
        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=output_fields
        )

        logger.info(f"✅ 만료 임박 문서 조회 완료: {len(results)}개 항목 발견")
        return results

    except Exception as e:
        logger.error(
            f"❌ 컬렉션 '{collection_name}'에서 만료 임박 문서 조회 중 오류 발생: {e}"
        )
        raise e


async def validate_documents(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    hash_sha256_list: List[str],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    여러 문서를 배치로 검증합니다.

    문서 권한 확인 및 상태 검증을 수행하여 유효한 문서와 실패한 문서를 분리합니다.
    get_documents 함수를 활용하여 한 번의 쿼리로 배치 조회를 수행합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 접근 가능한 role_id 리스트
        hash_sha256_list: 검증할 문서 해시값 리스트

    Returns:
        tuple[List[Dict], List[Dict]]:
            - 첫 번째: 유효한 문서 리스트 (status=registered)
            - 두 번째: 실패한 문서 리스트 (오류 정보 포함)

    Example:
        >>> valid, failed = await validate_documents(
        ...     group_id=1,
        ...     user_id=123,
        ...     role_ids=[1, 2],
        ...     hash_sha256_list=["abc123...", "def456..."]
        ... )
        >>> print(f"유효: {len(valid)}, 실패: {len(failed)}")
    """
    try:
        logger.info(
            f"문서 배치 검증 시작: user={user_id}, group={group_id}, 문서 수={len(hash_sha256_list)}"
        )

        # select_documents를 사용하여 배치 조회 (권한 확인 자동 포함)
        documents = await select_documents(
            group_id=group_id,
            user_id=user_id,
            role_ids=role_ids,
            db_type="meta",
            hash_sha256_option=hash_sha256_list,  # 리스트 전달
        )

        logger.info(
            f"배치 조회 완료: {len(documents)}개 문서 조회됨 (요청: {len(hash_sha256_list)}개)"
        )

        # 조회된 문서를 hash_sha256로 매핑
        doc_map = {doc["hash_sha256"]: doc for doc in documents}

        valid_docs = []
        failed_docs = []

        # 각 요청된 해시값에 대해 검증
        for hash_sha256 in hash_sha256_list:
            if hash_sha256 not in doc_map:
                # 문서를 찾을 수 없거나 권한이 없음
                failed_docs.append(
                    {
                        "hash_sha256": hash_sha256,
                        "reason": "문서를 찾을 수 없거나 접근 권한이 없습니다",
                    }
                )
                logger.warning(
                    f"문서 조회 실패: hash={hash_sha256[:16]}... (권한 없음 또는 존재하지 않음)"
                )
                continue

            doc = doc_map[hash_sha256]

            # 상태 검증: registered 상태만 허용
            if doc.get("status") != DocumentStatus.REGISTERED:
                failed_docs.append(
                    {
                        "hash_sha256": hash_sha256,
                        "title": doc.get("title", "N/A"),
                        "reason": f"문서 상태가 '{DocumentStatus.REGISTERED}'가 아닙니다 (현재: {doc.get('status', 'unknown')})",
                    }
                )
                logger.warning(
                    f"문서 상태 불일치: hash={hash_sha256[:16]}..., "
                    f"status={doc.get('status')}, title={doc.get('title', 'N/A')}"
                )
                continue

            # 유효한 문서
            valid_docs.append(doc)
            logger.debug(
                f"문서 검증 성공: hash={hash_sha256[:16]}..., title={doc.get('title', 'N/A')}"
            )

        logger.info(
            f"배치 검증 완료: 유효 {len(valid_docs)}개, 실패 {len(failed_docs)}개"
        )

        return valid_docs, failed_docs

    except Exception as e:
        logger.error(f"❌ 문서 배치 검증 중 오류 발생: {e}", exc_info=True)
        # 모든 문서를 실패로 처리
        failed_docs = [
            {
                "hash_sha256": hash_sha256,
                "reason": f"검증 중 오류 발생: {str(e)}",
            }
            for hash_sha256 in hash_sha256_list
        ]
        return [], failed_docs


async def get_hash_by_title(
    group_id: int,
    role_ids: List[int],
    title: str,
) -> Optional[str]:
    """
    meta 컬렉션에서 title exact match로 hash_sha256 조회

    만료된 문서는 제외하고 유효한 문서만 조회한다.

    Args:
        group_id: 그룹 ID
        role_ids: 접근 가능한 role_id 리스트
        title: 조회할 문서 title (source_document에서 확장자 제거한 값)

    Returns:
        단일 매칭 시 hash_sha256, 0건 또는 복수건 시 None
    """
    from app.utils.milvus_filter import escape_milvus_value

    collection_name = f"TB_{group_id}_meta"
    try:
        await ensure_collection_loaded(collection_name, "meta")

        role_filter = " || ".join(
            [f"array_contains(role_ids, {rid})" for rid in role_ids]
        )
        escaped_title = escape_milvus_value(title)
        current_time = int(datetime.now(ZoneInfo("Asia/Seoul")).timestamp())
        expr = (
            f"({role_filter}) and title == '{escaped_title}' "
            f"and expiration_date > {current_time}"
        )

        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=["hash_sha256", "title"],
            limit=10,
            consistency_level="Strong",
        )

        if len(results) == 1:
            return results[0]["hash_sha256"]

        if len(results) > 1:
            logger.warning(
                f"title '{title}'에 대해 {len(results)}건 복수 매칭 — "
                f"hash_sha256 확정 불가, null 처리"
            )

        return None

    except Exception as e:
        logger.error(f"meta 컬렉션 title 조회 실패: {e}")
        return None


async def check_document_exists(
    collection_name: str,
    hash_sha256: str,
) -> bool:
    """
    문서 존재 여부 확인 (멱등성 보장용)

    삽입 전 동일 hash_sha256을 가진 문서가 이미 존재하는지 확인합니다.
    consistency_level="Strong"을 사용하여 최신 데이터를 기준으로 확인합니다.

    Args:
        collection_name: 컬렉션 이름
        hash_sha256: 문서 해시값

    Returns:
        bool: 문서가 존재하면 True, 없으면 False

    Raises:
        Exception: 조회 중 오류 발생 시
    """
    try:
        await ensure_collection_loaded(collection_name, "meta")

        expr = f"hash_sha256 == '{hash_sha256}'"
        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=["id"],  # 존재 여부만 확인하므로 id만 조회
            limit=1,
            consistency_level="Strong"
        )

        exists = bool(results)
        if exists:
            logger.debug(
                f"문서 존재 확인됨: collection={collection_name}, "
                f"hash={hash_sha256[:16]}..."
            )
        return exists

    except Exception as e:
        logger.error(
            f"문서 존재 여부 확인 중 오류 발생: "
            f"collection={collection_name}, hash={hash_sha256[:16]}..., error={e}"
        )
        raise e


# ------------------------------------------
# UPDATE
# ------------------------------------------


async def create_document(collection_name: str, db_type: str, data: List[dict]) -> List[int]:
    """
    데이터 삽입

    지정된 컬렉션에 데이터를 삽입합니다.

    Args:
        collection_name: 컬렉션 이름
        db_type: 데이터베이스 타입 (meta, vector)
        data: 삽입할 데이터 리스트

    Returns:
        List[int]: 삽입된 항목들의 Milvus PK(id) 리스트

    Raises:
        Exception: 데이터 삽입 중 오류 발생 시
    """
    try:
        await ensure_collection_loaded(collection_name, db_type)

        insert_result = await async_insert(
            collection_name=collection_name,
            data=data
        )
        # flush() 제거: MilvusClient 자동 flush (성능 최적화)
        # 데이터 가시성은 조회 시 consistency_level="Strong"으로 보장
        inserted_ids = insert_result["ids"]
        logger.debug(f"✅ 삽입 결과: {insert_result}")
        logger.info(f"✅ 컬렉션 '{collection_name}'에 {len(data)}개 항목 삽입 완료")
        return inserted_ids
    except Exception as e:
        logger.error(f"❌ 컬렉션 '{collection_name}'에 데이터 삽입 중 오류 발생: {e}")
        raise e


async def update_document(
    group_id: int,
    user_id: int,
    role_ids: List[int],
    db_type: str,
    hash_sha256: str,
    update_data: dict,
    include_embedding_value: bool = True,
) -> None:
    """
    데이터 업데이트

    사용자 권한 및 해시값을 기준으로 데이터를 업데이트합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        role_ids: 역할 ID 리스트
        db_type: 데이터베이스 타입 (meta, vector)
        hash_sha256: 문서 해시
        update_data: 업데이트할 데이터
        include_embedding_value: embedding_value 필드 포함 여부 (기본값: True)
            False로 설정 시 메모리 사용량 최소화 (롤백 API 등에서 사용)
            단, meta 컬렉션에서는 upsert 시 필수 필드이므로 True 권장

    Raises:
        Exception: 데이터 업데이트 중 오류 발생 시
    """
    collection_name = f"TB_{group_id}_{db_type}"
    try:
        await ensure_collection_loaded(collection_name, db_type)

        # role_ids 기반 필터링 조건 설정
        # 1(ADMIN)이 role_ids에 포함된 경우 모든 문서 수정 가능, 그 외는 본인 문서만 수정 가능
        if 1 in role_ids:
            expr = f"hash_sha256 == '{hash_sha256}'"
        else:
            expr = f"user_id == {user_id} and hash_sha256 == '{hash_sha256}'"

        # 기존 데이터 조회 (consistency_level="Strong"으로 최신 데이터 보장)
        output_fields = get_all_field_names(db_type) if include_embedding_value else get_output_fields(db_type)
        existing_data = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=output_fields,
            consistency_level="Strong"
        )

        # 업데이트할 데이터가 없으면 경고 로그 출력
        if not existing_data:
            logger.warning(
                f"⚠️ 업데이트할 기존 데이터가 없습니다. hash_sha256: {hash_sha256}"
            )
            return

        # 기존 데이터를 업데이트
        updated_items = []
        for item in existing_data:
            # 중요: id 필드가 있는지 확인
            if "id" not in item:
                logger.error(f"❌ id 필드가 없는 항목이 발견되었습니다: {item}")
                continue

            # 업데이트할 필드만 수정
            for key, value in update_data.items():
                item[key] = value

            # 업데이트 전 데이터 로깅
            logger.debug(f"항목 업데이트 준비 - id: {item.get('id')}")
            updated_items.append(item)

        # 업데이트 실행
        if updated_items:
            logger.info(
                f"✅ Milvus 업데이트: filter={expr}, 항목 수: {len(updated_items)}"
            )
            await async_upsert(
                collection_name=collection_name,
                data=updated_items
            )
            # flush() 제거: MilvusClient 자동 flush (성능 최적화)
            logger.info(
                f"✅ 컬렉션 {collection_name}의 {len(updated_items)}개 행이 업데이트되었습니다."
            )
        else:
            logger.warning("⚠️ 업데이트할 유효한 항목이 없습니다.")
    except Exception as e:
        logger.error(f"❌ 컬렉션 '{collection_name}'에서 행 업데이트 중 오류 발생: {e}")
        raise e


async def update_documents_batch(
    group_id: int,
    hash_sha256_list: List[str],
    update_data: dict,
    include_embedding_value: bool = True,
) -> int:
    """
    여러 문서를 한 번에 업데이트 (배치 처리)

    N번의 개별 Milvus 호출 대신 1번의 배치 호출로 성능 개선.
    - 1번의 query (IN 연산자)
    - 1번의 upsert

    Args:
        group_id: 그룹 ID
        hash_sha256_list: 업데이트할 문서 해시 리스트
        update_data: 업데이트할 데이터
        include_embedding_value: embedding_value 필드 포함 여부 (기본값: True)

    Returns:
        int: 업데이트된 문서 수

    Raises:
        Exception: 데이터 업데이트 중 오류 발생 시
    """
    if not hash_sha256_list:
        return 0

    collection_name = f"TB_{group_id}_meta"

    try:
        await ensure_collection_loaded(collection_name, "meta")

        # IN 연산자로 한 번에 모든 문서 조회
        hash_list_str = ", ".join([f"'{h}'" for h in hash_sha256_list])
        expr = f"hash_sha256 in [{hash_list_str}]"

        # output_fields 설정
        output_fields = get_all_field_names("meta") if include_embedding_value else get_output_fields("meta")

        # 한 번의 query로 모든 문서 조회
        existing_data = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=output_fields
        )

        if not existing_data:
            logger.warning(
                f"⚠️ 업데이트할 문서가 없습니다: group_id={group_id}, "
                f"hash 수={len(hash_sha256_list)}"
            )
            return 0

        # 모든 문서에 update_data 적용
        updated_items = []
        for item in existing_data:
            if "id" not in item:
                logger.error(f"❌ id 필드가 없는 항목: {item.get('hash_sha256', 'unknown')}")
                continue

            for key, value in update_data.items():
                item[key] = value

            updated_items.append(item)

        if not updated_items:
            logger.warning("⚠️ 업데이트할 유효한 항목이 없습니다.")
            return 0

        # 한 번의 upsert로 모든 문서 업데이트
        await async_upsert(
            collection_name=collection_name,
            data=updated_items
        )
        # flush() 제거: MilvusClient 자동 flush (성능 최적화)

        logger.info(
            f"✅ 배치 업데이트 완료: group_id={group_id}, "
            f"업데이트={len(updated_items)}개"
        )
        return len(updated_items)

    except Exception as e:
        logger.error(
            f"❌ 배치 업데이트 중 오류: group_id={group_id}, error={e}"
        )
        raise e


async def update_status(
    group_id: int,
    user_id: int,
    hash_sha256: str,
    status: str,
) -> None:
    """
    문서 상태 업데이트 (meta collection)

    주의: meta collection의 id는 auto_id=True이므로,
    upsert를 사용하여 명시적으로 업데이트합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        hash_sha256: 문서 해시
        status: 새로운 상태 (registered, running, uploaded, failed 등)

    Raises:
        Exception: 상태 업데이트 중 오류 발생 시
    """
    try:
        collection_name = f"TB_{group_id}_meta"
        await ensure_collection_loaded(collection_name, "meta")

        # hash_sha256과 user_id로 기존 문서 확인 (consistency_level="Strong"으로 최신 데이터 보장)
        expr = f"hash_sha256 == '{hash_sha256}' && user_id == {user_id}"
        check_result = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=["id", "status", "hash_sha256", "user_id"],
            limit=10,
            consistency_level="Strong",
        )

        if not check_result:
            logger.warning(
                f"⚠️ 상태 업데이트할 문서가 없습니다: "
                f"user_id={user_id}, hash={hash_sha256[:16]}..."
            )
            return

        if len(check_result) > 1:
            logger.warning(
                f"⚠️ 동일한 hash_sha256과 user_id를 가진 문서가 {len(check_result)}개 존재합니다! "
                f"user_id={user_id}, hash={hash_sha256[:16]}..."
            )

        # 기존 레코드 ID 로깅
        existing_ids = [item.get("id") for item in check_result]
        logger.info(
            f"✅ 문서 상태 업데이트 시작: "
            f"user_id={user_id}, hash={hash_sha256[:16]}..., "
            f"기존 status={check_result[0].get('status')}, "
            f"새 status={status}, "
            f"existing_ids={existing_ids}"
        )

        # 모든 필드를 조회하여 upsert (consistency_level="Strong"으로 최신 데이터 보장)
        output_fields = get_all_field_names("meta")
        existing_data = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=output_fields,
            consistency_level="Strong"
        )

        updated_items = []
        for item in existing_data:
            if "id" not in item:
                logger.error(f"❌ id 필드가 없는 항목: {item.keys()}")
                continue

            old_status = item.get("status")
            item["status"] = status
            updated_items.append(item)

            logger.debug(f"  ID={item['id']}: {old_status} -> {status}")

        # upsert 실행
        if updated_items:
            await async_upsert(
                collection_name=collection_name,
                data=updated_items
            )
            # flush() 제거: MilvusClient 자동 flush (성능 최적화)
            # 데이터 가시성은 조회 시 consistency_level="Strong"으로 보장

            # 업데이트 검증
            verify_result = await async_query(
                collection_name=collection_name,
                filter=expr,
                output_fields=["id", "status"],
                limit=10,
                consistency_level="Strong"
            )

            verify_ids = [item.get("id") for item in verify_result]

            if len(verify_result) > len(check_result):
                logger.error(
                    f"❌ 중복 행 생성 감지! "
                    f"user_id={user_id}, hash={hash_sha256[:16]}..., "
                    f"이전: {len(check_result)}개 (ids={existing_ids}), "
                    f"이후: {len(verify_result)}개 (ids={verify_ids})"
                )
            else:
                logger.info(
                    f"✅ 문서 상태 업데이트 완료: "
                    f"user_id={user_id}, hash={hash_sha256[:16]}..., "
                    f"status={status}, "
                    f"업데이트된 행={len(updated_items)}개, "
                    f"검증 결과={len(verify_result)}개"
                )
        else:
            logger.warning("⚠️ 업데이트할 유효한 항목이 없습니다.")

    except Exception as e:
        logger.error(
            f"❌ 문서 상태 업데이트 중 오류 발생: "
            f"user_id={user_id}, hash={hash_sha256[:16]}..., error={e}"
        )
        raise e


async def select_documents_by_status(
    group_id: int,
    status: str,
    limit: int = 1000,
) -> List[dict]:
    """
    특정 상태의 문서 목록 조회 (meta collection)

    Args:
        group_id: 그룹 ID
        status: 문서 상태 (registered, running, uploaded, failed 등)
        limit: 최대 조회 개수

    Returns:
        List[dict]: 문서 목록

    Raises:
        Exception: 조회 중 오류 발생 시
    """
    try:
        collection_name = f"TB_{group_id}_meta"
        await ensure_collection_loaded(collection_name, "meta")

        # status로 문서 조회
        expr = f"status == '{status}'"
        output_fields = ["hash_sha256", "title", "filename", "status", "user_id"]

        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=output_fields,
            limit=limit,
        )

        logger.info(
            f"✅ 상태별 문서 조회 완료: group_id={group_id}, "
            f"status={status}, 문서 수={len(results)}"
        )

        return results

    except Exception as e:
        logger.error(
            f"❌ 상태별 문서 조회 중 오류 발생: group_id={group_id}, "
            f"status={status}, error={e}"
        )
        return []


# ------------------------------------------
# DELETE
# ------------------------------------------


def drop_collection(collection_name: str) -> None:
    """
    컬렉션 삭제

    지정된 이름의 컬렉션을 삭제합니다.

    Args:
        collection_name: 삭제할 컬렉션 이름
    """
    utility.drop_collection(collection_name)
    logger.info(f"✅ 컬렉션 '{collection_name}' 삭제 완료")


async def delete_document(
    collection_name: str,
    collection_type: str,
    filters: dict,
) -> None:
    """
    데이터 삭제

    필터 조건에 맞는 데이터를 삭제합니다.

    Args:
        collection_name: 컬렉션 이름
        collection_type: 컬렉션 타입 (meta, vector)
        filters: 삭제할 데이터 필터링 조건

    Raises:
        Exception: 데이터 삭제 중 오류 발생 시
    """
    try:
        await ensure_collection_loaded(collection_name, collection_type)

        # 필터 조건 구성
        expr_parts = []
        for key, value in filters.items():
            if isinstance(value, str):
                expr_parts.append(f"{key} == '{value}'")
            else:
                expr_parts.append(f"{key} == {value}")
        expr = " and ".join(expr_parts)

        # 삭제 실행
        logger.debug(f"Milvus 삭제: filter={expr}")
        await async_delete(
            collection_name=collection_name,
            filter=expr
        )
        logger.info(f"✅ 컬렉션 '{collection_name}'에서 데이터 삭제 완료")
    except Exception as e:
        logger.error(f"❌ 데이터 삭제 중 오류 발생: {e}")
        raise e


async def delete_vectors(
    group_id: int,
    hash_sha256_list: List[str],
) -> int:
    """
    hash_sha256 기준으로 vector 컬렉션의 청크+벡터 삭제

    임베딩 롤백 시 사용됩니다.

    Args:
        group_id: 그룹 ID
        hash_sha256_list: 삭제할 문서 해시 리스트

    Returns:
        int: 삭제된 행 수

    Raises:
        Exception: 삭제 중 오류 발생 시
    """
    try:
        collection_name = f"TB_{group_id}_vector"
        await ensure_collection_loaded(collection_name, "vector")

        # IN 연산자용 해시 리스트 문자열 생성
        hash_list_str = ", ".join([f"'{h}'" for h in hash_sha256_list])
        expr = f"hash_sha256 in [{hash_list_str}]"

        # 삭제 전 개수 확인
        before_result = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=["id"]
        )
        deleted_count = len(before_result)

        if deleted_count == 0:
            logger.info(
                f"삭제할 벡터 없음: group_id={group_id}, "
                f"hash 수={len(hash_sha256_list)}"
            )
            return 0

        # 삭제 실행
        await async_delete(
            collection_name=collection_name,
            filter=expr
        )
        # flush() 제거: MilvusClient 자동 flush (성능 최적화)

        logger.info(
            f"✅ 벡터 삭제 완료: group_id={group_id}, "
            f"삭제된 청크={deleted_count}개"
        )
        return deleted_count

    except Exception as e:
        logger.error(
            f"❌ 벡터 삭제 중 오류 발생: group_id={group_id}, error={e}"
        )
        raise e


async def delete_vectors_by_ids(group_id: int, inserted_ids: List[int]) -> int:
    """Milvus PK(id) 기준으로 vector 컬렉션의 청크를 삭제한다.

    R-02(BM25 실패 시 split-brain 보완)용. hash 기준 전체 삭제(delete_vectors)와 달리
    이번 실행에서 insert된 id만 정리하므로 같은 hash의 기존 정상 vector를 건드리지 않는다.
    meta/BM25/status는 건드리지 않는다.

    Args:
        group_id: 그룹 ID
        inserted_ids: 이번 실행에서 insert된 Milvus PK(id) 리스트

    Returns:
        int: 삭제 요청한 id 수 (빈 목록이면 0, no-op)

    Raises:
        Exception: 삭제 중 오류 발생 시
    """
    if not inserted_ids:
        return 0

    # 인젝션 방지: PK는 int64이므로 명시적으로 int로 강제
    safe_ids = [int(pk) for pk in inserted_ids]
    collection_name = f"TB_{group_id}_vector"
    try:
        await ensure_collection_loaded(collection_name, "vector")
        await async_delete(collection_name=collection_name, filter=f"id in {safe_ids}")
        logger.info(
            f"✅ 이번 실행 vector 삭제(id 기준): group_id={group_id}, "
            f"삭제 id 수={len(safe_ids)}"
        )
        return len(safe_ids)
    except Exception as e:
        logger.error(
            f"❌ 이번 실행 vector 삭제(id 기준) 실패: group_id={group_id}, error={e}"
        )
        raise e


async def delete_documents_batch(
    group_id: int,
    hash_sha256_list: List[str],
) -> Dict[str, int]:
    """
    여러 문서를 배치로 삭제 (meta + vector 컬렉션)

    N번의 개별 Milvus 호출 대신 2번의 배치 호출로 성능 개선.
    - 1번의 delete (vector 컬렉션)
    - 1번의 delete (meta 컬렉션)

    Args:
        group_id: 그룹 ID
        hash_sha256_list: 삭제할 문서 해시 리스트

    Returns:
        Dict[str, int]: 삭제 결과
            - vector_deleted: 삭제된 벡터(청크) 수
            - meta_deleted: 삭제된 메타데이터 수

    Raises:
        Exception: 삭제 중 오류 발생 시
    """
    if not hash_sha256_list:
        return {"vector_deleted": 0, "meta_deleted": 0}

    result = {"vector_deleted": 0, "meta_deleted": 0}

    try:
        # IN 연산자용 해시 리스트 문자열 생성
        hash_list_str = ", ".join([f"'{h}'" for h in hash_sha256_list])
        expr = f"hash_sha256 in [{hash_list_str}]"

        # 1. Vector 컬렉션 배치 삭제
        vector_collection_name = f"TB_{group_id}_vector"
        await ensure_collection_loaded(vector_collection_name, "vector")

        # 삭제 전 개수 확인
        vector_before = await async_query(
            collection_name=vector_collection_name,
            filter=expr,
            output_fields=["id"]
        )
        result["vector_deleted"] = len(vector_before)

        if result["vector_deleted"] > 0:
            await async_delete(
                collection_name=vector_collection_name,
                filter=expr
            )
            logger.info(
                f"✅ Vector 배치 삭제 완료: group_id={group_id}, "
                f"삭제={result['vector_deleted']}개"
            )

        # 2. Meta 컬렉션 배치 삭제
        meta_collection_name = f"TB_{group_id}_meta"
        await ensure_collection_loaded(meta_collection_name, "meta")

        # 삭제 전 개수 확인
        meta_before = await async_query(
            collection_name=meta_collection_name,
            filter=expr,
            output_fields=["id"]
        )
        result["meta_deleted"] = len(meta_before)

        if result["meta_deleted"] > 0:
            await async_delete(
                collection_name=meta_collection_name,
                filter=expr
            )
            logger.info(
                f"✅ Meta 배치 삭제 완료: group_id={group_id}, "
                f"삭제={result['meta_deleted']}개"
            )

        logger.info(
            f"✅ 문서 배치 삭제 완료: group_id={group_id}, "
            f"hash 수={len(hash_sha256_list)}, "
            f"vector={result['vector_deleted']}개, meta={result['meta_deleted']}개"
        )

        return result

    except Exception as e:
        logger.error(
            f"❌ 문서 배치 삭제 중 오류 발생: group_id={group_id}, error={e}"
        )
        raise e
