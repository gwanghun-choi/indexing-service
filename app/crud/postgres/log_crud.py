from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import logging
from sqlalchemy import text, select, func, and_
from sqlalchemy.exc import SQLAlchemyError

from app.config.database.session import get_async_db_context
from app.entity.postgres.action_log_entity import UserActionLog

logger = logging.getLogger(__name__)


class ActionLogCRUD:
    """
    사용자 액션 로그 CRUD 작업을 담당하는 클래스

    로그 저장, 조회, 통계, 분석 기능을 제공합니다.
    """

    def _parse_json_field(self, value: Any) -> Optional[Dict[str, Any]]:
        """
        JSON 문자열을 딕셔너리로 파싱하는 헬퍼 메서드

        Args:
            value: 파싱할 값 (문자열, 딕셔너리, 또는 None)

        Returns:
            Optional[Dict[str, Any]]: 파싱된 딕셔너리 또는 None
        """
        if value is None:
            return None

        # 이미 딕셔너리인 경우 그대로 반환
        if isinstance(value, dict):
            return value

        # 문자열인 경우 JSON 파싱 시도
        if isinstance(value, str):
            try:
                # 빈 문자열이나 'null' 처리
                if value.strip() == "" or value.strip().lower() == "null":
                    return None

                # JSON 파싱
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else None
            except (json.JSONDecodeError, ValueError):
                # JSON 파싱 실패 시 None 반환
                logger.warning(f"JSON 파싱 실패: {value}")
                return None

        # 기타 타입은 None으로 처리
        return None

    async def create_action_log(self, log_data: Dict[str, Any]) -> Optional[int]:
        """
        새로운 액션 로그를 생성합니다.

        Args:
            log_data: 로그 데이터 딕셔너리

        Returns:
            Optional[int]: 생성된 로그의 ID, 실패 시 None

        Raises:
            Exception: 데이터베이스 작업 중 오류 발생 시
        """
        try:
            async with get_async_db_context() as db:
                action_log = UserActionLog(**log_data)
                db.add(action_log)
                await db.commit()
                await db.refresh(action_log)

                logger.debug(f"액션 로그 생성 완료: ID={action_log.id}")
                return action_log.id

        except SQLAlchemyError as e:
            logger.error(f"액션 로그 생성 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"액션 로그 생성 중 예상치 못한 오류: {e}")
            raise

    async def select_action_logs(
        self,
        user_id: Optional[int] = None,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        success_only: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        조건에 따라 액션 로그를 조회합니다.

        Args:
            user_id: 사용자 ID 필터
            action_type: 액션 타입 필터
            start_date: 시작 날짜
            end_date: 종료 날짜
            success_only: 성공한 요청만 조회할지 여부
            limit: 조회할 최대 개수
            offset: 조회 시작 위치

        Returns:
            List[Dict[str, Any]]: 액션 로그 목록

        Raises:
            Exception: 데이터베이스 조회 중 오류 발생 시
        """
        try:
            async with get_async_db_context() as db:
                query = select(UserActionLog)

                # 필터 조건 추가
                conditions = []

                if user_id is not None:
                    conditions.append(UserActionLog.user_id == user_id)

                if action_type is not None:
                    conditions.append(UserActionLog.action_type == action_type)

                if start_date is not None:
                    conditions.append(UserActionLog.created_at >= start_date)

                if end_date is not None:
                    conditions.append(UserActionLog.created_at <= end_date)

                if success_only is not None:
                    if success_only:
                        conditions.append(UserActionLog.success == "SUCCESS")
                    else:
                        conditions.append(UserActionLog.success != "SUCCESS")

                if conditions:
                    query = query.where(and_(*conditions))

                # 정렬 및 페이징
                query = query.order_by(UserActionLog.created_at.desc())
                query = query.offset(offset).limit(limit)

                result = await db.execute(query)
                logs = result.scalars().all()

                # 딕셔너리 형태로 변환
                return [
                    {
                        "id": log.id,
                        "user_id": log.user_id,
                        "group_id": log.group_id,
                        "role_id": log.role_id,
                        "action_type": log.action_type,
                        "endpoint": log.endpoint,
                        "http_method": log.http_method,
                        "document_id": log.document_id,
                        "document_title": log.document_title,
                        "document_category": log.document_category,
                        "file_name": log.file_name,
                        "file_type": log.file_type,
                        "file_size": log.file_size,
                        "action_details": self._parse_json_field(log.action_details),
                        "request_params": self._parse_json_field(log.request_params),
                        "changes_made": self._parse_json_field(log.changes_made),
                        "search_query": log.search_query,
                        "search_results_count": log.search_results_count,
                        "use_reranker": log.use_reranker,
                        "status_code": log.status_code,
                        "success": log.success,
                        "error_message": log.error_message,
                        "error_type": log.error_type,
                        "tokens_used": log.tokens_used,
                        "cost_incurred": log.cost_incurred,
                        "processing_time_ms": log.processing_time_ms,
                        "ip_address": log.ip_address,
                        "user_agent": log.user_agent,
                        "session_id": log.session_id,
                        "task_id": log.task_id,
                        "request_id": log.request_id,
                        "created_at": log.created_at,
                        "request_start_time": log.request_start_time,
                        "request_end_time": log.request_end_time,
                    }
                    for log in logs
                ]

        except SQLAlchemyError as e:
            logger.error(f"액션 로그 조회 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"액션 로그 조회 중 예상치 못한 오류: {e}")
            raise

    async def select_action_log_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        """
        ID로 특정 액션 로그를 조회합니다.

        Args:
            log_id: 로그 ID

        Returns:
            Optional[Dict[str, Any]]: 액션 로그 정보, 없으면 None

        Raises:
            Exception: 데이터베이스 조회 중 오류 발생 시
        """
        try:
            async with get_async_db_context() as db:
                query = select(UserActionLog).where(UserActionLog.id == log_id)
                result = await db.execute(query)
                log = result.scalar_one_or_none()

                if not log:
                    return None

                return {
                    "id": log.id,
                    "user_id": log.user_id,
                    "group_id": log.group_id,
                    "role_id": log.role_id,
                    "action_type": log.action_type,
                    "endpoint": log.endpoint,
                    "http_method": log.http_method,
                    "document_id": log.document_id,
                    "document_title": log.document_title,
                    "document_category": log.document_category,
                    "file_name": log.file_name,
                    "file_type": log.file_type,
                    "file_size": log.file_size,
                    "action_details": self._parse_json_field(log.action_details),
                    "request_params": self._parse_json_field(log.request_params),
                    "changes_made": self._parse_json_field(log.changes_made),
                    "search_query": log.search_query,
                    "search_results_count": log.search_results_count,
                    "use_reranker": log.use_reranker,
                    "status_code": log.status_code,
                    "success": log.success,
                    "error_message": log.error_message,
                    "error_type": log.error_type,
                    "tokens_used": log.tokens_used,
                    "cost_incurred": log.cost_incurred,
                    "processing_time_ms": log.processing_time_ms,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "session_id": log.session_id,
                    "task_id": log.task_id,
                    "request_id": log.request_id,
                    "created_at": log.created_at,
                    "request_start_time": log.request_start_time,
                    "request_end_time": log.request_end_time,
                }

        except SQLAlchemyError as e:
            logger.error(f"액션 로그 조회 실패 (ID: {log_id}): {e}")
            raise
        except Exception as e:
            logger.error(f"액션 로그 조회 중 예상치 못한 오류 (ID: {log_id}): {e}")
            raise

    async def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """
        오래된 로그를 정리합니다.

        Args:
            days_to_keep: 보관할 일수 (기본 90일)

        Returns:
            int: 삭제된 로그 개수

        Raises:
            Exception: 데이터베이스 작업 중 오류 발생 시
        """
        try:
            cutoff_date = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(
                days=days_to_keep
            )

            async with get_async_db_context() as db:
                # 삭제할 로그 개수 확인
                count_query = select(func.count()).where(
                    UserActionLog.created_at < cutoff_date
                )
                count_result = await db.execute(count_query)
                delete_count = count_result.scalar()

                if delete_count > 0:
                    # 로그 삭제
                    delete_query = text(
                        "DELETE FROM indexing.indexing_action_logs WHERE created_at < :cutoff_date"
                    )
                    await db.execute(delete_query, {"cutoff_date": cutoff_date})
                    await db.commit()

                    logger.info(
                        f"오래된 액션 로그 {delete_count}개 삭제 완료 (기준일: {cutoff_date})"
                    )

                return delete_count

        except SQLAlchemyError as e:
            logger.error(f"오래된 로그 정리 실패: {e}")
            raise
        except Exception as e:
            logger.error(f"오래된 로그 정리 중 예상치 못한 오류: {e}")
            raise
