"""
임베딩 스케줄 서비스

임베딩 자동 실행 스케줄의 비즈니스 로직을 제공합니다.
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, status
from croniter import croniter

from app.crud.postgres import schedule_crud
from app.crud.milvus.document_crud import validate_documents, select_documents_by_status
from app.dto.document_status import DocumentStatus
from app.dto.schedule_dto import (
    CreateScheduleRequestDTO,
    UpdateScheduleRequestDTO,
    ScheduleResponseDTO,
    ScheduleListResponseDTO,
    ExecutionHistoryResponseDTO,
    ExecuteScheduleResponseDTO,
)
from app.service.embedding_generation_pipeline import run_embedding_generation_pipeline

logger = logging.getLogger(__name__)


class ScheduleService:
    """스케줄 서비스 클래스"""

    def __init__(self):
        """스케줄 서비스 초기화"""
        logger.info("✅ ScheduleService initialized successfully")

    @staticmethod
    def _generate_schedule_name(document_count: int, scheduled_at: datetime) -> str:
        """
        스케줄 이름 자동 생성

        Args:
            document_count: 문서 개수
            scheduled_at: 예약 시간

        Returns:
            str: 생성된 스케줄 이름
        """
        return f"{scheduled_at.strftime('%Y-%m-%d %H:%M')} 임베딩 예약 (문서 {document_count}개)"

    @staticmethod
    def _validate_cron_expression(cron_expr: str) -> bool:
        """
        Cron 표현식 유효성 검증

        Args:
            cron_expr: Cron 표현식

        Returns:
            bool: 유효 여부

        Raises:
            ValueError: 유효하지 않은 Cron 표현식
        """
        try:
            croniter(cron_expr)
            return True
        except Exception as e:
            raise ValueError(f"유효하지 않은 Cron 표현식입니다: {str(e)}")

    async def create_schedule(
        self,
        request: CreateScheduleRequestDTO,
        user_id: int,
        group_id: int,
        total_role: List[int],
    ) -> ScheduleResponseDTO:
        """
        스케줄 생성

        Args:
            request: 스케줄 생성 요청
            user_id: 사용자 ID
            group_id: 그룹 ID
            total_role: 역할 ID 리스트

        Returns:
            ScheduleResponseDTO: 생성된 스케줄 정보

        Raises:
            HTTPException: 생성 실패 시
        """
        try:
            logger.info(
                f"📅 스케줄 생성 시작: user_id={user_id}, "
                f"documents={len(request.document_hashes)}"
            )

            # 1. 문서 검증 (권한 + 상태 확인)
            valid_docs, failed_docs = await validate_documents(
                group_id=group_id,
                user_id=user_id,
                role_ids=total_role,
                hash_sha256_list=request.document_hashes,
            )

            if not valid_docs:
                error_msg = f"유효한 문서가 없습니다. 모든 문서가 실패했습니다 (실패: {len(failed_docs)}개)"
                logger.warning(f"⚠️ {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": error_msg,
                        "failed_count": len(failed_docs),
                        "failed_documents": failed_docs,
                    },
                )

            # 2. Cron 표현식 검증 (있는 경우)
            if request.cron_expression:
                self._validate_cron_expression(request.cron_expression)

            # 3. 스케줄 이름 자동 생성 (없는 경우)
            schedule_name = request.name or self._generate_schedule_name(
                len(valid_docs), request.scheduled_at
            )

            # 4. 임베딩 설정 구성
            embedding_config = {
                "enable_pii_anonymization": request.enable_pii_anonymization,
                "pii_strategy": request.pii_strategy,
                "pii_types": request.pii_types,
                "persona_id": request.persona_id,
                "filter_score": request.filter_score,
            }

            # chunking 객체가 있으면 사용, 없으면 레거시 필드 사용
            if request.chunking:
                embedding_config["chunking"] = request.chunking
            else:
                embedding_config["chunk_size"] = request.chunk_size
                embedding_config["chunk_overlap"] = request.chunk_overlap

            # 5. 스케줄 데이터 구성
            schedule_data = {
                "name": schedule_name,
                "description": request.description,
                "user_id": user_id,
                "group_id": group_id,
                "role_ids": total_role,  # 스케줄 생성자의 역할 정보 저장
                "document_hashes": [doc["hash_sha256"] for doc in valid_docs],
                "scheduled_at": request.scheduled_at,
                "cron_expression": request.cron_expression,
                "timezone": request.timezone,
                "embedding_config": embedding_config,
            }

            # 6. 스케줄 생성
            schedule = await schedule_crud.create_schedule(schedule_data)

            logger.info(f"✅ 스케줄 생성 완료: ID={schedule.id}, name={schedule.name}")

            # 7. 응답 DTO 변환
            return self._to_schedule_response(schedule)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 스케줄 생성 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    async def get_schedule(
        self,
        schedule_id: int,
        user_id: int,
        group_id: int,
    ) -> ScheduleResponseDTO:
        """
        스케줄 상세 조회

        Args:
            schedule_id: 스케줄 ID
            user_id: 사용자 ID
            group_id: 그룹 ID

        Returns:
            ScheduleResponseDTO: 스케줄 정보

        Raises:
            HTTPException: 조회 실패 시
        """
        try:
            schedule = await schedule_crud.select_schedule_by_id(
                schedule_id, user_id, group_id
            )

            if not schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="스케줄을 찾을 수 없습니다.",
                )

            return self._to_schedule_response(schedule)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 스케줄 조회 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    async def get_schedules(
        self,
        user_id: int,
        group_id: int,
        page: int = 1,
        per_page: int = 20,
        is_active: Optional[bool] = None,
    ) -> ScheduleListResponseDTO:
        """
        스케줄 목록 조회

        Args:
            user_id: 사용자 ID
            group_id: 그룹 ID
            page: 페이지 번호
            per_page: 페이지당 항목 수
            is_active: 활성화 여부 필터

        Returns:
            ScheduleListResponseDTO: 스케줄 목록

        Raises:
            HTTPException: 조회 실패 시
        """
        try:
            schedules, total = await schedule_crud.select_schedules_by_group(
                group_id=group_id,
                user_id=user_id,
                page=page,
                per_page=per_page,
                is_active=is_active,
            )

            items = [self._to_schedule_response(schedule) for schedule in schedules]

            return ScheduleListResponseDTO(
                total=total,
                page=page,
                per_page=per_page,
                items=items,
            )

        except Exception as e:
            logger.error(f"❌ 스케줄 목록 조회 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    async def update_schedule(
        self,
        schedule_id: int,
        request: UpdateScheduleRequestDTO,
        user_id: int,
        group_id: int,
    ) -> ScheduleResponseDTO:
        """
        스케줄 수정

        Args:
            schedule_id: 스케줄 ID
            request: 수정 요청
            user_id: 사용자 ID
            group_id: 그룹 ID

        Returns:
            ScheduleResponseDTO: 수정된 스케줄 정보

        Raises:
            HTTPException: 수정 실패 시
        """
        try:
            # 1. 기존 스케줄 조회
            schedule = await schedule_crud.select_schedule_by_id(
                schedule_id, user_id, group_id
            )

            if not schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="스케줄을 찾을 수 없습니다.",
                )

            # 2. 업데이트 데이터 구성
            update_data = {}

            if request.name is not None:
                update_data["name"] = request.name

            if request.description is not None:
                update_data["description"] = request.description

            if request.document_hashes is not None:
                update_data["document_hashes"] = request.document_hashes

            if request.scheduled_at is not None:
                update_data["scheduled_at"] = request.scheduled_at

            if request.cron_expression is not None:
                self._validate_cron_expression(request.cron_expression)
                update_data["cron_expression"] = request.cron_expression

            if request.timezone is not None:
                update_data["timezone"] = request.timezone

            if request.is_active is not None:
                update_data["is_active"] = request.is_active

            # 임베딩 설정 업데이트
            if any(
                [
                    request.chunking is not None,
                    request.chunk_size is not None,
                    request.chunk_overlap is not None,
                    request.enable_pii_anonymization is not None,
                ]
            ):
                embedding_config = schedule.embedding_config.copy()

                # chunking 객체가 있으면 우선 적용 (레거시 필드 제거)
                if request.chunking is not None:
                    embedding_config["chunking"] = request.chunking
                    # chunking 사용 시 레거시 필드 제거
                    embedding_config.pop("chunk_size", None)
                    embedding_config.pop("chunk_overlap", None)
                else:
                    # 레거시 필드 업데이트
                    if request.chunk_size is not None:
                        embedding_config["chunk_size"] = request.chunk_size

                    if request.chunk_overlap is not None:
                        embedding_config["chunk_overlap"] = request.chunk_overlap

                if request.enable_pii_anonymization is not None:
                    embedding_config[
                        "enable_pii_anonymization"
                    ] = request.enable_pii_anonymization

                update_data["embedding_config"] = embedding_config

            # 3. 스케줄 업데이트
            updated_schedule = await schedule_crud.update_schedule(
                schedule_id, user_id, group_id, update_data
            )

            if not updated_schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="스케줄을 찾을 수 없습니다.",
                )

            logger.info(f"✅ 스케줄 수정 완료: ID={schedule_id}")

            return self._to_schedule_response(updated_schedule)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 스케줄 수정 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    async def delete_schedules_bulk(
        self,
        schedule_ids: List[int],
        user_id: int,
        group_id: int,
    ) -> Dict[str, Any]:
        """
        스케줄 삭제 (Soft Delete) - 다중

        Args:
            schedule_ids: 스케줄 ID 리스트
            user_id: 사용자 ID
            group_id: 그룹 ID

        Returns:
            Dict[str, Any]: 삭제 결과 상세 정보

        Raises:
            HTTPException: 삭제 실패 시
        """
        try:
            logger.info(
                f"🗑️ 스케줄 일괄 삭제 시작: user_id={user_id}, "
                f"요청 개수={len(schedule_ids)}"
            )

            # 일괄 삭제 실행
            deleted_ids, failed_ids = await schedule_crud.delete_schedules_soft_bulk(
                schedule_ids, user_id, group_id
            )

            total_requested = len(schedule_ids)
            deleted_count = len(deleted_ids)
            failed_count = len(failed_ids)

            # 메시지 생성
            if deleted_count == total_requested:
                message = f"{deleted_count}개의 스케줄이 성공적으로 삭제되었습니다."
            elif deleted_count > 0:
                message = (
                    f"{deleted_count}개의 스케줄이 삭제되었습니다. "
                    f"({failed_count}개는 권한이 없거나 존재하지 않아 삭제되지 않았습니다.)"
                )
            else:
                message = "삭제할 수 있는 스케줄이 없습니다. 권한을 확인해주세요."

            logger.info(
                f"✅ 스케줄 일괄 삭제 완료: "
                f"성공 {deleted_count}개, 실패 {failed_count}개"
            )

            return {
                "total_requested": total_requested,
                "deleted_count": deleted_count,
                "failed_count": failed_count,
                "deleted_ids": deleted_ids,
                "failed_ids": failed_ids,
                "message": message,
            }

        except Exception as e:
            logger.error(f"❌ 스케줄 일괄 삭제 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    async def execute_schedule(
        self,
        schedule_id: int,
        user_id: int,
        group_id: int,
        total_role: List[int],
    ) -> ExecuteScheduleResponseDTO:
        """
        스케줄 즉시 실행

        Args:
            schedule_id: 스케줄 ID
            user_id: 사용자 ID
            group_id: 그룹 ID
            total_role: 역할 ID 리스트

        Returns:
            ExecuteScheduleResponseDTO: 실행 결과

        Raises:
            HTTPException: 실행 실패 시
        """
        try:
            # 1. 스케줄 조회
            schedule = await schedule_crud.select_schedule_by_id(
                schedule_id, user_id, group_id
            )

            if not schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="스케줄을 찾을 수 없습니다.",
                )

            logger.info(f"🚀 스케줄 즉시 실행 시작: ID={schedule_id}")

            # 2. 문서 상태 검증 (status='registered'인 문서만 처리)
            valid_docs, failed_docs = await validate_documents(
                group_id=group_id,
                hash_sha256_list=schedule.document_hashes,
                user_id=user_id,
                role_ids=total_role,
            )

            if not valid_docs:
                logger.warning(
                    f"⚠️ 스케줄 {schedule_id}: 실행 가능한 문서가 없음 "
                    f"(전체: {len(schedule.document_hashes)}, 실패: {len(failed_docs)})"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="실행 가능한 문서가 없습니다. "
                    "모든 문서가 이미 처리되었거나 상태가 올바르지 않습니다.",
                )

            logger.info(
                f"✅ 문서 검증 완료: 유효 {len(valid_docs)}개, 실패 {len(failed_docs)}개"
            )

            # 3. 실행 이력 생성
            history_data = {
                "schedule_id": schedule_id,
                "execution_time": datetime.utcnow(),
                "status": "running",
                "started_at": datetime.utcnow(),
            }

            history = await schedule_crud.create_execution_history(history_data)

            # 4. 임베딩 파이프라인 실행 (유효한 문서만)
            task_ids = []
            embedding_config = schedule.embedding_config

            for doc in valid_docs:
                task_id = str(uuid.uuid4())
                doc_hash = doc["hash_sha256"]

                payload = {
                    "task_id": task_id,
                    "user_id": user_id,
                    "group_id": group_id,
                    "total_role": total_role,
                    "hash_sha256": doc_hash,
                    "embedding_model": "openai",
                    "model_name": "text-embedding-ada-002",
                    **embedding_config,
                }

                run_embedding_generation_pipeline.apply_async(
                    args=[payload], task_id=task_id
                )

                task_ids.append(task_id)

            # 5. 실행 이력 업데이트
            await schedule_crud.update_execution_history(
                history.id,
                {
                    "documents_processed": len(valid_docs),
                    "task_ids": task_ids,
                },
            )

            logger.info(
                f"✅ 스케줄 즉시 실행 완료: ID={schedule_id}, "
                f"유효 문서 {len(valid_docs)}개, tasks={len(task_ids)}"
            )

            # 메시지 구성
            message = f"{len(valid_docs)}개 문서에 대한 임베딩이 시작되었습니다."
            if failed_docs:
                message += f" ({len(failed_docs)}개 문서는 이미 처리되었거나 상태가 올바르지 않아 제외됨)"

            return ExecuteScheduleResponseDTO(
                execution_id=history.id,
                status="running",
                message=message,
                task_ids=task_ids,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 스케줄 즉시 실행 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    async def get_execution_history(
        self,
        schedule_id: int,
        user_id: int,
        group_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """
        실행 이력 조회

        Args:
            schedule_id: 스케줄 ID
            user_id: 사용자 ID
            group_id: 그룹 ID
            page: 페이지 번호
            per_page: 페이지당 항목 수

        Returns:
            Dict[str, Any]: 실행 이력 목록

        Raises:
            HTTPException: 조회 실패 시
        """
        try:
            # 1. 스케줄 조회 (권한 확인)
            schedule = await schedule_crud.select_schedule_by_id(
                schedule_id, user_id, group_id
            )

            if not schedule:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="스케줄을 찾을 수 없습니다.",
                )

            # 2. 실행 이력 조회
            histories, total = await schedule_crud.select_execution_history_by_schedule(
                schedule_id, page, per_page
            )

            items = [self._to_history_response(history) for history in histories]

            return {
                "total": total,
                "page": page,
                "per_page": per_page,
                "items": items,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 실행 이력 조회 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    @staticmethod
    def _to_schedule_response(schedule) -> ScheduleResponseDTO:
        """ORM 모델을 응답 DTO로 변환"""
        return ScheduleResponseDTO(
            id=schedule.id,
            name=schedule.name,
            description=schedule.description,
            user_id=schedule.user_id,
            group_id=schedule.group_id,
            role_ids=schedule.role_ids,
            document_hashes=schedule.document_hashes,
            document_count=len(schedule.document_hashes),
            scheduled_at=schedule.scheduled_at,
            cron_expression=schedule.cron_expression,
            timezone=schedule.timezone,
            is_active=schedule.is_active,
            embedding_config=schedule.embedding_config,
            last_executed_at=schedule.last_executed_at,
            total_executions=schedule.total_executions,
            successful_executions=schedule.successful_executions,
            failed_executions=schedule.failed_executions,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

    @staticmethod
    def _to_history_response(history) -> ExecutionHistoryResponseDTO:
        """ORM 모델을 응답 DTO로 변환"""
        return ExecutionHistoryResponseDTO(
            id=history.id,
            schedule_id=history.schedule_id,
            execution_time=history.execution_time,
            status=history.status,
            documents_processed=history.documents_processed,
            documents_success=history.documents_success,
            documents_failed=history.documents_failed,
            task_ids=history.task_ids,
            started_at=history.started_at,
            completed_at=history.completed_at,
            duration_seconds=history.duration_seconds,
            error_message=history.error_message,
            created_at=history.created_at,
        )

    async def get_scheduled_documents(
        self, user_id: int, group_id: int
    ) -> Dict[str, Any]:
        """
        현재 실행 중인 문서 조회

        Milvus meta collection에서 status='running'인 문서를 조회합니다.
        클라이언트가 1분마다 호출하여 임베딩이 시작된 문서를 감지합니다.

        Args:
            user_id: 사용자 ID
            group_id: 그룹 ID

        Returns:
            Dict[str, Any]: 실행 중인 문서 목록
                - documents: 문서 딕셔너리 (hash_sha256: 문서정보)
                - total_running: 실행 중인 문서 수

        Raises:
            HTTPException: 조회 실패 시
        """
        try:
            # Milvus meta collection에서 status='running'인 문서 조회
            running_docs = await select_documents_by_status(
                group_id=group_id,
                status=DocumentStatus.RUNNING,
                limit=1000,
            )

            # 문서를 hash_sha256을 키로 하는 딕셔너리로 변환
            documents_dict = {}
            for doc in running_docs:
                hash_sha256 = doc.get("hash_sha256")
                if hash_sha256:
                    documents_dict[hash_sha256] = {
                        "hash_sha256": hash_sha256,
                        "title": doc.get("title", "제목 없음"),
                        "filename": doc.get("filename", "파일명 없음"),
                        "status": "running",
                        "user_id": doc.get("user_id"),
                    }

            logger.info(
                f"✅ 실행 중인 문서 조회 완료: user_id={user_id}, "
                f"group_id={group_id}, 문서 수={len(documents_dict)}"
            )

            return {
                "documents": documents_dict,
                "total_running": len(documents_dict),
            }

        except Exception as e:
            logger.error(f"❌ 실행 중인 문서 조회 실패: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

