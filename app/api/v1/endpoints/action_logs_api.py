from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse
import logging

from app.service import action_log_service
from app.dto.action_log_dto import (
    ActionLogListResponseDTO,
    ActionLogResponseDTO,
    LogCleanupResponseDTO,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        400: {"description": "잘못된 요청 - 요청 매개변수가 유효하지 않습니다."},
        401: {"description": "인증 실패 - 유효한 인증 정보가 필요합니다."},
        403: {"description": "권한 부족 - 요청된 작업에 대한 권한이 없습니다."},
        404: {"description": "찾을 수 없음 - 요청된 리소스가 존재하지 않습니다."},
        500: {"description": "서버 오류 - 서버 내부 오류가 발생했습니다."},
    },
)




@router.get(
    "/",
    response_model=ActionLogListResponseDTO,
    summary="액션 로그 목록 조회",
    responses={
        200: {
            "description": "성공적으로 액션 로그 목록을 조회했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "logs": [
                            {
                                "id": 1234,
                                "user_id": 101,
                                "action_type": "UPLOAD",
                                "endpoint": "/v1/embeddings/upload",
                                "http_method": "POST",
                                "status_code": 200,
                                "success": True,
                                "processing_time_ms": 1250.5,
                                "created_at": "2024-03-15T10:30:45Z",
                                "request_body": {"filename": "contract.pdf"},
                                "response_body": {"message": "File uploaded successfully"},
                                "error_message": None
                            }
                        ],
                        "total_count": 150,
                        "page": 1,
                        "page_size": 50,
                        "total_pages": 3
                    }
                }
            }
        }
    },
    description="""
📊 **액션 로그 목록 조회**

조건에 따라 액션 로그를 조회합니다. 페이징, 필터링, 정렬 기능을 제공합니다.

## 필터링 옵션
- **사용자별**: 특정 사용자의 활동만 조회
- **액션 타입별**: READ, CREATE, UPDATE, DELETE, SEARCH, UPLOAD, DOWNLOAD
- **기간별**: 시작 날짜와 종료 날짜로 범위 지정
- **성공 여부**: 성공/실패 요청 필터링

## 페이징
- 최대 1000개까지 한 번에 조회 가능
- 기본값: 50개
    """,
)
async def get_action_logs(
    user_id: Optional[int] = Query(None, description="사용자 ID 필터"),
    action_type: Optional[str] = Query(None, description="액션 타입 필터"),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
    success_only: Optional[bool] = Query(None, description="성공한 요청만 조회"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=1000, description="페이지 크기"),
):
    """
    사용자 활동 로그를 조회합니다.

    Args:
        user_id: 사용자 ID 필터 (선택적)
            - 특정 사용자의 로그만 조회
        action_type: 액션 타입 필터 (선택적)
            - READ, CREATE, UPDATE, DELETE, SEARCH, UPLOAD, DOWNLOAD
        start_date: 시작 날짜 (선택적)
            - ISO 8601 형식 (예: 2024-01-15T10:30:00Z)
        end_date: 종료 날짜 (선택적)
            - ISO 8601 형식
        success_only: 성공 여부 필터 (선택적)
            - True: 성공한 요청만 (status_code < 400)
            - False: 실패한 요청만 (status_code >= 400)
            - None: 모든 요청 포함
        page: 페이지 번호 (기본값: 1)
        page_size: 페이지 크기 (기본값: 50)

    Returns:
        ActionLogListResponseDTO: 페이징된 액션 로그 목록
            - logs: 로그 항목 목록
            - total_count: 총 로그 수
            - page: 현재 페이지
            - page_size: 페이지 크기
            - total_pages: 총 페이지 수

    Raises:
        HTTPException: 로그 조회 실패 시
            - 400: 잘못된 필터 파라미터
            - 500: 데이터베이스 연결 오류, 내부 서버 오류
    """
    try:
        result = await action_log_service.get_action_logs(
            user_id=user_id,
            action_type=action_type,
            start_date=start_date,
            end_date=end_date,
            success_only=success_only,
            page=page,
            page_size=page_size,
        )

        logger.info(f"✅ 액션 로그 목록 조회 완료: {len(result['logs'])}개")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 액션 로그 목록 조회 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="액션 로그 목록 조회 중 오류가 발생했습니다.",
        )


@router.get(
    "/{log_id}",
    response_model=ActionLogResponseDTO,
    summary="특정 액션 로그 조회",
    responses={
        200: {
            "description": "성공적으로 액션 로그를 조회했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1234,
                        "user_id": 101,
                        "action_type": "UPLOAD",
                        "endpoint": "/v1/embeddings/upload",
                        "http_method": "POST",
                        "status_code": 200,
                        "success": True,
                        "processing_time_ms": 1250.5,
                        "created_at": "2024-03-15T10:30:45Z",
                        "request_body": {"filename": "contract.pdf", "category": "계약서"},
                        "response_body": {"message": "File uploaded successfully", "document_id": 5678},
                        "error_message": None,
                        "user_agent": "Mozilla/5.0",
                        "ip_address": "192.168.1.100"
                    }
                }
            }
        }
    },
    description="""
🔍 **특정 액션 로그 상세 조회**

ID로 특정 액션 로그의 상세 정보를 조회합니다.
요청/응답 본문, 에러 메시지 등 전체 정보를 포함합니다.
    """,
)
async def get_action_log_by_id(log_id: int):
    """
    특정 액션 로그의 상세 정보를 조회합니다.

    - **log_id**: 조회할 로그의 ID
    """
    try:
        result = await action_log_service.get_action_log_by_id(log_id)
        logger.info(f"✅ 액션 로그 상세 조회 완료: ID={log_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 액션 로그 상세 조회 중 오류 발생 (ID: {log_id}): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="액션 로그 상세 조회 중 오류가 발생했습니다.",
        )


