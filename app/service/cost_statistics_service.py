import logging
from typing import Dict, Any

from app.crud.milvus.cost_crud import select_cost_statistics_for_user
from app.dto.cost_statistics_dto import (
    CostStatisticsRequestDTO,
    CostStatisticsResponseDTO,
    DailyCostStatisticsDTO,
)
from app.utils.date_utils import validate_date_range

logger = logging.getLogger(__name__)


async def get_user_cost_statistics(
    user_id: int, group_id: int, request: CostStatisticsRequestDTO
) -> CostStatisticsResponseDTO:
    """
    사용자의 기간별 비용 및 저장소 통계를 조회합니다.

    Args:
        user_id: 사용자 ID (JWT에서 추출)
        group_id: 그룹 ID (JWT에서 추출)
        request: 통계 조회 요청 DTO

    Returns:
        CostStatisticsResponseDTO: 비용 및 저장소 통계 응답

    Raises:
        ValueError: 유효하지 않은 날짜 범위인 경우
        Exception: 데이터 조회 중 오류 발생 시
    """
    try:
        logger.info(
            f"✅ 비용 통계 서비스 시작: user_id={user_id}, 기간={request.start_date} ~ {request.end_date}"
        )

        # 1. 날짜 범위 유효성 검증
        validate_date_range(request.start_date, request.end_date)

        # 2. CRUD를 통해 통계 데이터 조회
        statistics_data = await select_cost_statistics_for_user(
            group_id=group_id,
            user_id=user_id,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        # 3. 응답 형식으로 변환
        response_data = await format_statistics_response(
            daily_data=statistics_data["daily_data"],
            summary=statistics_data["summary"],
        )

        logger.info(
            f"✅ 비용 통계 서비스 완료: user_id={user_id}, 총 {len(response_data.data)}일 데이터"
        )
        return response_data

    except ValueError as ve:
        logger.warning(f"⚠️ 유효하지 않은 요청: user_id={user_id}, 오류: {ve}")
        raise ve
    except Exception as e:
        logger.error(f"❌ 비용 통계 서비스 실패: user_id={user_id}, 오류: {e}")
        raise


async def format_statistics_response(
    daily_data: Dict[str, Dict[str, float]], summary: Dict[str, Any]
) -> CostStatisticsResponseDTO:
    """
    CRUD 결과를 API 응답 형식으로 변환합니다.

    Args:
        daily_data: 날짜별 집계 데이터
        summary: 전체 요약 통계

    Returns:
        CostStatisticsResponseDTO: 응답 형식으로 변환된 데이터
    """
    try:
        # 일별 데이터를 DTO 리스트로 변환
        daily_statistics = []

        for date_str, stats in sorted(daily_data.items()):
            daily_stat = DailyCostStatisticsDTO(
                date=date_str,
                total_cost=round(stats["total_cost"], 6),  # 소수점 6자리로 변경
                total_storage=stats["total_storage"],
                document_count=stats["document_count"],
            )
            daily_statistics.append(daily_stat)

        # 응답 DTO 생성
        response = CostStatisticsResponseDTO(data=daily_statistics, summary=summary)

        logger.debug(f"응답 변환 완료: {len(daily_statistics)}개 일별 데이터")
        return response

    except Exception as e:
        logger.error(f"❌ 응답 형식 변환 실패: {e}")
        raise
