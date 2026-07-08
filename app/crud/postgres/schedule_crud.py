"""
임베딩 스케줄 CRUD

임베딩 자동 실행 스케줄의 데이터베이스 접근 로직을 제공합니다.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any

from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.exc import SQLAlchemyError

from app.config.database.session import (
    get_async_db_context,
    get_async_db_context_for_worker,
)
from app.entity.postgres.schedule import EmbeddingSchedule, ScheduleExecutionHistory

logger = logging.getLogger(__name__)


# ========================================
# 스케줄 CRUD
# ========================================


async def create_schedule(schedule_data: Dict[str, Any]) -> EmbeddingSchedule:
    """
    스케줄 생성

    Args:
        schedule_data: 스케줄 데이터

    Returns:
        EmbeddingSchedule: 생성된 스케줄

    Raises:
        SQLAlchemyError: 데이터베이스 오류
    """
    try:
        async with get_async_db_context() as db:
            schedule = EmbeddingSchedule(**schedule_data)
            db.add(schedule)
            await db.flush()
            await db.refresh(schedule)
            await db.commit()

            logger.info(f"✅ 스케줄 생성 완료: ID={schedule.id}, name={schedule.name}")
            return schedule

    except SQLAlchemyError as e:
        logger.error(f"❌ 스케줄 생성 실패: {e}")
        raise


async def select_schedule_by_id(
    schedule_id: int, user_id: int, group_id: int
) -> Optional[EmbeddingSchedule]:
    """
    스케줄 ID로 스케줄 조회 (권한 검증 포함)

    본인이 생성한 스케줄만 조회 가능합니다.

    Args:
        schedule_id: 스케줄 ID
        user_id: 사용자 ID
        group_id: 그룹 ID

    Returns:
        Optional[EmbeddingSchedule]: 스케줄 (없으면 None)
    """
    try:
        async with get_async_db_context() as db:
            stmt = select(EmbeddingSchedule).where(
                and_(
                    EmbeddingSchedule.id == schedule_id,
                    EmbeddingSchedule.group_id == group_id,
                    EmbeddingSchedule.user_id == user_id,  # 본인이 생성한 것만
                    EmbeddingSchedule.deleted_at.is_(None),
                )
            )

            result = await db.execute(stmt)
            schedule = result.scalar_one_or_none()

            if schedule:
                logger.debug(f"✅ 스케줄 조회 완료: ID={schedule_id}")
            else:
                logger.warning(f"⚠️ 스케줄을 찾을 수 없음: ID={schedule_id}")

            return schedule

    except SQLAlchemyError as e:
        logger.error(f"❌ 스케줄 조회 실패: {e}")
        raise


async def select_schedules_by_group(
    group_id: int,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    is_active: Optional[bool] = None,
) -> tuple[List[EmbeddingSchedule], int]:
    """
    그룹별 스케줄 목록 조회 (페이지네이션)

    본인이 생성한 스케줄만 조회합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        page: 페이지 번호 (1부터 시작)
        per_page: 페이지당 항목 수
        is_active: 활성화 여부 필터 (None이면 전체)

    Returns:
        tuple[List[EmbeddingSchedule], int]: (스케줄 목록, 전체 개수)
    """
    try:
        async with get_async_db_context() as db:
            # 기본 조건: 그룹 + 본인이 생성한 스케줄만
            conditions = [
                EmbeddingSchedule.group_id == group_id,
                EmbeddingSchedule.user_id == user_id,  # 본인이 생성한 것만
                EmbeddingSchedule.deleted_at.is_(None),
            ]

            # 활성화 상태 필터
            if is_active is not None:
                conditions.append(EmbeddingSchedule.is_active == is_active)

            # 전체 개수 조회
            count_stmt = (
                select(func.count())
                .select_from(EmbeddingSchedule)
                .where(and_(*conditions))
            )
            total = await db.scalar(count_stmt)

            # 목록 조회
            stmt = (
                select(EmbeddingSchedule)
                .where(and_(*conditions))
                .order_by(EmbeddingSchedule.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )

            result = await db.execute(stmt)
            schedules = result.scalars().all()

            logger.info(
                f"✅ 스케줄 목록 조회 완료: group_id={group_id}, user_id={user_id}, "
                f"total={total}, page={page}, per_page={per_page}"
            )

            return list(schedules), total

    except SQLAlchemyError as e:
        logger.error(f"❌ 스케줄 목록 조회 실패: {e}")
        raise


async def update_schedule(
    schedule_id: int, user_id: int, group_id: int, update_data: Dict[str, Any]
) -> Optional[EmbeddingSchedule]:
    """
    스케줄 수정

    본인이 생성한 스케줄만 수정 가능합니다.

    Args:
        schedule_id: 스케줄 ID
        user_id: 사용자 ID
        group_id: 그룹 ID
        update_data: 수정할 데이터

    Returns:
        Optional[EmbeddingSchedule]: 수정된 스케줄 (없으면 None)
    """
    try:
        async with get_async_db_context() as db:
            # updated_at 자동 갱신
            update_data["updated_at"] = datetime.now(ZoneInfo("Asia/Seoul"))

            stmt = (
                update(EmbeddingSchedule)
                .where(
                    and_(
                        EmbeddingSchedule.id == schedule_id,
                        EmbeddingSchedule.group_id == group_id,
                        EmbeddingSchedule.user_id == user_id,  # 본인이 생성한 것만
                        EmbeddingSchedule.deleted_at.is_(None),
                    )
                )
                .values(**update_data)
                .returning(EmbeddingSchedule)
            )

            result = await db.execute(stmt)
            await db.commit()
            schedule = result.scalar_one_or_none()

            if schedule:
                logger.info(f"✅ 스케줄 수정 완료: ID={schedule_id}")
            else:
                logger.warning(f"⚠️ 수정할 스케줄을 찾을 수 없음: ID={schedule_id}")

            return schedule

    except SQLAlchemyError as e:
        logger.error(f"❌ 스케줄 수정 실패: {e}")
        raise


async def delete_schedules_soft_bulk(
    schedule_ids: List[int], user_id: int, group_id: int
) -> tuple[List[int], List[int]]:
    """
    스케줄 소프트 삭제 (다중)

    본인이 생성한 스케줄만 삭제 가능합니다.

    Args:
        schedule_ids: 스케줄 ID 리스트
        user_id: 사용자 ID
        group_id: 그룹 ID

    Returns:
        tuple[List[int], List[int]]: (삭제된 ID 리스트, 실패한 ID 리스트)
    """
    if not schedule_ids:
        return [], []

    deleted_ids: List[int] = []
    failed_ids: List[int] = []

    try:
        async with get_async_db_context() as db:
            stmt = (
                update(EmbeddingSchedule)
                .where(
                    and_(
                        EmbeddingSchedule.id.in_(schedule_ids),
                        EmbeddingSchedule.group_id == group_id,
                        EmbeddingSchedule.user_id == user_id,
                        EmbeddingSchedule.deleted_at.is_(None),
                    )
                )
                .values(
                    deleted_at=datetime.now(ZoneInfo("Asia/Seoul")),
                    is_active=False,
                )
                .returning(EmbeddingSchedule.id)
            )

            result = await db.execute(stmt)
            rows = result.fetchall()
            deleted_ids = [row[0] for row in rows]

            deleted_id_set = set(deleted_ids)
            failed_ids = [schedule_id for schedule_id in schedule_ids if schedule_id not in deleted_id_set]

            await db.commit()

            logger.info(
                f"✅ 스케줄 일괄 삭제 완료: "
                f"성공 {len(deleted_ids)}개, 실패 {len(failed_ids)}개"
            )

        return deleted_ids, failed_ids

    except SQLAlchemyError as e:
        logger.error(f"❌ 스케줄 일괄 삭제 실패: {e}")
        raise


async def select_active_schedules_to_run(now: datetime) -> List[EmbeddingSchedule]:
    """
    실행할 활성 스케줄 조회 (Celery Beat용)

    Args:
        now: 현재 시간

    Returns:
        List[EmbeddingSchedule]: 실행할 스케줄 목록
    """
    try:
        async with get_async_db_context_for_worker() as db:
            stmt = select(EmbeddingSchedule).where(
                and_(
                    EmbeddingSchedule.is_active.is_(True),
                    EmbeddingSchedule.deleted_at.is_(None),
                    EmbeddingSchedule.scheduled_at <= now,
                )
            )

            result = await db.execute(stmt)
            schedules = result.scalars().all()

            logger.info(f"✅ 실행할 스케줄 조회 완료: {len(schedules)}개")
            return list(schedules)

    except SQLAlchemyError as e:
        logger.error(f"❌ 실행할 스케줄 조회 실패: {e}")
        raise


async def update_schedule_execution_stats(
    schedule_id: int,
    last_executed_at: datetime,
    success: bool = True,
) -> None:
    """
    스케줄 실행 통계 업데이트

    Args:
        schedule_id: 스케줄 ID
        last_executed_at: 마지막 실행 시간
        success: 성공 여부
    """
    try:
        async with get_async_db_context_for_worker() as db:
            # 기존 스케줄 조회
            schedule = await db.get(EmbeddingSchedule, schedule_id)
            if not schedule:
                logger.warning(f"⚠️ 스케줄을 찾을 수 없음: ID={schedule_id}")
                return

            # 통계 업데이트
            schedule.last_executed_at = last_executed_at
            schedule.total_executions += 1

            if success:
                schedule.successful_executions += 1
            else:
                schedule.failed_executions += 1

            schedule.updated_at = datetime.now(ZoneInfo("Asia/Seoul"))

            await db.commit()

            logger.info(
                f"✅ 스케줄 실행 통계 업데이트 완료: ID={schedule_id}, "
                f"success={success}"
            )

    except SQLAlchemyError as e:
        logger.error(f"❌ 스케줄 실행 통계 업데이트 실패: {e}")
        raise


# ========================================
# 실행 이력 CRUD
# ========================================


async def create_execution_history(
    history_data: Dict[str, Any],
) -> ScheduleExecutionHistory:
    """
    실행 이력 생성

    Args:
        history_data: 실행 이력 데이터

    Returns:
        ScheduleExecutionHistory: 생성된 실행 이력
    """
    try:
        async with get_async_db_context_for_worker() as db:
            history = ScheduleExecutionHistory(**history_data)
            db.add(history)
            await db.flush()
            await db.refresh(history)
            await db.commit()

            logger.info(
                f"✅ 실행 이력 생성 완료: ID={history.id}, schedule_id={history.schedule_id}"
            )
            return history

    except SQLAlchemyError as e:
        logger.error(f"❌ 실행 이력 생성 실패: {e}")
        raise


async def update_execution_history(
    history_id: int, update_data: Dict[str, Any]
) -> Optional[ScheduleExecutionHistory]:
    """
    실행 이력 업데이트

    Args:
        history_id: 실행 이력 ID
        update_data: 업데이트할 데이터

    Returns:
        Optional[ScheduleExecutionHistory]: 업데이트된 실행 이력
    """
    try:
        async with get_async_db_context_for_worker() as db:
            stmt = (
                update(ScheduleExecutionHistory)
                .where(ScheduleExecutionHistory.id == history_id)
                .values(**update_data)
                .returning(ScheduleExecutionHistory)
            )

            result = await db.execute(stmt)
            await db.commit()
            history = result.scalar_one_or_none()

            if history:
                logger.info(f"✅ 실행 이력 업데이트 완료: ID={history_id}")
            else:
                logger.warning(
                    f"⚠️ 업데이트할 실행 이력을 찾을 수 없음: ID={history_id}"
                )

            return history

    except SQLAlchemyError as e:
        logger.error(f"❌ 실행 이력 업데이트 실패: {e}")
        raise


async def select_execution_history_by_schedule(
    schedule_id: int,
    page: int = 1,
    per_page: int = 20,
) -> tuple[List[ScheduleExecutionHistory], int]:
    """
    스케줄별 실행 이력 조회 (페이지네이션)

    Args:
        schedule_id: 스케줄 ID
        page: 페이지 번호
        per_page: 페이지당 항목 수

    Returns:
        tuple[List[ScheduleExecutionHistory], int]: (실행 이력 목록, 전체 개수)
    """
    try:
        async with get_async_db_context() as db:
            # 전체 개수 조회
            count_stmt = (
                select(func.count())
                .select_from(ScheduleExecutionHistory)
                .where(ScheduleExecutionHistory.schedule_id == schedule_id)
            )
            total = await db.scalar(count_stmt)

            # 목록 조회
            stmt = (
                select(ScheduleExecutionHistory)
                .where(ScheduleExecutionHistory.schedule_id == schedule_id)
                .order_by(ScheduleExecutionHistory.execution_time.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )

            result = await db.execute(stmt)
            histories = result.scalars().all()

            logger.info(
                f"✅ 실행 이력 조회 완료: schedule_id={schedule_id}, "
                f"total={total}, page={page}"
            )

            return list(histories), total

    except SQLAlchemyError as e:
        logger.error(f"❌ 실행 이력 조회 실패: {e}")
        raise


async def select_execution_history_by_id(
    history_id: int,
) -> Optional[ScheduleExecutionHistory]:
    """
    실행 이력 ID로 조회

    Args:
        history_id: 실행 이력 ID

    Returns:
        Optional[ScheduleExecutionHistory]: 실행 이력 (없으면 None)
    """
    try:
        async with get_async_db_context() as db:
            history = await db.get(ScheduleExecutionHistory, history_id)

            if history:
                logger.debug(f"✅ 실행 이력 조회 완료: ID={history_id}")
            else:
                logger.warning(f"⚠️ 실행 이력을 찾을 수 없음: ID={history_id}")

            return history

    except SQLAlchemyError as e:
        logger.error(f"❌ 실행 이력 조회 실패: {e}")
        raise


async def delete_old_execution_history(cutoff_date: datetime) -> int:
    """
    오래된 실행 이력 삭제 (정리 작업용)

    Args:
        cutoff_date: 삭제 기준 날짜 (이 날짜 이전 데이터 삭제)

    Returns:
        int: 삭제된 행 수
    """
    try:
        async with get_async_db_context() as db:
            stmt = delete(ScheduleExecutionHistory).where(
                ScheduleExecutionHistory.created_at < cutoff_date
            )

            result = await db.execute(stmt)
            await db.commit()

            logger.info(f"✅ 오래된 실행 이력 삭제 완료: {result.rowcount}개")

            return result.rowcount

    except SQLAlchemyError as e:
        logger.error(f"❌ 오래된 실행 이력 삭제 실패: {e}")
        raise
