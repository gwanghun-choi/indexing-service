"""
임베딩 스케줄 API

임베딩 자동 실행 스케줄 관리 API 엔드포인트를 제공합니다.
"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query, status

from app.dto.schedule_dto import (
    CreateScheduleRequestDTO,
    UpdateScheduleRequestDTO,
    DeleteScheduleRequestDTO,
    DeleteScheduleResponseDTO,
    ScheduleResponseDTO,
    ScheduleListResponseDTO,
    ExecuteScheduleResponseDTO,
    MessageResponseDTO,
)
from app.service.schedule_service import ScheduleService
from app.utils.auth_utils import get_parsed_jwt_data

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

# 서비스 인스턴스
schedule_service = ScheduleService()


@router.post(
    "",
    summary="스케줄 생성 (임베딩 예약)",
    response_model=ScheduleResponseDTO,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "스케줄이 성공적으로 생성되었습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "name": "2025-10-31 14:00 임베딩 예약 (문서 5개)",
                        "scheduled_at": "2025-10-31T14:00:00+09:00",
                        "is_active": True,
                        "document_count": 5,
                    }
                }
            },
        },
        400: {
            "description": "잘못된 요청 - 유효한 문서가 없거나 Cron 표현식이 잘못되었습니다.",
        },
    },
    description="""
📅 **임베딩 스케줄 생성 (예약)**

사용자가 선택한 문서들을 특정 시간에 자동으로 임베딩 처리하도록 예약합니다.

## 청킹 전략 (chunking)

| 전략 | 설명 | 주요 파라미터 |
|------|------|--------------|
| `fixed` | 고정 크기 분할 (기본) | `chunk_size`, `chunk_overlap` |
| `semantic` | 의미 기반 분할 | `similarity_threshold`, `max_chunk_size` |

## 사용 예시 - 1회성 예약 (Semantic Chunking)
```bash
curl -X POST "http://localhost:8002/api/v1/schedules" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "document_hashes": ["abc123...", "def456..."],
    "scheduled_at": "2025-10-31T14:00:00",
    "chunking": {
      "strategy": "semantic",
      "similarity_threshold": 0.5,
      "max_chunk_size": 1500
    },
    "enable_pii_anonymization": false
  }'
```

## 사용 예시 - 반복 스케줄 (Fixed Chunking)
```bash
curl -X POST "http://localhost:8002/api/v1/schedules" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "매일 새벽 임베딩",
    "document_hashes": ["abc123...", "def456..."],
    "scheduled_at": "2025-11-01T02:00:00",
    "cron_expression": "0 2 * * *",
    "chunking": {
      "strategy": "fixed",
      "chunk_size": 500,
      "chunk_overlap": 50
    },
    "enable_pii_anonymization": false
  }'
```

## 하위 호환 (Legacy)
기존 방식도 지원하지만, 새로운 `chunking` 객체 사용을 권장합니다.
```json
{
  "chunk_size": 500,
  "chunk_overlap": 50
}
```

## 처리 흐름
1. 문서 권한 및 상태 검증 (`status='registered'` 확인)
2. Cron 표현식 검증 (반복 스케줄인 경우)
3. 스케줄 이름 자동 생성 (미입력 시)
4. PostgreSQL에 스케줄 정보 저장
5. Celery Beat가 해당 시간에 자동 실행

## 주요 특징
- **1회성 예약**: `scheduled_at`만 설정
- **반복 스케줄**: `cron_expression` 추가 설정
- **자동 이름 생성**: 이름 미입력 시 시스템이 자동 생성
- **문서 검증**: 권한 없거나 상태가 잘못된 문서는 제외
    """,
)
async def create_schedule(
    request: CreateScheduleRequestDTO,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ScheduleResponseDTO:
    """
    스케줄 생성

    Args:
        request: 스케줄 생성 요청
        jwt_data: JWT 인증 정보

    Returns:
        ScheduleResponseDTO: 생성된 스케줄 정보
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]
    total_role = jwt_data["total_role"]

    logger.info(f"📅 스케줄 생성 요청: user_id={user_id}, group_id={group_id}")

    return await schedule_service.create_schedule(
        request, user_id, group_id, total_role
    )