@router.post(
    "/cleanup",
    response_model=LogCleanupResponseDTO,
    summary="오래된 로그 정리",
    responses={
        200: {
            "description": "성공적으로 오래된 로그를 정리했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "deleted_count": 4523,
                        "before_cleanup": 15678,
                        "after_cleanup": 11155,
                        "days_kept": 90,
                        "cleanup_date": "2024-03-15T14:30:00Z"
                    }
                }
            }
        }
    },
    description="""
🧹 **오래된 로그 정리**

지정된 기간보다 오래된 액션 로그를 삭제합니다. 관리자 권한이 필요합니다.

## 주의사항
⚠️ **이 작업은 되돌릴 수 없습니다. 신중하게 사용하세요.**

## 기본 정책
- 기본 보관 기간: 90일
- 최소 보관 기간: 7일
- 최대 보관 기간: 365일
    """,
)
async def cleanup_old_logs(
    days_to_keep: int = Query(90, description="보관할 일수"),
):
    """
    오래된 액션 로그를 정리합니다.

    - **days_to_keep**: 보관할 일수 (기본값: 90일)

    ⚠️ **주의**: 이 작업은 되돌릴 수 없습니다. 신중하게 사용하세요.
    """
    try:
        result = await action_log_service.cleanup_old_logs(days_to_keep=days_to_keep)

        logger.info(f"✅ 오래된 로그 정리 완료: {result['deleted_count']}개 삭제")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 오래된 로그 정리 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="오래된 로그 정리 중 오류가 발생했습니다.",
        )


@router.get(
    "/export/csv",
    summary="액션 로그 CSV 내보내기",
    responses={
        200: {
            "description": "성공적으로 CSV 데이터를 생성했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "csv_content": "ID,사용자ID,액션타입,엔드포인트,HTTP메서드,상태코드,성공여부,처리시간(ms),생성시간\n1234,101,UPLOAD,/v1/embeddings/upload,POST,200,True,1250.5,2024-03-15T10:30:45Z\n1235,102,SEARCH,/v1/documents/meta,GET,200,True,45.2,2024-03-15T10:31:20Z",
                        "total_records": 2
                    }
                }
            }
        }
    },
    description="""
📥 **액션 로그 CSV 내보내기**

액션 로그를 CSV 형식으로 내보냅니다.

## 제한사항
- 최대 10,000개 레코드까지 내보내기 가능
- 대용량 데이터는 기간을 나누어 내보내기 권장

## CSV 형식
- 헤더: ID, 사용자ID, 액션타입, 엔드포인트, HTTP메서드, 상태코드, 성공여부, 처리시간(ms), 생성시간
- 인코딩: UTF-8
    """,
)
async def export_logs_to_csv(
    user_id: Optional[int] = Query(None, description="사용자 ID 필터"),
    action_type: Optional[str] = Query(None, description="액션 타입 필터"),
    start_date: Optional[datetime] = Query(None, description="시작 날짜"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜"),
):
    """
    액션 로그를 CSV 형식으로 내보냅니다.

    - **user_id**: 특정 사용자의 로그만 내보내기
    - **action_type**: 특정 액션 타입의 로그만 내보내기
    - **start_date**: 시작 날짜 (ISO 8601 형식)
    - **end_date**: 종료 날짜 (ISO 8601 형식)
    """
    try:
        # 대용량 데이터 처리를 위해 제한된 수량으로 조회
        logs_data = await action_log_service.get_action_logs(
            user_id=user_id,
            action_type=action_type,
            start_date=start_date,
            end_date=end_date,
            page=1,
            page_size=10000,  # 최대 10,000개
        )

        # CSV 헤더 생성
        csv_content = "ID,사용자ID,액션타입,엔드포인트,HTTP메서드,상태코드,성공여부,처리시간(ms),생성시간\n"

        # 데이터 행 추가
        for log in logs_data["logs"]:
            csv_content += f"{log['id']},{log['user_id']},{log['action_type']},{log['endpoint']},{log['http_method']},{log['status_code']},{log['success']},{log['processing_time_ms']},{log['created_at']}\n"

        logger.info(f"✅ 액션 로그 CSV 내보내기 완료: {len(logs_data['logs'])}개")

        return JSONResponse(
            content={
                "csv_content": csv_content,
                "total_records": len(logs_data["logs"]),
            },
            headers={"Content-Type": "application/json"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 액션 로그 CSV 내보내기 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="액션 로그 CSV 내보내기 중 오류가 발생했습니다.",
        )
