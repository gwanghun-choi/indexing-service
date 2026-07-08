from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from typing import List
import logging
import tempfile
import os
import datetime

from app.parser.factory import create_parser
from app.service.simulate_cost import CostSimulator

from app.config.constants import ALLOWED_EXTENSIONS
from app.crud.postgres.user_crud import select_embedding_models
from app.dto.cost_dto import (
    EmbeddingModelDTO,
    DocumentAnalysisResponseDTO,
)
from app.dto.cost_statistics_dto import (
    CostStatisticsRequestDTO,
    CostStatisticsResponseDTO,
)
from app.service.cost_statistics_service import get_user_cost_statistics
from app.utils.auth_utils import get_parsed_jwt_data

logger = logging.getLogger(__name__)


router = APIRouter(
    responses={
        400: {"description": "bad request"},
        401: {"description": "unauthorized"},
        404: {"description": "not found"},
        500: {"description": "internal server error"},
    },
)

# 🔧 컬럼 이름을 리스트로 관리합니다.
COLUMNS = [
    "model_name",
    "provider",
    "category",
    "version",
    "status",
    "max_tokens",
    "max_input_tokens",
    "input_cost_per_token",
    "output_cost_per_token",
    "litellm_provider",
    "mode",
    "total_usage_count",
    "successful_runs",
    "created_at",
    "updated_at",
    "logo",
    "source",
]


