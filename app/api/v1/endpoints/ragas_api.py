"""RAGAS 검색품질 평가 API"""

import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError

from app.crud.postgres.ragas_evaluation_crud import RagasEvaluationCRUD
from app.crud.postgres.ragas_llm_model_crud import RagasLlmModelCRUD
from app.dto.ragas_dto import (
    RagasEvalDeleteResponseDTO,
    RagasEvalRequestParams,
    RagasEvalStartResponseDTO,
    RagasEvaluationDetailResponseDTO,
    RagasEvaluationListResponseDTO,
)
from app.service.ragas_eval_service import validate_dataset_bytes
from app.utils.auth_utils import get_parsed_jwt_data, get_user_passport_header
from app.worker.ragas_eval_task import run_ragas_evaluation_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/models",
    summary="RAGAS 평가 가능 AI 모델 목록",
    description="평가에 사용할 수 있는 활성 AI 모델 목록을 조회합니다.",
)
async def get_models(
    jwt_data: dict = Depends(get_parsed_jwt_data),
):
    """활성 LLM 모델 목록 조회"""
    crud = RagasLlmModelCRUD()
    models = await crud.select_active_models()
    return {"models": models}


@router.post(
    "/evaluate",
    summary="RAGAS 검색품질 평가 시작",
    response_model=RagasEvalStartResponseDTO,
    status_code=202,
    description="""
골든 데이터셋(Excel)을 업로드하여 검색 파이프라인 평가를 시작합니다.
평가는 백그라운드에서 실행되며, 즉시 evaluation_id를 반환합니다.

## 입력
- **file**: Excel 파일 (.xlsx), sheet명 `dataset`
- **검색 설정**: search_mode, limit, dense_weight, sparse_weight 등 (Form 파라미터)
- **eval_mode**: retrieval (검색 품질) / generation (답변 품질) / all (전체) — 기본값: retrieval
- **llm_model**: 평가 AI 모델 — 기본값: gpt-4o

## 처리 흐름
1. Excel 파일 검증 + DB에 평가 레코드 생성 (status=pending)
2. Celery 태스크로 백그라운드 평가 시작
3. `GET /evaluations/{id}`로 상태 확인 및 결과 조회

## 응답 예시
```json
{"evaluation_id": 5, "status": "pending"}
```
    """,
)
async def evaluate_search_quality(
    request: Request,
    file: UploadFile = File(..., description="골든 데이터셋 Excel 파일 (.xlsx)"),
    search_mode: str = Form(default="hybrid", description="검색 모드 (hybrid / dense)"),
    limit: int = Form(default=10, description="검색 결과 수 (1~100)"),
    dense_weight: float = Form(default=0.7, description="Dense 가중치 (0.0~1.0)"),
    sparse_weight: float = Form(default=0.3, description="Sparse 가중치 (0.0~1.0)"),
    reranker: Optional[str] = Form(default=None, description="flashrank / cohere"),
    rerank_top_n: int = Form(default=10, description="Reranker 최종 반환 수"),
    use_multi_query: bool = Form(default=False, description="LLM 쿼리 확장"),
    threshold: float = Form(default=0.7, description="유사도 커트라인 (0.0~1.0, 미만 결과 제외)"),
    eval_mode: str = Form(default="retrieval", description="평가 모드 (retrieval / generation / all)"),
    llm_model: str = Form(default="gpt-4o", description="평가 AI 모델 (gpt-4o / gpt-4o-mini / gpt-5.4-mini 등)"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> RagasEvalStartResponseDTO:
    """RAGAS 평가를 백그라운드로 시작"""
    # 파일 확장자 검증
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="xlsx 파일만 업로드 가능합니다.")

    # eval_mode 검증
    if eval_mode not in ("retrieval", "generation", "all"):
        raise HTTPException(status_code=422, detail="eval_mode는 retrieval / generation / all 중 하나여야 합니다.")

    # llm_model 검증 (빈 문자열 방지 + 앞뒤 공백 제거)
    llm_model = llm_model.strip() if llm_model else ""
    if not llm_model:
        raise HTTPException(status_code=422, detail="llm_model은 비어있을 수 없습니다.")

    # llm_model DB 검증 (활성 모델만 허용)
    llm_model_crud = RagasLlmModelCRUD()
    if not await llm_model_crud.is_model_active(llm_model):
        raise HTTPException(status_code=422, detail=f"사용할 수 없는 모델입니다: {llm_model}. GET /ragas/models에서 사용 가능한 모델을 확인하세요.")

    try:
        config = RagasEvalRequestParams(
            search_mode=search_mode,
            limit=limit,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            reranker=reranker,
            rerank_top_n=rerank_top_n,
            use_multi_query=use_multi_query,
            threshold=threshold,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    # Excel 파일 읽기
    file_bytes = await file.read()

    # 업로드 즉시 데이터셋 형식 검증 (실패 시 레코드 생성/디스패치 없이 즉시 반려)
    # → 잘못된 파일이 pending 레코드로 남아 화면이 무한 로딩되는 것을 원천 차단
    # 참고: response는 업로드 시 비어 있어도 된다 (generation/all은 평가 시작 시 에이전트로 채움)
    try:
        item_count = validate_dataset_bytes(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"RAGAS 데이터셋 검증 통과: {item_count}건, file={file.filename}")

    # Excel 파일을 base64로 인코딩 (Celery JSON 직렬화 호환)
    dataset_base64 = base64.b64encode(file_bytes).decode("utf-8")

    user_passport = get_user_passport_header(request)

    # DB에 평가 레코드 생성
    crud = RagasEvaluationCRUD()
    evaluation_id = await crud.create_evaluation({
        "user_id": jwt_data["user_id"],
        "group_id": jwt_data["group_id"],
        "eval_mode": eval_mode,
        "llm_model": llm_model,
        "search_config": config.model_dump(),
        "dataset_filename": file.filename,
    })

    # Celery 태스크 디스패치
    task_config = {
        **config.model_dump(),
        "eval_mode": eval_mode,
        "llm_model": llm_model,
        "user_id": jwt_data["user_id"],
        "group_id": jwt_data["group_id"],
        "total_role": jwt_data["total_role"],
        "user_passport": user_passport,
    }
    run_ragas_evaluation_task.delay(evaluation_id, dataset_base64, task_config)

    logger.info(f"RAGAS 평가 시작: evaluation_id={evaluation_id}")
    return RagasEvalStartResponseDTO(evaluation_id=evaluation_id, status="pending")


@router.get(
    "/evaluations",
    summary="RAGAS 평가 목록 조회",
    response_model=RagasEvaluationListResponseDTO,
    description="평가 이력을 페이지네이션으로 조회합니다. 상태/모드로 필터 가능.",
)
async def get_evaluations(
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(default=20, ge=1, le=100, description="페이지당 건수"),
    status: Optional[str] = Query(default=None, description="상태 필터 (pending/running/completed/failed)"),
    eval_mode: Optional[str] = Query(default=None, description="평가 모드 필터 (retrieval/generation/all)"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> RagasEvaluationListResponseDTO:
    """평가 목록 조회"""
    crud = RagasEvaluationCRUD()
    offset = (page - 1) * page_size
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    evaluations = await crud.select_evaluations(
        user_id=user_id,
        group_id=group_id,
        limit=page_size,
        offset=offset,
        status=status,
        eval_mode=eval_mode,
    )

    return {
        "evaluations": evaluations,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": len(evaluations),
            "has_next": len(evaluations) == page_size,
        },
    }


@router.get(
    "/evaluations/{evaluation_id}",
    summary="RAGAS 평가 상세 조회",
    response_model=RagasEvaluationDetailResponseDTO,
    description="평가 결과 상세를 조회합니다. 완료 시 개별 질문 점수(details)가 포함됩니다.",
)
async def get_evaluation_detail(
    evaluation_id: int,
    item_id: Optional[int] = Query(default=None, description="특정 질문 ID로 필터 (미지정 시 전체)"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> RagasEvaluationDetailResponseDTO:
    """평가 상세 조회"""
    crud = RagasEvaluationCRUD()
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]
    result = await crud.select_evaluation_by_id(evaluation_id, user_id=user_id, group_id=group_id, item_id=item_id)
    if result is None:
        raise HTTPException(status_code=404, detail="평가를 찾을 수 없습니다.")
    return result


@router.delete(
    "/evaluations/{evaluation_id}",
    summary="RAGAS 평가 결과 삭제",
    response_model=RagasEvalDeleteResponseDTO,
    description="평가 결과를 삭제합니다. 진행 중(pending/running)인 평가는 삭제할 수 없습니다.",
)
async def delete_evaluation(
    evaluation_id: int,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> RagasEvalDeleteResponseDTO:
    """평가 결과 삭제"""
    crud = RagasEvaluationCRUD()
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]
    try:
        deleted = await crud.delete_evaluation(evaluation_id, user_id=user_id, group_id=group_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if not deleted:
        raise HTTPException(status_code=404, detail="평가를 찾을 수 없습니다.")

    return RagasEvalDeleteResponseDTO(id=evaluation_id, deleted=True)
