import hashlib
import logging
import tempfile
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from celery.exceptions import Ignore
from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.chunking import ChunkerFactory
from app.config import settings
from app.config.constants import DEFAULT_VECTOR_DIMENSION
from app.dto.chunking_dto import parse_chunking_config
from app.crud.milvus.document_crud import (
    check_document_exists,
    create_document,
    select_documents,
    update_document,
    update_status,
)
from app.dto.document_status import DocumentStatus
from app.parser.factory import ParserFactory
from app.parser.ocr_parser import OcrParser, OcrUnavailableError
from app.service.document_summary_service import DocumentSummaryService
from app.service.utils.cleanup import cleanup_temp_file
from app.utils.check_duplicate import is_duplicate_data
from app.utils.document_utils import merge_parsed_content_to_text
from app.utils.embedding import embed_query
from app.utils.notification import (
    publish_duplicate_detected,
    publish_ocr_required,
    publish_upload_completed,
    publish_upload_failed,
)
from app.utils.pii_utils import apply_pii_to_text
from app.worker.celery import app
from app.worker.utils.async_runner import task_async_runner

load_dotenv()
logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    time_limit=300,
    soft_time_limit=270,
    max_retries=3,
    default_retry_delay=30,
)
def download_document(self, params: dict) -> dict:
    """
    Cloud Storage에서 문서를 다운로드합니다.

    download_url을 사용하여 문서를 다운로드하여 임시 파일로 저장합니다.

    타임아웃:
    - soft_time_limit: 4분 30초 - 정상 종료 시도
    - time_limit: 5분 - 강제 종료
    """
    try:
        url = params["download_url"]

        logger.info(f"[pipeline] ☁️ 문서 다운로드 시작: {url[:50]}...")

        # cloud-storage 의 인증 endpoint 호출 — `x-user-passport` 헤더 동봉.
        # rabbitmq_consumer 가 `params["passport_json"]` 에 직렬화된 passport JSON 박제.
        passport_json = params.get("passport_json")
        headers = {"x-user-passport": passport_json} if passport_json else {}
        logger.info(
            f"[pipeline] 🔐 download headers: passport_json_present={bool(passport_json)} "
            f"len={len(passport_json) if passport_json else 0}"
        )

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as temp_file:
            temp_path = temp_file.name
            logger.info(f"[pipeline] 📁 임시 파일 생성: {temp_path}")

            # 스트리밍으로 파일 다운로드
            response = requests.get(url, stream=True, timeout=120, headers=headers)
            response.raise_for_status()

            total_bytes = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    total_bytes += len(chunk)

            logger.info(
                f"[pipeline] ✅ 다운로드 완료: {total_bytes:,} bytes ({total_bytes/1024/1024:.2f} MB)"
            )

            # 임시 파일 경로를 params에 저장
            params["temp_file_path"] = temp_path

        return params

    except requests.exceptions.RequestException as e:
        logger.error(f"[pipeline] 💥 문서 다운로드 실패: {e}")
        self.retry(exc=e, countdown=5)
    except Exception as e:
        logger.error(f"[pipeline] 💥 문서 다운로드 중 오류 발생: {e}")
        self.retry(exc=e, countdown=5)


@app.task(
    bind=True,
    time_limit=120,
    soft_time_limit=110,
    max_retries=3,
    default_retry_delay=10,
)
def extract_metadata(self, params: dict) -> dict:
    """
    메타데이터를 추출합니다.

    타임아웃:
    - soft_time_limit: 1분 50초 - 정상 종료 시도
    - time_limit: 2분 - 강제 종료
    """
    try:
        logger.info("[pipeline] 📊 메타데이터 추출 시작...")

        # 임시 파일 경로 사용 (retrieve_document에서 저장한 경로)
        temp_file_path = params["temp_file_path"]

        # 파라미터 추가
        file_type = params["file_path"].split(".")[-1]
        params["file_type"] = file_type
        params["filename"] = Path(params["file_path"]).name

        # 고유 해시값 생성
        logger.info(f"[pipeline] 🔐 파일 해시값 생성 시작: {temp_file_path}")
        with open(temp_file_path, "rb") as f:
            sha256_hash = hashlib.sha256()
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
            params["hash_sha256"] = sha256_hash.hexdigest()
        logger.info(
            f"[pipeline] ✅ 파일 해시값 생성 완료: {params['hash_sha256'][:8]}..."
        )

        params["status"] = DocumentStatus.UPLOADING
        params["start_date"] = int(time.time())

        return params

    except Exception as e:
        logger.error(f"[pipeline] 💥 메타데이터 추출 중 오류 발생: {e}")
        self.retry(exc=e, countdown=5)