@router.get(
    "/models",
    summary="임베딩 모델 목록 조회",
    response_model=List[EmbeddingModelDTO],
    responses={
        200: {
            "description": "성공적으로 임베딩 모델 목록을 조회했습니다.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "model_name": "text-embedding-ada-002",
                            "provider": "openai",
                            "category": "embedding",
                            "version": "v2",
                            "status": "active",
                            "max_tokens": 8191,
                            "max_input_tokens": 8191,
                            "input_cost_per_token": 0.0001,
                            "output_cost_per_token": 0.0,
                            "litellm_provider": "openai",
                            "mode": "embedding",
                            "total_usage_count": 1523,
                            "successful_runs": 1502,
                            "created_at": "2024-01-15T09:30:00",
                            "updated_at": "2024-03-20T14:45:00",
                            "logo": "https://openai.com/logo.png",
                            "source": "official"
                        }
                    ]
                }
            }
        }
    },
    description="""
🧮 **임베딩 모델 정보 조회**

데이터베이스에 등록된 모든 임베딩 모델의 상세 정보를 조회합니다.
각 모델의 제공업체, 버전, 토큰당 비용, 상태 등의 정보를 포함합니다.

## 응답 정보
- 모델명, 제공업체, 카테고리
- 최대 토큰 수, 입력/출력 비용  
- 사용 통계 (총 사용횟수, 성공률)
- 생성/수정 시간

## 반환 데이터
- **model_name**: 모델 이름
- **provider**: 제공업체 (openai, naver, huggingface 등)
- **input_cost_per_token**: 토큰당 입력 비용
- **max_tokens**: 최대 토큰 수
- **status**: 모델 상태 (active, inactive)
    """,
)
async def get_models_list() -> List[EmbeddingModelDTO]:
    """
    사용 가능한 모든 임베딩 모델 정보를 조회합니다.

    Returns:
        List[EmbeddingModelDTO]: 임베딩 모델 정보 목록
            - model_name: 모델 이름
            - provider: 제공업체 (openai, naver, huggingface 등)
            - category: 모델 카테고리
            - version: 모델 버전
            - status: 모델 상태 (active, inactive)
            - max_tokens: 최대 토큰 수
            - input_cost_per_token: 토큰당 입력 비용
            - output_cost_per_token: 토큰당 출력 비용
            - total_usage_count: 총 사용 횟수
            - successful_runs: 성공한 실행 횟수
            - created_at: 생성 시간
            - updated_at: 수정 시간

    Raises:
        HTTPException: 모델 목록 조회 실패 시
            - 500: 데이터베이스 연결 오류, 데이터 파싱 오류
    """
    try:
        raw_data = await select_embedding_models()

        # datetime 객체를 ISO 형식의 문자열로 변환
        formatted_result = [
            {
                column: (
                    row[column].isoformat()
                    if column in ["created_at", "updated_at"]
                    and isinstance(row[column], datetime.datetime)
                    else row[column]
                )
                for column in COLUMNS
            }
            for row in raw_data
        ]

        return formatted_result
    except Exception as e:
        logger.error(f"모델 목록 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/models",
    summary="문서 분석 및 비용 계산",
    response_model=List[DocumentAnalysisResponseDTO],
    responses={
        200: {
            "description": "성공적으로 문서를 분석하고 비용을 계산했습니다.",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "model_name": "text-embedding-ada-002",
                            "provider": "openai",
                            "tokens": 1250,
                            "cost": 0.125,
                            "input_cost_per_token": 0.0001
                        },
                        {
                            "model_name": "text-embedding-3-small",
                            "provider": "openai",
                            "tokens": 1250,
                            "cost": 0.025,
                            "input_cost_per_token": 0.00002
                        }
                    ]
                }
            }
        }
    },
    description="""
💰 **문서 임베딩 비용 계산**

업로드된 문서를 파싱하여 텍스트를 추출하고, 등록된 모든 임베딩 모델에 대해
처리 시 발생할 토큰 수와 예상 비용을 계산합니다.

## 처리 과정
1. 업로드된 파일의 확장자 검증 (PDF, DOCX, TXT, MD 등)
2. 파일을 임시 저장 후 텍스트 추출
3. 각 임베딩 모델별 토큰 수 계산
4. 모델별 비용 산출 (토큰 수 × 모델별 단가)
5. 임시 파일 자동 삭제

## 지원 파일 형식
PDF, DOCX, TXT, MD, PPTX 등

## 응답 정보
각 모델별로 다음 정보를 제공:
- 모델명 및 제공업체
- 계산된 토큰 수
- 예상 처리 비용 (원)
- 토큰당 단가
    """,
)
async def calculate_cost(
    file: UploadFile = File(...),
) -> List[DocumentAnalysisResponseDTO]:
    """
    업로드된 문서의 임베딩 처리 비용을 계산합니다.

    Args:
        file: 분석할 문서 파일 (UploadFile 형식)
            - 지원 형식: PDF, DOCX, TXT, MD, PPTX 등
            - 최대 크기: 설정된 MAX_UPLOAD_SIZE 제한

    Returns:
        List[DocumentAnalysisResponseDTO]: 각 모델별 분석 결과
            - model_name: 모델 이름
            - provider: 제공업체
            - tokens: 계산된 토큰 수
            - cost: 예상 비용 (원)
            - input_cost_per_token: 토큰당 단가

    Raises:
        HTTPException: 파일 분석 실패 시
            - 400: 지원하지 않는 파일 형식
            - 500: 파일 파싱 실패, 토큰 계산 오류, 내부 서버 오류
    """
    try:
        # DB에서 모델 목록 가져오기
        raw_data = await select_embedding_models()

        # 필요한 필드만 추출
        models_data = [
            {
                "model_name": row["model_name"],
                "provider": row["provider"],
                "input_cost_per_token": row["input_cost_per_token"],
            }
            for row in raw_data
        ]

        # 파일 확장자 체크
        file_type = file.filename.split(".")[-1]
        if file_type not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"허용되지 않는 파일 형식입니다. 지원되는 형식: {ALLOWED_EXTENSIONS}",
            )

        # 임시 파일로 저장
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}")
        try:
            # 파일 내용 읽기
            contents = await file.read()
            # 임시 파일에 쓰기
            tmp_file.write(contents)
            tmp_file.close()

            # 문서 파싱 - 임시 파일 경로 사용
            parser = await create_parser(file_type)
            parsed_contents = await parser.parsing(tmp_file.name)

            # 모든 텍스트 추출
            all_text = ""
            for page in parsed_contents:
                all_text += page["text"]

            # CostSimulator 인스턴스 생성
            simulator = CostSimulator()
            # 모델 목록 설정
            await simulator.initialize_registry(models_data)

            # 결과를 저장할 리스트
            result_costs = []

            # 각 모델에 대해 토큰 수와 비용 계산
            for model in models_data:
                model_name = model["model_name"]

                try:
                    model_result = model.copy()

                    # 계산 수행
                    cost_info = await simulator.calculate_document_cost(
                        all_text, model_name
                    )

                    # 결과 추가
                    model_result["tokens"] = cost_info["tokens"]
                    model_result["cost"] = cost_info["cost"]

                    # 결과 리스트에 추가
                    result_costs.append(model_result)
                except Exception as e:
                    logger.warning(f"모델 '{model_name}' 분석 중 오류: {e}")

            # 결과 합치기
            return result_costs

        finally:
            # 임시 파일 삭제
            if os.path.exists(tmp_file.name):
                os.unlink(tmp_file.name)

    except Exception as e:
        logger.error(f"문서 분석 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/statistics",
    summary="비용 및 저장소 사용량 통계 조회",
    response_model=CostStatisticsResponseDTO,
    responses={
        200: {
            "description": "성공적으로 비용 통계를 조회했습니다.",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "date": "2024-01-01",
                                "total_cost": 125.50,
                                "total_storage": 15728640,
                                "document_count": 23
                            },
                            {
                                "date": "2024-01-02", 
                                "total_cost": 89.75,
                                "total_storage": 8388608,
                                "document_count": 15
                            },
                            {
                                "date": "2024-01-03",
                                "total_cost": 0.00,
                                "total_storage": 0,
                                "document_count": 0
                            }
                        ],
                        "summary": {
                            "total_days": 31,
                            "total_cost": 3875.25,
                            "total_storage": 487784320,
                            "total_documents": 1250,
                            "avg_daily_cost": 125.01,
                            "avg_daily_storage": 15735302
                        }
                    }
                }
            }
        }
    },
    description="""
📊 **사용자별 일별 비용 및 저장소 사용량 통계**

사용자가 지정한 기간 동안의 AI 문서 처리 비용과 저장소 사용량을 일별로 조회합니다.
JWT에서 자동으로 사용자 정보를 추출하여 해당 사용자의 데이터만 제공합니다.

## 주요 기능
- **일별 비용 추적**: 임베딩 + 요약 비용의 합계
- **저장소 사용량 분석**: 업로드된 파일의 총 용량 (바이트 단위)
- **빈 날짜 처리**: 데이터가 없는 날짜는 0으로 표시
- **완전한 기간 커버**: 시작일부터 종료일까지 모든 날짜 포함

## 데이터 소스
- **Milvus Meta 컬렉션**: `TB_{group_id}_meta`
- **집계 필드**: `cost`, `summary_cost`, `file_size`, `end_date`
- **시간대**: Asia/Seoul 기준

## 제한 사항
- **사용자 격리**: JWT에서 추출된 사용자만 조회 가능
- **미래 날짜**: 오늘 이후 날짜는 조회 불가

## 응답 필드 설명
### data (배열)
- **date**: 날짜 (YYYY-MM-DD 형식)
- **total_cost**: 해당 날짜의 총 비용 (달러 단위, 소수점 2자리)
- **total_storage**: 해당 날짜의 총 저장 용량 (바이트 단위)
- **document_count**: 해당 날짜의 문서 수

### summary (객체)
- **total_days**: 조회 기간 총 일수
- **total_cost**: 전체 기간 총 비용
- **total_storage**: 전체 기간 총 저장 용량
- **total_documents**: 전체 기간 총 문서 수
- **avg_daily_cost**: 일평균 비용
- **avg_daily_storage**: 일평균 저장 용량

## 활용 예시
- **대시보드**: 비용 추이 차트 생성
- **예산 관리**: 월별/주별 비용 분석
- **용량 관리**: 저장소 사용량 모니터링
- **보고서**: 사용량 통계 리포트 생성
    """,
)
async def get_cost_statistics(
    request: CostStatisticsRequestDTO = Depends(),
    jwt_data: dict = Depends(get_parsed_jwt_data),
) -> CostStatisticsResponseDTO:
    """
    사용자의 기간별 비용 및 저장소 사용량 통계를 조회합니다.

    Args:
        request: 통계 조회 요청 DTO (CostStatisticsRequestDTO)
            - start_date: 시작 날짜 (YYYY-MM-DD 형식)
            - end_date: 종료 날짜 (YYYY-MM-DD 형식)
        jwt_data: JWT에서 파싱된 사용자 정보 (자동 의존성 주입)
            - user_id: 사용자 ID
            - group_id: 그룹 ID (멀티테넌시)
            - role_id: 역할 ID (권한 레벨)

    Returns:
        CostStatisticsResponseDTO: 비용 및 저장소 통계 응답
            - data: 일별 통계 목록 (DailyCostStatisticsDTO[])
            - summary: 전체 요약 통계 (Dict)

    Raises:
        HTTPException: 통계 조회 실패 시
            - 400: 잘못된 날짜 범위
            - 401: JWT 인증 실패
            - 404: 사용자를 찾을 수 없음
            - 500: Milvus 연결 오류, 데이터 집계 실패, 내부 서버 오류
    """
    try:
        # JWT에서 사용자 정보 추출
        user_id = jwt_data["user_id"]
        group_id = jwt_data["group_id"]

        logger.info(
            f"✅ 비용 통계 조회 요청: user_id={user_id}, 기간={request.start_date} ~ {request.end_date}"
        )

        # 통계 조회 수행
        result = await get_user_cost_statistics(
            user_id=user_id, group_id=group_id, request=request
        )

        logger.info(
            f"✅ 비용 통계 조회 완료: user_id={user_id}, 총 비용=${result.summary['total_cost']}, 총 용량={result.summary['total_storage']}바이트, 총 문서={result.summary['total_documents']}개"
        )
        logger.info(f"  📋 일별 데이터 개수: {len(result.data)}개")
        for i, daily in enumerate(result.data[:3]):  # 처음 3개만 로깅
            logger.info(
                f"    [{i+1}] {daily.date}: 비용=${daily.total_cost}, 용량={daily.total_storage}바이트, 문서={daily.document_count}개"
            )
        return result

    except ValueError as ve:
        logger.warning(f"⚠️ 잘못된 요청 파라미터: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(
            f"❌ 비용 통계 조회 실패: user_id={jwt_data.get('user_id')}, 오류: {e}"
        )
        raise HTTPException(status_code=500, detail=f"비용 통계 조회 실패: {str(e)}")
