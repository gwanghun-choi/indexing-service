"""
RAGAS 평가 결과 CRUD

평가 생성, 상태 갱신, 결과 저장, 목록/상세 조회, 삭제를 담당합니다.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from zoneinfo import ZoneInfo

from app.config.database.session import get_async_db_context, get_async_db_context_for_worker
from app.entity.postgres.ragas_evaluation_entity import (
    RagasEvaluation,
    RagasEvaluationDetail,
)

logger = logging.getLogger(__name__)


class RagasEvaluationCRUD:
    """RAGAS 평가 결과 CRUD 클래스"""

    def __init__(self, *, use_worker_session: bool = False) -> None:
        self._get_db = get_async_db_context_for_worker if use_worker_session else get_async_db_context

    async def create_evaluation(self, data: Dict[str, Any]) -> int:
        """
        평가 레코드 생성 (status=pending)

        Args:
            data: user_id, group_id, eval_mode, llm_model, search_config, dataset_filename

        Returns:
            생성된 evaluation ID
        """
        try:
            async with self._get_db() as db:
                evaluation = RagasEvaluation(
                    user_id=data["user_id"],
                    group_id=data["group_id"],
                    eval_mode=data["eval_mode"],
                    llm_model=data["llm_model"],
                    search_config=data["search_config"],
                    dataset_filename=data["dataset_filename"],
                    status="pending",
                )
                db.add(evaluation)
                await db.flush()
                evaluation_id = evaluation.id
                logger.info(f"RAGAS 평가 생성: id={evaluation_id}")
                return evaluation_id
        except SQLAlchemyError as e:
            logger.error(f"RAGAS 평가 생성 실패: {e}")
            raise

    async def update_status(
        self,
        evaluation_id: int,
        status: str,
        started_at: Optional[datetime] = None,
    ) -> None:
        """
        평가 상태 갱신

        Args:
            evaluation_id: 평가 ID
            status: 변경할 상태 (running, completed, failed)
            started_at: 시작 시각 (running 전환 시)
        """
        try:
            async with self._get_db() as db:
                query = select(RagasEvaluation).where(
                    RagasEvaluation.id == evaluation_id
                )
                result = await db.execute(query)
                evaluation = result.scalar_one_or_none()
                if evaluation is None:
                    raise ValueError(f"평가를 찾을 수 없습니다: id={evaluation_id}")

                evaluation.status = status
                if started_at:
                    evaluation.started_at = started_at
        except SQLAlchemyError as e:
            logger.error(f"RAGAS 평가 상태 갱신 실패: {e}")
            raise

    async def fail_stale_evaluations(
        self,
        pending_before: datetime,
        running_before: datetime,
    ) -> List[int]:
        """오래된 pending/running 평가를 failed로 마감한다 (무한 로딩 방지).

        - pending + started_at IS NULL + created_at < pending_before
          → 작업이 시작되지 못한 고아(orphaned) 레코드
        - running + started_at < running_before
          → 제한 시간을 초과한 레코드

        Args:
            pending_before: 이 시각 이전에 생성된 미시작 pending을 정리
            running_before: 이 시각 이전에 시작된 running을 정리

        Returns:
            failed로 전환된 평가 ID 목록
        """
        failed_ids: List[int] = []
        try:
            async with self._get_db() as db:
                query = select(RagasEvaluation).where(
                    or_(
                        and_(
                            RagasEvaluation.status == "pending",
                            RagasEvaluation.started_at.is_(None),
                            RagasEvaluation.created_at < pending_before,
                        ),
                        and_(
                            RagasEvaluation.status == "running",
                            RagasEvaluation.started_at < running_before,
                        ),
                    )
                )
                result = await db.execute(query)
                now = datetime.now(ZoneInfo("Asia/Seoul"))
                for evaluation in result.scalars().all():
                    if evaluation.status == "pending":
                        evaluation.error_message = (
                            "작업이 시작되지 못해 자동 중단되었습니다(orphaned). "
                            "워커 상태를 확인하거나 다시 시도해 주세요."
                        )
                    else:
                        evaluation.error_message = (
                            "평가가 제한 시간을 초과하여 자동 중단되었습니다."
                        )
                    evaluation.status = "failed"
                    evaluation.completed_at = now
                    failed_ids.append(evaluation.id)

            if failed_ids:
                logger.info(
                    f"RAGAS stale 평가 자동 실패 처리: {failed_ids}"
                )
            return failed_ids
        except SQLAlchemyError as e:
            logger.error(f"RAGAS stale 평가 정리 실패: {e}")
            raise

    async def save_result(
        self,
        evaluation_id: int,
        result_data: Dict[str, Any],
        details: List[Dict[str, Any]],
    ) -> None:
        """
        평가 결과 저장 (summary + details) → status=completed

        Args:
            evaluation_id: 평가 ID
            result_data: summary, by_document, by_category, total_items, duration_seconds
            details: 개별 질문 결과 리스트
        """
        try:
            async with self._get_db() as db:
                query = select(RagasEvaluation).where(
                    RagasEvaluation.id == evaluation_id
                )
                result = await db.execute(query)
                evaluation = result.scalar_one_or_none()
                if evaluation is None:
                    raise ValueError(f"평가를 찾을 수 없습니다: id={evaluation_id}")

                evaluation.summary = result_data["summary"]
                evaluation.by_document = result_data["by_document"]
                evaluation.by_category = result_data["by_category"]
                evaluation.total_items = result_data["total_items"]
                evaluation.duration_seconds = result_data["duration_seconds"]
                evaluation.status = "completed"
                evaluation.completed_at = datetime.now(ZoneInfo("Asia/Seoul"))

                for detail in details:
                    db.add(RagasEvaluationDetail(
                        evaluation_id=evaluation_id,
                        **detail,
                    ))

                logger.info(
                    f"RAGAS 평가 결과 저장 완료: id={evaluation_id}, "
                    f"items={result_data['total_items']}"
                )
        except SQLAlchemyError as e:
            logger.error(f"RAGAS 평가 결과 저장 실패: {e}")
            raise

    async def save_failure(
        self,
        evaluation_id: int,
        error_message: str,
    ) -> None:
        """
        평가 실패 저장 → status=failed

        Args:
            evaluation_id: 평가 ID
            error_message: 에러 메시지
        """
        try:
            async with self._get_db() as db:
                query = select(RagasEvaluation).where(
                    RagasEvaluation.id == evaluation_id
                )
                result = await db.execute(query)
                evaluation = result.scalar_one_or_none()
                if evaluation is None:
                    raise ValueError(f"평가를 찾을 수 없습니다: id={evaluation_id}")

                evaluation.status = "failed"
                evaluation.error_message = error_message
                evaluation.completed_at = datetime.now(ZoneInfo("Asia/Seoul"))

                logger.info(f"RAGAS 평가 실패 기록: id={evaluation_id}")
        except SQLAlchemyError as e:
            logger.error(f"RAGAS 평가 실패 저장 실패: {e}")
            raise

    async def select_evaluations(
        self,
        user_id: int,
        group_id: int,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        eval_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        평가 목록 조회 (페이지네이션 + 필터)

        Args:
            limit: 조회 건수
            offset: 시작 위치
            status: 상태 필터
            eval_mode: 평가 모드 필터

        Returns:
            평가 목록 (details 제외)
        """
        try:
            async with self._get_db() as db:
                query = select(RagasEvaluation)

                conditions = [
                    RagasEvaluation.user_id == user_id,
                    RagasEvaluation.group_id == group_id,
                ]
                if status is not None:
                    conditions.append(RagasEvaluation.status == status)
                if eval_mode is not None:
                    conditions.append(RagasEvaluation.eval_mode == eval_mode)
                query = query.where(and_(*conditions))

                query = query.order_by(RagasEvaluation.created_at.desc())
                query = query.offset(offset).limit(limit)

                result = await db.execute(query)
                evaluations = result.scalars().all()

                return [self._to_list_dict(e) for e in evaluations]
        except SQLAlchemyError as e:
            logger.error(f"RAGAS 평가 목록 조회 실패: {e}")
            raise

    async def select_evaluation_by_id(
        self,
        evaluation_id: int,
        user_id: int,
        group_id: int,
        item_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        평가 상세 조회 (details 포함)

        Args:
            evaluation_id: 평가 ID
            user_id: 사용자 ID
            group_id: 그룹 ID
            item_id: 특정 질문 ID (지정 시 해당 detail만 반환, 미지정 시 전체)

        Returns:
            평가 상세 정보 (details 포함), 없으면 None
        """
        try:
            async with self._get_db() as db:
                query = select(RagasEvaluation).where(
                    and_(
                        RagasEvaluation.id == evaluation_id,
                        RagasEvaluation.user_id == user_id,
                        RagasEvaluation.group_id == group_id,
                    )
                )
                result = await db.execute(query)
                evaluation = result.scalar_one_or_none()
                if evaluation is None:
                    return None

                details_query = (
                    select(RagasEvaluationDetail)
                    .where(RagasEvaluationDetail.evaluation_id == evaluation_id)
                )
                if item_id is not None:
                    details_query = details_query.where(
                        RagasEvaluationDetail.item_id == item_id
                    )
                details_query = details_query.order_by(RagasEvaluationDetail.item_id)

                details_result = await db.execute(details_query)
                details = details_result.scalars().all()

                return self._to_detail_dict(evaluation, details)
        except SQLAlchemyError as e:
            logger.error(f"RAGAS 평가 상세 조회 실패: {e}")
            raise

    async def delete_evaluation(self, evaluation_id: int, user_id: int, group_id: int) -> bool:
        """
        평가 결과 삭제 (details CASCADE)

        Args:
            evaluation_id: 평가 ID

        Returns:
            삭제 성공 여부

        Raises:
            ValueError: 진행 중(pending/running)인 평가 삭제 시도 시
        """
        try:
            async with self._get_db() as db:
                query = select(RagasEvaluation).where(
                    and_(
                        RagasEvaluation.id == evaluation_id,
                        RagasEvaluation.user_id == user_id,
                        RagasEvaluation.group_id == group_id,
                    )
                )
                result = await db.execute(query)
                evaluation = result.scalar_one_or_none()
                if evaluation is None:
                    return False

                if evaluation.status in ("pending", "running"):
                    raise ValueError(
                        f"진행 중인 평가는 삭제할 수 없습니다. (status: {evaluation.status})"
                    )

                await db.delete(evaluation)
                logger.info(f"RAGAS 평가 삭제: id={evaluation_id}")
                return True
        except SQLAlchemyError as e:
            logger.error(f"RAGAS 평가 삭제 실패: {e}")
            raise

    def _to_list_dict(self, e: RagasEvaluation) -> Dict[str, Any]:
        """목록 조회용 딕셔너리 변환 (details 제외)"""
        return {
            "id": e.id,
            "status": e.status,
            "eval_mode": e.eval_mode,
            "llm_model": e.llm_model,
            "summary": e.summary,
            "search_config": e.search_config,
            "total_items": e.total_items,
            "duration_seconds": e.duration_seconds,
            "dataset_filename": e.dataset_filename,
            "created_at": e.created_at,
            "completed_at": e.completed_at,
        }

    def _to_detail_dict(
        self,
        e: RagasEvaluation,
        details: list,
    ) -> Dict[str, Any]:
        """상세 조회용 딕셔너리 변환 (details 포함)"""
        return {
            "id": e.id,
            "status": e.status,
            "eval_mode": e.eval_mode,
            "llm_model": e.llm_model,
            "summary": e.summary,
            "by_document": e.by_document,
            "by_category": e.by_category,
            "search_config": e.search_config,
            "total_items": e.total_items,
            "duration_seconds": e.duration_seconds,
            "dataset_filename": e.dataset_filename,
            "error_message": e.error_message,
            "started_at": e.started_at,
            "completed_at": e.completed_at,
            "created_at": e.created_at,
            "details": [
                {
                    "item_id": d.item_id,
                    "user_input": d.user_input,
                    "category": d.category,
                    "source_document": d.source_document,
                    "source_document_hash": d.source_document_hash,
                    "context_precision": d.context_precision,
                    "context_recall": d.context_recall,
                    "faithfulness": d.faithfulness,
                    "answer_relevancy": d.answer_relevancy,
                    "response": d.response,
                    "reference_contexts": d.reference_contexts,
                    "retrieved_contexts": d.retrieved_contexts,
                    "retrieved_chunks": d.retrieved_chunks,
                    "num_results": d.num_results,
                }
                for d in details
            ],
        }