@app.task(
    bind=True, time_limit=60, soft_time_limit=55, max_retries=3, default_retry_delay=5
)
def check_duplicate(self, params: dict) -> dict:
    """
    중복 문서를 확인합니다.

    타임아웃:
    - soft_time_limit: 55초 - 정상 종료 시도
    - time_limit: 60초 - 강제 종료
    """
    try:
        logger.info("[pipeline] 🔍 중복 문서 확인 시작...")

        user_id = params["user_id"]
        title = params["title"]

        # 중복 문서 확인
        with task_async_runner() as runner:
            is_duplicate = runner.run(is_duplicate_data(params))

        if is_duplicate:
            logger.info(f"[pipeline] ⚠️ 중복 문서 감지됨: {title}")
            # 중복 감지 시 SSE 알림 발행
            publish_duplicate_detected(
                task_id=params["task_id"],
                user_id=str(user_id),
            )

            # 중복 문서의 경우 임시 파일 정리 후 작업 종료
            cleanup_temp_file(params)

            # Celery 작업을 정상적으로 종료 (결과 기록하지 않음)
            raise Ignore()

        logger.info("[pipeline] ✅ 중복 문서 없음 - 처리 계속 진행")
        return params

    except Ignore:
        logger.info("[pipeline] ✅ 중복 문서 처리 완료. 작업을 종료합니다.")
        raise
    except Exception as e:
        logger.error(f"[pipeline] 💥 중복 확인 중 오류 발생: {e}")
        self.retry(exc=e, countdown=5)


@app.task(
    bind=True,
    time_limit=120,
    soft_time_limit=110,
    max_retries=3,
    default_retry_delay=10,
)
def insert_initial_metadata(self, params: dict) -> dict:
    """
    초기 메타데이터를 Milvus에 삽입합니다.

    타임아웃:
    - soft_time_limit: 1분 50초 - 정상 종료 시도
    - time_limit: 2분 - 강제 종료
    """
    try:
        logger.info("[pipeline] 📝 초기 메타데이터 삽입 시작...")

        # expiration_date를 Asia/Seoul 타임존 Unix 타임스탬프로 변환
        seoul_tz = ZoneInfo("Asia/Seoul")
        expiration_dt = datetime.fromisoformat(
            params["expiration_date"].replace("Z", "+00:00")
        )
        expiration_timestamp = int(expiration_dt.astimezone(seoul_tz).timestamp())

        # 초기 데이터 구성
        db_type = "meta"
        data = {
            "category": params["category"],
            "title": params["title"],
            "filename": params["filename"],
            "summary": "",
            "file_type": params["file_type"],
            "file_size": params["file_size"],
            "status": params["status"],
            "role_ids": params["total_role"],
            "persona_id": params.get("persona_id", 0),
            "file_path": params["file_path"],
            "download_url": params["download_url"],
            "chunk_count": 0,
            "token": 0,
            "cost": 0,
            "group_id": params["group_id"],
            "user_id": params["user_id"],
            "hash_sha256": params["hash_sha256"],
            "start_date": params["start_date"],
            "end_date": 0,
            "expiration_date": expiration_timestamp,
            "embedding_value": [0.0] * DEFAULT_VECTOR_DIMENSION,
            "summary_token": 0,
            "summary_cost": 0.0,
            "anonymization_strategy": (
                params.get("pii_strategy")
                if params.get("enable_pii_anonymization")
                else None
            ),
            # 청킹 설정 (Semantic Chunking일 때 max_chunk_size 사용)
            "chunk_size": (
                params["chunking"]["max_chunk_size"]
                if params.get("chunking") and params["chunking"]["strategy"] == "semantic"
                else params["chunk_size"]
            ),
            "chunk_overlap": (
                0
                if params.get("chunking") and params["chunking"]["strategy"] == "semantic"
                else params["chunk_overlap"]
            ),
            # PII 비식별화 설정
            "enable_pii_anonymization": (
                1 if params.get("enable_pii_anonymization") else 0
            ),
            "pii_types": (
                ",".join(params.get("pii_types", []))
                if params.get("enable_pii_anonymization") and params.get("pii_types")
                else None
            ),
            # 페르소나 필터링 결과 (초기값 0)
            "original_chunk_count": 0,
            "filtered_chunk_count": 0,
            # 임베딩 소요 시간 (초기값 0)
            "embedding_start_date": 0,
            "embedding_end_date": 0,
        }
        collection_name = f"{params['collection_header']}_{db_type}"

        # 멱등성 보장: 삽입 전 동일 hash_sha256 존재 여부 확인
        with task_async_runner() as runner:
            existing = runner.run(
                check_document_exists(collection_name, params["hash_sha256"])
            )

        if existing:
            # 이미 존재하면 삽입 스킵 (워커 crash 후 재시도 시 중복 방지)
            logger.info(
                f"[pipeline] ⏭️ 문서가 이미 존재하여 삽입 스킵: "
                f"hash={params['hash_sha256'][:16]}..."
            )
            return params

        # Milvus에 초기 데이터 삽입
        with task_async_runner() as runner:
            runner.run(create_document(collection_name, db_type, [data]))

        logger.info("[pipeline] ✅ 초기 메타데이터 삽입 완료")
        return params

    except Exception as e:
        logger.error(f"[pipeline] 💥 메타데이터 삽입 중 오류 발생: {e}")
        self.retry(exc=e, countdown=5)


