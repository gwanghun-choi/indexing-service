from typing import Dict, Optional, Any
from datetime import datetime
import logging
from fastapi import HTTPException, status

from app.crud.postgres.log_crud import ActionLogCRUD

logger = logging.getLogger(__name__)

# 모듈 레벨 CRUD 인스턴스
_crud = ActionLogCRUD()


async def get_action_logs(
    user_id: Optional[int] = None,
    action_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    success_only: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """
    조건에 따라 액션 로그를 조회합니다.

    Args:
        user_id: 사용자 ID 필터
        action_type: 액션 타입 필터
        start_date: 시작 날짜
        end_date: 종료 날짜
        success_only: 성공한 요청만 조회할지 여부
        page: 페이지 번호 (1부터 시작)
        page_size: 페이지 크기

    Returns:
        Dict[str, Any]: 페이징된 액션 로그 목록

    Raises:
        HTTPException: 조회 중 오류 발생 시
    """
    try:
        # 페이징 계산
        offset = (page - 1) * page_size
        limit = page_size

        # 유효성 검사
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페이지 번호는 1 이상이어야 합니다.",
            )

        if page_size < 1 or page_size > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="페이지 크기는 1-1000 사이여야 합니다.",
            )

        # 날짜 유효성 검사
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="시작 날짜는 종료 날짜보다 이전이어야 합니다.",
            )

        # 로그 조회
        logs = await _crud.select_action_logs(
            user_id=user_id,
            action_type=action_type,
            start_date=start_date,
            end_date=end_date,
            success_only=success_only,
            limit=limit,
            offset=offset,
        )

        logger.info(f"액션 로그 조회 완료: {len(logs)}개 조회 ✅")

        return {
            "logs": logs,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": len(logs),
                "has_next": len(logs) == page_size,
            },
            "filters": {
                "user_id": user_id,
                "action_type": action_type,
                "start_date": start_date,
                "end_date": end_date,
                "success_only": success_only,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"액션 로그 조회 중 오류 발생: {str(e)} ❌")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="액션 로그 조회 중 오류가 발생했습니다.",
        )


async def get_action_log_by_id(log_id: int) -> Dict[str, Any]:
    """
    ID로 특정 액션 로그를 조회합니다.

    Args:
        log_id: 로그 ID

    Returns:
        Dict[str, Any]: 액션 로그 정보

    Raises:
        HTTPException: 로그를 찾을 수 없거나 조회 중 오류 발생 시
    """
    try:
        if log_id < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 로그 ID입니다.",
            )

        log = await _crud.select_action_log_by_id(log_id)

        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ID {log_id}에 해당하는 액션 로그를 찾을 수 없습니다.",
            )

        logger.info(f"액션 로그 조회 완료: ID={log_id} ✅")
        return log

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"액션 로그 조회 중 오류 발생 (ID: {log_id}): {str(e)} ❌")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="액션 로그 조회 중 오류가 발생했습니다.",
        )


async def get_user_activity_summary(
    user_id: int, days: int = 30
) -> Dict[str, Any]:
    """
    특정 사용자의 활동 요약을 조회합니다.

    Args:
        user_id: 사용자 ID
        days: 조회할 일수

    Returns:
        Dict[str, Any]: 사용자 활동 요약

    Raises:
        HTTPException: 조회 중 오류 발생 시
    """
    try:
        if user_id < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효하지 않은 사용자 ID입니다.",
            )

        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="조회 일수는 1-365일 사이여야 합니다.",
            )

        summary = await _crud.get_user_activity_summary(
            user_id=user_id, days=days
        )

        # 활동 점수 계산 (간단한 알고리즘)
        activity_score = _calculate_activity_score(summary)
        summary["activity_score"] = activity_score

        logger.info(
            f"사용자 활동 요약 조회 완료: user_id={user_id}, days={days} ✅"
        )
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"사용자 활동 요약 조회 중 오류 발생 (user_id: {user_id}): {str(e)} ❌"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 활동 요약 조회 중 오류가 발생했습니다.",
        )


async def cleanup_old_logs(days_to_keep: int = 90) -> Dict[str, Any]:
    """
    오래된 로그를 정리합니다.

    Args:
        days_to_keep: 보관할 일수

    Returns:
        Dict[str, Any]: 정리 결과

    Raises:
        HTTPException: 정리 중 오류 발생 시
    """
    try:
        if days_to_keep < 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="최소 7일 이상의 로그를 보관해야 합니다.",
            )

        deleted_count = await _crud.cleanup_old_logs(days_to_keep)

        logger.info(f"오래된 로그 정리 완료: {deleted_count}개 삭제 ✅")

        return {
            "deleted_count": deleted_count,
            "days_kept": days_to_keep,
            "cleanup_date": datetime.utcnow(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"오래된 로그 정리 중 오류 발생: {str(e)} ❌")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="오래된 로그 정리 중 오류가 발생했습니다.",
        )


def _calculate_activity_score(summary: Dict[str, Any]) -> int:
    """
    사용자 활동 점수를 계산합니다.

    Args:
        summary: 사용자 활동 요약

    Returns:
        int: 활동 점수 (0-100)
    """
    score = 0

    # 요청 수에 따른 점수 (최대 40점)
    total_requests = summary.get("total_requests", 0)
    score += min(total_requests * 2, 40)

    # 성공률에 따른 점수 (최대 30점)
    success_rate = summary.get("success_rate", 0)
    score += int(success_rate * 0.3)

    # 세션 수에 따른 점수 (최대 20점)
    unique_sessions = summary.get("unique_sessions", 0)
    score += min(unique_sessions * 5, 20)

    # 다양한 액션 타입 사용에 따른 점수 (최대 10점)
    action_types = len(summary.get("action_breakdown", []))
    score += min(action_types * 2, 10)

    return min(score, 100)