@router.get(
    "",
    summary="스케줄 목록 조회",
    response_model=ScheduleListResponseDTO,
    responses={
        200: {
            "description": "스케줄 목록이 성공적으로 반환되었습니다.",
        }
    },
    description="""
📋 **스케줄 목록 조회**

현재 그룹의 모든 스케줄 목록을 페이지네이션과 함께 조회합니다.

## 필터링
- `is_active`: 활성화 여부로 필터링 (true, false, null)

## 정렬
- 최신 생성순으로 정렬

## 페이지네이션
- `page`: 페이지 번호 (기본: 1)
- `per_page`: 페이지당 항목 수 (기본: 20, 최대: 100)
    """,
)
async def get_schedules(
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    is_active: Optional[bool] = Query(None, description="활성화 여부 필터"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ScheduleListResponseDTO:
    """
    스케줄 목록 조회

    Args:
        page: 페이지 번호
        per_page: 페이지당 항목 수
        is_active: 활성화 여부 필터
        jwt_data: JWT 인증 정보

    Returns:
        ScheduleListResponseDTO: 스케줄 목록
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    logger.info(
        f"📋 스케줄 목록 조회 요청: user_id={user_id}, "
        f"group_id={group_id}, page={page}"
    )

    return await schedule_service.get_schedules(
        user_id, group_id, page, per_page, is_active
    )


@router.get(
    "/scheduled-documents",
    summary="현재 실행 중인 문서 조회 (SSE 연결용)",
    response_model=Dict[str, Any],
    responses={
        200: {
            "description": "실행 중인 문서 목록이 성공적으로 반환되었습니다.",
        }
    },
    description="""
🔄 **현재 실행 중인 문서 조회**

클라이언트가 1분마다 호출하여 임베딩이 실행 중인 문서를 감지합니다.

## 사용 시나리오
1. 사용자가 임베딩 관련 페이지 접속
2. 클라이언트가 1분마다 이 API 호출
3. status='running'인 문서가 있으면 반환
4. 클라이언트가 해당 문서에 대해 SSE 연결:
   - `/sse/pipeline/document/{user_id}/{hash_sha256}`

## 반환 정보
- hash_sha256: 문서 해시
- title: 문서 제목
- filename: 파일명
- status: 항상 'running'

## 예시 응답
```json
{
  "documents": {
    "abc123...": {
      "hash_sha256": "abc123...",
      "title": "문서1.pdf",
      "filename": "document1.pdf",
      "status": "running"
    }
  },
  "total_running": 1
}
```

## 주의사항
- 임베딩이 완료되면 status가 'uploaded'로 변경되어 목록에서 제외됨
- 실패한 경우 status가 'failed'로 변경되어 목록에서 제외됨
    """,
)
async def get_scheduled_documents(
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """
    현재 실행 중인 문서 조회

    Args:
        jwt_data: JWT 인증 정보

    Returns:
        Dict[str, Any]: 실행 중인 문서 목록
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    logger.info(f"🔄 실행 중인 문서 조회 요청: user_id={user_id}, group_id={group_id}")

    return await schedule_service.get_scheduled_documents(user_id, group_id)


@router.get(
    "/{schedule_id}",
    summary="스케줄 상세 조회",
    response_model=ScheduleResponseDTO,
    responses={
        200: {
            "description": "스케줄 정보가 성공적으로 반환되었습니다.",
        },
        404: {
            "description": "스케줄을 찾을 수 없습니다.",
        },
    },
    description="""
🔍 **스케줄 상세 조회**

특정 스케줄의 상세 정보를 조회합니다.

## 반환 정보
- 기본 정보 (이름, 설명, 예약 시간)
- 문서 목록 (hash_sha256)
- 임베딩 설정
- 실행 통계 (총 실행 횟수, 성공/실패 횟수)
- 메타데이터 (생성일, 수정일)
    """,
)
async def get_schedule(
    schedule_id: int,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ScheduleResponseDTO:
    """
    스케줄 상세 조회

    Args:
        schedule_id: 스케줄 ID
        jwt_data: JWT 인증 정보

    Returns:
        ScheduleResponseDTO: 스케줄 정보
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    logger.info(
        f"🔍 스케줄 상세 조회 요청: schedule_id={schedule_id}, user_id={user_id}"
    )

    return await schedule_service.get_schedule(schedule_id, user_id, group_id)


@router.put(
    "/{schedule_id}",
    summary="스케줄 수정",
    response_model=ScheduleResponseDTO,
    responses={
        200: {
            "description": "스케줄이 성공적으로 수정되었습니다.",
        },
        404: {
            "description": "스케줄을 찾을 수 없습니다.",
        },
    },
    description="""
✏️ **스케줄 수정**

기존 스케줄의 설정을 수정합니다.

## 수정 가능 항목
- 스케줄 이름
- 설명
- 문서 목록
- 예약 시간
- Cron 표현식
- 청킹 설정 (`chunking` 객체)
- 활성화 여부

## 청킹 설정 수정 예시
```json
{
  "chunking": {
    "strategy": "semantic",
    "similarity_threshold": 0.6,
    "max_chunk_size": 2000
  }
}
```

## 주의사항
- 수정하지 않을 항목은 요청에서 생략하면 됩니다 (부분 업데이트)
- `chunking` 설정 시 기존 `chunk_size`/`chunk_overlap` 값은 무시됩니다
- 이미 실행된 이력은 영향받지 않습니다
    """,
)
async def update_schedule(
    schedule_id: int,
    request: UpdateScheduleRequestDTO,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ScheduleResponseDTO:
    """
    스케줄 수정

    Args:
        schedule_id: 스케줄 ID
        request: 수정 요청
        jwt_data: JWT 인증 정보

    Returns:
        ScheduleResponseDTO: 수정된 스케줄 정보
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    logger.info(f"✏️ 스케줄 수정 요청: schedule_id={schedule_id}, user_id={user_id}")

    return await schedule_service.update_schedule(
        schedule_id, request, user_id, group_id
    )


@router.delete(
    "",
    summary="스케줄 삭제 (단일/다중)",
    response_model=DeleteScheduleResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "스케줄이 성공적으로 삭제되었습니다.",
            "content": {
                "application/json": {
                    "examples": {
                        "single": {
                            "summary": "단일 스케줄 삭제",
                            "value": {
                                "total_requested": 1,
                                "deleted_count": 1,
                                "failed_count": 0,
                                "deleted_ids": [1],
                                "failed_ids": [],
                                "message": "1개의 스케줄이 성공적으로 삭제되었습니다.",
                            },
                        },
                        "multiple": {
                            "summary": "다중 스케줄 삭제",
                            "value": {
                                "total_requested": 5,
                                "deleted_count": 5,
                                "failed_count": 0,
                                "deleted_ids": [1, 2, 3, 4, 5],
                                "failed_ids": [],
                                "message": "5개의 스케줄이 성공적으로 삭제되었습니다.",
                            },
                        },
                        "partial": {
                            "summary": "부분 성공",
                            "value": {
                                "total_requested": 5,
                                "deleted_count": 3,
                                "failed_count": 2,
                                "deleted_ids": [1, 2, 3],
                                "failed_ids": [4, 5],
                                "message": "3개의 스케줄이 삭제되었습니다. (2개는 권한이 없거나 존재하지 않아 삭제되지 않았습니다.)",
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "잘못된 요청 - 스케줄 ID 리스트가 유효하지 않습니다.",
        },
    },
    description="""
🗑️ **스케줄 삭제 (단일/다중)**

하나 또는 여러 스케줄을 삭제합니다 (Soft Delete).

## 동작
- 실제 데이터는 삭제되지 않고 `deleted_at` 컬럼이 업데이트됩니다
- 자동으로 `is_active = false`로 변경됩니다
- 실행 이력은 유지됩니다
- 삭제된 스케줄은 목록 조회에서 제외됩니다
- **본인이 생성한 스케줄만 삭제 가능**합니다

## 사용 예시 - 단일 삭제
```bash
curl -X DELETE "http://localhost:8002/api/v1/schedules" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "schedule_ids": [1]
  }'
```

## 사용 예시 - 다중 삭제
```bash
curl -X DELETE "http://localhost:8002/api/v1/schedules" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "schedule_ids": [1, 2, 3, 4, 5]
  }'
```

## 주의사항
- 권한이 없거나 존재하지 않는 스케줄은 삭제되지 않고 `failed_ids`에 포함됩니다
- 부분 성공 시에도 200 상태 코드를 반환하며, 응답에 성공/실패 내역이 포함됩니다
    """,
)
async def delete_schedules(
    request: DeleteScheduleRequestDTO,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> DeleteScheduleResponseDTO:
    """
    스케줄 삭제 (단일/다중)

    Args:
        request: 삭제 요청 (스케줄 ID 리스트)
        jwt_data: JWT 인증 정보

    Returns:
        DeleteScheduleResponseDTO: 삭제 결과 상세 정보
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    logger.info(
        f"🗑️ 스케줄 삭제 요청: user_id={user_id}, "
        f"스케줄 개수={len(request.schedule_ids)}"
    )

    result = await schedule_service.delete_schedules_bulk(
        request.schedule_ids, user_id, group_id
    )

    return DeleteScheduleResponseDTO(**result)


@router.patch(
    "/{schedule_id}/cancel",
    summary="스케줄 취소 (비활성화)",
    response_model=MessageResponseDTO,
    responses={
        200: {
            "description": "스케줄이 성공적으로 취소되었습니다.",
        },
        404: {
            "description": "스케줄을 찾을 수 없습니다.",
        },
    },
    description="""
⏸️ **스케줄 취소 (비활성화)**

스케줄을 취소합니다 (삭제하지 않고 비활성화).

## 동작
- `is_active = false`로 변경
- 스케줄 데이터는 유지
- 실행 이력은 유지
- 필요 시 다시 활성화 가능 (수정 API 사용)
    """,
)
async def cancel_schedule(
    schedule_id: int,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> MessageResponseDTO:
    """
    스케줄 취소 (비활성화)

    Args:
        schedule_id: 스케줄 ID
        jwt_data: JWT 인증 정보

    Returns:
        MessageResponseDTO: 취소 결과 메시지
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    logger.info(f"⏸️ 스케줄 취소 요청: schedule_id={schedule_id}, user_id={user_id}")

    # 스케줄 수정 API를 활용하여 is_active = False로 변경
    request = UpdateScheduleRequestDTO(is_active=False)
    await schedule_service.update_schedule(schedule_id, request, user_id, group_id)

    return MessageResponseDTO(message="스케줄이 성공적으로 취소되었습니다.")


@router.post(
    "/{schedule_id}/execute",
    summary="스케줄 즉시 실행",
    response_model=ExecuteScheduleResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {
            "description": "스케줄 실행이 시작되었습니다.",
        },
        404: {
            "description": "스케줄을 찾을 수 없습니다.",
        },
    },
    description="""
⚡ **스케줄 즉시 실행**

예약된 시간을 기다리지 않고 스케줄을 즉시 실행합니다.

## 동작
1. 스케줄에 등록된 문서들을 조회
2. 각 문서에 대해 임베딩 파이프라인 시작
3. Celery 태스크 ID 목록 반환
4. 실행 이력에 기록

## 주의사항
- 예약된 시간이 지나지 않아도 즉시 실행됩니다
- 다음 예약 시간에도 정상적으로 실행됩니다
- WebSocket으로 실시간 진행 상황 확인 가능
    """,
)
async def execute_schedule(
    schedule_id: int,
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> ExecuteScheduleResponseDTO:
    """
    스케줄 즉시 실행

    Args:
        schedule_id: 스케줄 ID
        jwt_data: JWT 인증 정보

    Returns:
        ExecuteScheduleResponseDTO: 실행 결과
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]
    total_role = jwt_data["total_role"]

    logger.info(
        f"⚡ 스케줄 즉시 실행 요청: schedule_id={schedule_id}, user_id={user_id}"
    )

    return await schedule_service.execute_schedule(
        schedule_id, user_id, group_id, total_role
    )


@router.get(
    "/{schedule_id}/history",
    summary="스케줄 실행 이력 조회",
    response_model=Dict[str, Any],
    responses={
        200: {
            "description": "실행 이력이 성공적으로 반환되었습니다.",
        },
        404: {
            "description": "스케줄을 찾을 수 없습니다.",
        },
    },
    description="""
📊 **스케줄 실행 이력 조회**

특정 스케줄의 실행 이력을 조회합니다.

## 반환 정보
- 실행 시간
- 실행 상태 (running, success, failed, cancelled)
- 처리된 문서 수
- 성공/실패 문서 수
- Celery 태스크 ID 목록
- 실행 소요 시간
- 에러 메시지 (실패한 경우)

## 페이지네이션
- 최근 실행 이력부터 정렬되어 반환
    """,
)
async def get_execution_history(
    schedule_id: int,
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """
    스케줄 실행 이력 조회

    Args:
        schedule_id: 스케줄 ID
        page: 페이지 번호
        per_page: 페이지당 항목 수
        jwt_data: JWT 인증 정보

    Returns:
        Dict[str, Any]: 실행 이력 목록
    """
    user_id = jwt_data["user_id"]
    group_id = jwt_data["group_id"]

    logger.info(
        f"📊 실행 이력 조회 요청: schedule_id={schedule_id}, "
        f"user_id={user_id}, page={page}"
    )

    return await schedule_service.get_execution_history(
        schedule_id, user_id, group_id, page, per_page
    )