@app.task(
    bind=True,
    time_limit=900,
    soft_time_limit=870,
    max_retries=3,
    default_retry_delay=30,
)
def parse_document_task(self, params: dict) -> dict:
    """
    문서 파싱 및 텍스트 분할

    타임아웃:
    - soft_time_limit: 14분 30초 - 정상 종료 시도
    - time_limit: 15분 - 강제 종료
    """
    try:
        logger.info("[pipeline] 📄 문서 파싱 시작...")

        file_type = params["file_type"]
        temp_file_path = params["temp_file_path"]
        document_parser = params["document_parser"]

        # PII 설정
        enable_pii = params["enable_pii_anonymization"]
        pii_strategy = params["pii_strategy"]
        pii_types = params["pii_types"]

        if enable_pii:
            logger.info(f"[pipeline] 🔐 PII 비식별화 활성화: {pii_strategy}")

        # ParserFactory를 통한 파서 생성 (팩토리 패턴)
        parser_name = document_parser if document_parser else None
        logger.info(
            f"[pipeline] 📄 파서 생성: parser_name={parser_name}, file_type={file_type}"
        )

        with task_async_runner() as runner:
            parser = runner.run(
                ParserFactory.create(
                    parser_name=parser_name,
                    file_type=file_type,
                    enable_pii_anonymization=enable_pii,
                    pii_strategy=pii_strategy,
                    pii_types=pii_types,
                    use_worker_context=True,
                )
            )
            logger.info(
                f"[pipeline] ✅ 파서 생성 완료: {parser.get_parser_name()}"
            )
            parsed_contents = runner.run(
                parser.parsing(temp_file_path, params["filename"])
            )

        # 외부 파서 사용 시 PII 비식별화 적용 (내부 파서는 CleansingAdapter에서 처리)
        if document_parser and enable_pii:
            logger.info("[pipeline] 🔐 외부 파서 결과에 PII 비식별화 적용")
            for page in parsed_contents:
                page["text"] = apply_pii_to_text(
                    page["text"],
                    strategy=pii_strategy,
                    pii_types=pii_types,
                )

        # OCR이 필요한 문서인지 확인 (이미지 PDF) → Naver OCR fallback 시도
        if parsed_contents and len(parsed_contents) > 0:
            first_item = parsed_contents[0]
            if isinstance(first_item, dict) and first_item.get("needs_ocr", False):
                logger.info("[pipeline] 📄 OCR이 필요한 PDF 문서 감지 - OCR fallback 시도")

                try:
                    with task_async_runner() as runner:
                        parsed_contents = runner.run(
                            OcrParser().parsing(temp_file_path, params["filename"])
                        )
                    # CleansingAdapter를 우회하므로 OCR 텍스트에 PII 비식별화 직접 적용
                    if enable_pii:
                        logger.info("[pipeline] 🔐 OCR 결과에 PII 비식별화 적용")
                        for page in parsed_contents:
                            page["text"] = apply_pii_to_text(
                                page["text"],
                                strategy=pii_strategy,
                                pii_types=pii_types,
                            )
                    logger.info(
                        f"[OCR] ✅ OCR fallback 성공 - {len(parsed_contents)}개 페이지"
                    )
                except OcrUnavailableError as ocr_error:
                    # 페이지 초과 / 결과 없음 / API 오류 → 기존과 동일하게 ocr_required 유지
                    logger.info(
                        f"[OCR] OCR fallback 미수행/실패(reason={ocr_error.reason}) "
                        f"- ocr_required 유지"
                    )
                    update_ocr_required_status(params)
                    # update_ocr_required_status는 Ignore 예외를 발생시키므로 도달하지 않음
                    return params

        params["parsed_contents"] = parsed_contents

        # 텍스트 분할 (ChunkerFactory 사용)
        chunking_config = params.get("chunking")
        if chunking_config:
            # 새로운 chunking 설정 사용
            config = parse_chunking_config(chunking_config)
            chunker = ChunkerFactory.create(config)
        else:
            # 하위 호환: 기존 chunk_size/chunk_overlap 사용
            chunker = ChunkerFactory.create_fixed(
                chunk_size=params["chunk_size"],
                chunk_overlap=params["chunk_overlap"],
            )
        text_chunks = chunker.chunk(parsed_contents)

        logger.info(f"[pipeline] ✅ 파싱 완료: {len(text_chunks)}개 청크")

        params["db_type"] = "vector"
        params["text_chunks"] = text_chunks

        return params

    except Exception as e:
        logger.error(f"[pipeline] 💥 문서 파싱 중 오류 발생: {e}")
        raise


@app.task(
    bind=True,
    time_limit=600,
    soft_time_limit=570,
    max_retries=3,
    default_retry_delay=30,
)
def generate_document_summary(self, params: dict) -> dict:
    """
    문서를 파싱하고 요약을 생성하며 임베딩을 수행합니다.

    타임아웃:
    - soft_time_limit: 9분 30초 - 정상 종료 시도
    - time_limit: 10분 - 강제 종료
    """
    try:
        logger.info("[pipeline] 📝 문서 요약 생성 및 임베딩 시작...")

        # 파싱된 내용을 문자열로 변환
        merged_text = merge_parsed_content_to_text(params["parsed_contents"])
        logger.info(f"[pipeline] 📄 텍스트 변환 완료 - 길이: {len(merged_text)} 문자")

        # 모든 async 작업을 단일 이벤트 루프에서 실행
        # (여러 task_async_runner() 사용 시 이벤트 루프 충돌 발생)
        with task_async_runner() as runner:

            async def run_all_async_tasks():
                # 1. 요약 생성
                async with AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY
                ) as openai_client:
                    summary_service = DocumentSummaryService(openai_client)
                    summary_result = await summary_service.generate_summary(
                        document_content=merged_text,
                    )

                document_summary = summary_result["summary"]
                summary_token = summary_result["total_tokens"]
                summary_cost = (summary_result["prompt_tokens"] / 1000) * 0.00015 + (
                    summary_result["completion_tokens"] / 1000
                ) * 0.0006

                logger.info(
                    f"[pipeline] ✅ 문서 요약 생성 완료 - "
                    f"토큰: {summary_token}, 비용: ${summary_cost:.6f}"
                )

                # 2. 요약 임베딩
                embedded_summary = await embed_query(document_summary)
                logger.info(f"[pipeline] ✅ 요약 임베딩 완료: {len(embedded_summary)} 차원")

                # 3. Milvus 업데이트
                await update_document(
                    group_id=params["group_id"],
                    user_id=params["user_id"],
                    role_ids=params["total_role"],
                    db_type="meta",
                    hash_sha256=params["hash_sha256"],
                    update_data={
                        "summary": document_summary,
                        "summary_token": summary_token,
                        "summary_cost": summary_cost,
                        "embedding_value": embedded_summary,
                    },
                )
                logger.info("[pipeline] ✅ 요약, 임베딩 정보 업데이트 완료")

                # TODO: LightRAG 기능 임시 비활성화
                # # 4. LightRAG: 엔티티/관계 추출 및 저장
                # graph_result = await extract_graph_from_document(
                #     text=document_summary,
                #     hash_sha256=params["hash_sha256"],
                #     group_id=params["group_id"],
                #     user_id=params["user_id"],
                #     role_ids=params["total_role"],
                # )

                return {
                    "document_summary": document_summary,
                    "summary_token": summary_token,
                    "summary_cost": summary_cost,
                }

            runner.run(run_all_async_tasks())

        # TODO: LightRAG 기능 임시 비활성화
        # entities_count = result["graph_result"]["entities_count"]
        # relations_count = result["graph_result"]["relations_count"]
        #
        # logger.info(
        #     f"[pipeline] ✅ LightRAG 엔티티/관계 추출 완료 - "
        #     f"엔티티: {entities_count}개, 관계: {relations_count}개"
        # )
        #
        # params["entities_count"] = entities_count
        # params["relations_count"] = relations_count

        # 요약 정상 완료 후 parsed_contents는 더 이상 사용하지 않으므로 메모리 해제
        params.pop("parsed_contents", None)

        return params

    except Exception as e:
        logger.error(f"[pipeline] 💥 문서 요약 생성 중 오류 발생: {e}", exc_info=True)
        params["error"] = str(e)
        self.retry(exc=e, countdown=5)


@app.task(time_limit=60, soft_time_limit=55, max_retries=3, default_retry_delay=5)
def update_final_status(params: dict) -> dict:
    """
    문서 처리 완료 후 최종 상태를 업데이트합니다.

    타임아웃:
    - soft_time_limit: 55초 - 정상 종료 시도
    - time_limit: 60초 - 강제 종료
    """
    try:
        logger.info("[pipeline] ✅ 최종 상태 업데이트 중...")

        # 페르소나 필터링으로 스킵된 경우 처리
        if params["skip_embedding"]:
            save_final_document_status(params, DocumentStatus.SKIPPED)
            publish_upload_completed(
                task_id=params["task_id"],
                user_id=str(params["user_id"]),
                message=f"페르소나 필터링 결과 관련 청크 없음: {params['title']}",
                metadata={
                    "title": params["title"],
                    "status": "SKIPPED",
                    "reason": (
                        params["skip_reason"]
                        if "skip_reason" in params
                        else "no_relevant_chunks"
                    ),
                    "original_chunks": (
                        params["original_chunk_count"]
                        if "original_chunk_count" in params
                        else 0
                    ),
                    "selected_chunks": (
                        params["filtered_chunk_count"]
                        if "filtered_chunk_count" in params
                        else 0
                    ),
                },
            )
            cleanup_temp_file(params)
            return params

        # 최종 상태 업데이트 및 완료 알림 발행
        save_final_document_status(params, DocumentStatus.UPLOADED)
        publish_upload_completed(
            task_id=params["task_id"],
            user_id=str(params["user_id"]),
            message=f"문서 업로드가 완료되었습니다: {params['title']}",
            metadata={"title": params["title"], "status": "COMPLETED"},
        )
        cleanup_temp_file(params)
        return params

    except Exception as e:
        logger.error(f"[pipeline] ❌ 최종 상태 업데이트 중 오류 발생: {e}")
        cleanup_temp_file(params)
        raise e


@app.task(
    bind=True,
    time_limit=60,
    soft_time_limit=55,
    max_retries=3,
    default_retry_delay=5,
)
def update_registration_status(self, params: dict) -> dict:
    """
    문서 등록 완료 후 상태를 'registered'로 업데이트하고 임시 파일을 삭제합니다.

    분리 모드(pipeline_separation=true)에서 메타데이터 등록이 완료된 후 호출됩니다.

    Args:
        params: 파이프라인 매개변수

    Returns:
        dict: 업데이트된 params

    타임아웃:
    - soft_time_limit: 55초 - 정상 종료 시도
    - time_limit: 60초 - 강제 종료
    """
    try:
        logger.info("[pipeline] ✅ 문서 등록 완료 상태 업데이트 중...")

        # 상태를 'registered'로 업데이트
        update_data = {
            "status": DocumentStatus.REGISTERED,
            "end_date": int(time.time()),
        }

        # meta_info 업데이트 (비동기 함수를 동기적으로 실행)
        with task_async_runner() as runner:
            runner.run(
                update_document(
                    group_id=params["group_id"],
                    user_id=params["user_id"],
                    role_ids=params["total_role"],
                    db_type="meta",
                    hash_sha256=params["hash_sha256"],
                    update_data=update_data,
                )
            )

        logger.info(
            f"[pipeline] ✅ 문서 등록 완료: title={params['title']}, "
            f"hash={params['hash_sha256'][:8]}..."
        )

        # 임시 파일 삭제
        cleanup_temp_file(params)

        return params

    except Exception as e:
        logger.error(f"[pipeline] ❌ 문서 등록 상태 업데이트 중 오류 발생: {e}")
        cleanup_temp_file(params)
        raise


@app.task(time_limit=60, soft_time_limit=55, max_retries=3, default_retry_delay=5)
def update_ocr_required_status(params: dict) -> None:
    """
    OCR이 필요한 문서의 상태를 업데이트합니다.

    타임아웃:
    - soft_time_limit: 55초 - 정상 종료 시도
    - time_limit: 60초 - 강제 종료
    """
    try:
        logger.info("[pipeline] 📄 OCR 필요 문서 상태 업데이트 시작...")

        # OCR 필요 알림 발행
        publish_ocr_required(task_id=params["task_id"], user_id=str(params["user_id"]))

        # meta_info 업데이트를 위한 데이터 준비
        update_data = {
            "status": DocumentStatus.OCR_REQUIRED,
            "summary": "이 PDF는 스캔 이미지형 문서로 OCR 처리가 필요합니다.",
            "end_date": int(time.time()),
        }

        # meta_info 업데이트 (비동기 함수를 동기적으로 실행)
        with task_async_runner() as runner:
            runner.run(
                update_document(
                    group_id=params["group_id"],
                    user_id=params["user_id"],
                    role_ids=params["total_role"],
                    db_type="meta",
                    hash_sha256=params["hash_sha256"],
                    update_data=update_data,
                )
            )

        logger.info("[pipeline] ✅ OCR 필요 상태 업데이트 완료")

        # 임시 파일 정리
        cleanup_temp_file(params)

        # Ignore 예외를 발생시켜 파이프라인 종료
        raise Ignore("OCR이 필요한 문서로 파이프라인을 종료합니다.")

    except Ignore:
        raise
    except Exception as e:
        logger.error(f"[pipeline] ❌ OCR 필요 상태 업데이트 중 오류: {e}")
        # 실패하면 일반 실패 처리로 폴백
        update_failed_status(params)


@app.task(time_limit=60, soft_time_limit=55, max_retries=3, default_retry_delay=5)
def update_failed_status(params) -> None:
    """
    (업로드 실패) 상태 업데이트

    타임아웃:
    - soft_time_limit: 55초 - 정상 종료 시도
    - time_limit: 60초 - 강제 종료
    """
    # 파라미터가 문자열인 경우 처리
    if isinstance(params, str):
        logger.warning(f"[pipeline] ⚠️ 문자열 파라미터를 받았습니다: {params}")
        return

    try:
        filename = (
            params["filename"]
            if "filename" in params
            else params["url"] if "url" in params else "알 수 없음"
        )
        title = params["title"] if "title" in params else filename
        task_id = params["task_id"] if "task_id" in params else "unknown"
        user_id = params["user_id"] if "user_id" in params else "unknown"
        error_message = params["error"] if "error" in params else "알 수 없는 오류"

        logger.warning(f"[pipeline] ⚠️ 최종 상태 업데이트 (실패): '{filename}'")

        # 실패 알림 발행
        publish_upload_failed(
            task_id=task_id,
            user_id=str(user_id),
            message=f"문서 업로드에 실패했습니다: {title}",
            metadata={
                "document": {
                    "title": title,
                    "filename": filename,
                    "error": error_message,
                    "status": DocumentStatus.FAILED,
                }
            },
        )
        logger.info(
            f"[pipeline] ✅ 업로드 실패 알림 발행됨: task_id={task_id}, user_id={user_id}"
        )

        # 상태 업데이트
        if "group_id" in params:
            save_final_document_status(params, DocumentStatus.FAILED)
        else:
            logger.error(
                "[pipeline] ❌ 필수 파라미터(group_id) 누락으로 상태 업데이트 건너뜀"
            )

        cleanup_temp_file(params)

    except Exception as e:
        logger.error(f"[pipeline] ❌ 업로드 실패 알림 발행 중 오류 발생: {e}")
        cleanup_temp_file(params)


def save_final_document_status(params, status: str) -> None:
    """
    파이프라인 완료/실패 시 최종 문서 상태 저장
    """
    try:
        logger.info(f"[pipeline] ✅ 상태 업데이트 시작: 상태={status}")

        update_data = {"status": status}

        # 상태가 "uploaded" 또는 "skipped"인 경우, 비용 정보 및 임베딩 파라미터 업데이트
        if status in [DocumentStatus.UPLOADED, DocumentStatus.SKIPPED]:
            update_data.update(
                {
                    "token": params["total_tokens"] if "total_tokens" in params else 0,
                    "cost": params["total_cost"] if "total_cost" in params else 0,
                    "end_date": int(time.time()),
                    "chunk_count": (
                        params["chunk_count"]
                        if "chunk_count" in params
                        else len(params["transformed_data"])
                        if "transformed_data" in params
                        else 0
                    ),
                    # 청킹 설정 (Semantic Chunking일 때 max_chunk_size 사용)
                    "chunk_size": (
                        params["chunking"]["max_chunk_size"]
                        if params.get("chunking") and params["chunking"]["strategy"] == "semantic"
                        else params["chunk_size"]
                    ),
                    "chunk_overlap": (
                        0
                        if params.get("chunking") and params["chunking"]["strategy"] == "semantic"
                        else params["chunk_overlap"]
                    ),
                    # PII 비식별화 설정
                    "enable_pii_anonymization": (
                        1 if params.get("enable_pii_anonymization") else 0
                    ),
                    "pii_types": (
                        ",".join(params.get("pii_types", []))
                        if params.get("enable_pii_anonymization")
                        and params.get("pii_types")
                        else None
                    ),
                    # 페르소나 필터링 결과
                    "original_chunk_count": params.get("original_chunk_count", 0),
                    "filtered_chunk_count": params.get("filtered_chunk_count", 0),
                    # 임베딩 소요 시간
                    "embedding_start_date": params.get("embedding_start_date", 0),
                    "embedding_end_date": params.get("embedding_end_date", 0),
                }
            )

            # persona_id가 있고 0이 아닌 경우 업데이트
            if "persona_id" in params and params["persona_id"] != 0:
                update_data["persona_id"] = params["persona_id"]
                logger.debug(f"[pipeline] persona_id 업데이트: {params['persona_id']}")

            # PII 관련 파라미터 업데이트
            # 주의: anonymization_strategy는 Milvus 스키마와 엔티티 정의가 불일치하여
            # 업데이트 시 오류 발생 가능성이 있으므로 안전하게 스킵합니다.
            # 필요시 Milvus 컬렉션 스키마를 확인하고 재생성해야 합니다.
            # if "pii_strategy" in params and params["pii_strategy"]:
            #     update_data["anonymization_strategy"] = params["pii_strategy"]
            #     logger.debug(
            #         f"[pipeline] anonymization_strategy 업데이트: {params['pii_strategy']}"
            #     )

            # 주의: chunk_size, chunk_overlap, filter_score는 meta 컬렉션 스키마에 없으므로
            # 업데이트하지 않습니다. 이 정보가 필요하면 PostgreSQL 등 다른 DB에 저장해야 합니다.

            logger.debug(
                f"[pipeline] 비용 정보 및 임베딩 파라미터 포함 최종 업데이트: {update_data}"
            )

        # Milvus 업데이트
        with task_async_runner() as runner:
            runner.run(
                update_document(
                    group_id=params["group_id"],
                    user_id=params["user_id"],
                    role_ids=params["total_role"],
                    db_type="meta",
                    hash_sha256=params["hash_sha256"],
                    update_data=update_data,
                )
            )

        logger.info(f"[pipeline] ✅ 문서 상태가 업데이트되었습니다: 상태={status}")

        # 업로드 성공 시 메시지 발행
        if status == DocumentStatus.UPLOADED:
            publish_upload_completed(
                task_id=params["task_id"],
                user_id=params["user_id"],
                message="문서 처리가 성공적으로 완료되었습니다.",
                metadata={
                    "document": {
                        "title": params["title"] if "title" in params else "",
                        "filename": params["filename"] if "filename" in params else "",
                        "file_type": (
                            params["file_type"] if "file_type" in params else ""
                        ),
                        "hash_sha256": params["hash_sha256"],
                        "group_id": params["group_id"],
                        "role_ids": params["total_role"],
                        "status": status,
                    }
                },
            )
            logger.info(
                f"[pipeline] ✅ 작업 완료 메시지가 발행되었습니다: 태스크={params['task_id']}"
            )

    except Exception as e:
        logger.error(f"[pipeline] ❌ 상태 업데이트 중 오류 발생: {e}")
        raise e


@app.task(
    bind=True,
    time_limit=120,
    soft_time_limit=100,
    max_retries=3,
    default_retry_delay=30,
)
def validate_document_status(self, params: dict) -> dict:
    """
    문서 상태 검증 - 임베딩 생성 전 registered 상태 확인.

    Args:
        params: 파이프라인 매개변수
            - user_id: 사용자 ID
            - group_id: 그룹 ID
            - role_ids: 역할 ID 목록 (total_role)
            - hash_sha256: 문서 해시값

    Returns:
        dict: 검증된 문서 정보가 추가된 params

    Raises:
        ValueError: 문서를 찾을 수 없거나 상태가 registered가 아닌 경우
    """
    try:
        user_id = params["user_id"]
        group_id = params["group_id"]
        role_ids = params["total_role"]
        hash_sha256 = params["hash_sha256"]

        logger.info(
            f"[validate_document_status] 문서 상태 검증 시작: "
            f"user_id={user_id}, group_id={group_id}, hash={hash_sha256[:8]}..."
        )

        # Milvus meta 컬렉션에서 문서 조회
        with task_async_runner() as runner:
            documents = runner.run(
                select_documents(
                    group_id=group_id,
                    user_id=user_id,
                    role_ids=role_ids,
                    db_type="meta",
                    hash_sha256_option=hash_sha256,
                )
            )

        if not documents:
            error_msg = f"문서를 찾을 수 없습니다: hash={hash_sha256[:8]}..."
            logger.error(f"[validate_document_status] ❌ {error_msg}")
            raise ValueError(error_msg)

        document = documents[0]
        status = document["status"]

        # 조회된 문서의 hash_sha256이 요청한 것과 일치하는지 확인
        doc_hash = document["hash_sha256"]
        if doc_hash != hash_sha256:
            error_msg = (
                f"문서 해시 불일치: 요청={hash_sha256[:16]}..., "
                f"조회={doc_hash[:16]}..."
            )
            logger.error(f"[validate_document_status] ❌ {error_msg}")
            raise ValueError(error_msg)

        logger.info(
            f"[validate_document_status] 문서 조회 완료: "
            f"hash={doc_hash[:16]}..., title={document['title']}, "
            f"category={document['category']}, status={status}"
        )

        # registered 상태 확인
        if status != DocumentStatus.REGISTERED:
            error_msg = (
                f"문서 상태가 '{DocumentStatus.REGISTERED}'가 아닙니다: "
                f"current_status={status}, hash={hash_sha256[:8]}..."
            )
            logger.error(f"[validate_document_status] ❌ {error_msg}")
            raise ValueError(error_msg)

        # 필요한 메타데이터를 params에 추가 (Milvus에서 조회한 정보)
        # chunk_size, chunk_overlap은 API payload에서 전달받은 값만 사용
        params.update(
            {
                "title": document["title"],
                "filename": document["filename"],
                "file_type": document["file_type"],
                "download_url": document["download_url"],
                "category": document["category"],
                "expiration_date": document["expiration_date"],
            }
        )

        logger.info(
            f"[validate_document_status] ✅ 문서 상태 검증 완료: "
            f"title={params['title']}, download_url={params['download_url'][:50]}..."
        )

        return params

    except ValueError:
        raise  # ValueError는 그대로 전달
    except Exception as e:
        logger.error(
            f"[validate_document_status] ❌ 문서 상태 검증 중 오류 발생: {e}",
            exc_info=True,
        )
        raise


@app.task(time_limit=60, soft_time_limit=55, max_retries=3, default_retry_delay=10)
def update_status_to_running(params: dict) -> dict:
    """
    문서 상태를 'running'으로 업데이트

    임베딩 생성 파이프라인 시작 시 호출됩니다.
    클라이언트가 폴링 API를 통해 실행 중인 문서를 감지할 수 있도록 합니다.

    Args:
        params: 파이프라인 매개변수
            - group_id: 그룹 ID
            - hash_sha256: 문서 해시

    Returns:
        dict: 입력받은 params 그대로 반환

    Raises:
        Exception: 상태 업데이트 중 오류 발생 시
    """
    try:
        group_id = params["group_id"]
        user_id = params["user_id"]
        hash_sha256 = params["hash_sha256"]

        logger.info(
            f"[update_status_to_running] 📝 문서 상태를 'running'으로 변경: "
            f"user_id={user_id}, hash={hash_sha256[:16]}..."
        )

        # Milvus meta collection의 status를 'running'으로 업데이트
        with task_async_runner() as runner:
            runner.run(
                update_status(
                    group_id=group_id,
                    user_id=user_id,
                    hash_sha256=hash_sha256,
                    status=DocumentStatus.RUNNING,
                )
            )

        logger.info(
            f"[update_status_to_running] ✅ 문서 상태 변경 완료: "
            f"user_id={user_id}, hash={hash_sha256[:16]}..."
        )

        return params

    except Exception as e:
        logger.error(
            f"[update_status_to_running] ❌ 문서 상태 변경 중 오류 발생: {e}",
            exc_info=True,
        )
        raise
