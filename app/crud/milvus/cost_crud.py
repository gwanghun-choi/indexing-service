import logging
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List

from app.config.database.async_milvus import async_query
from app.utils.date_utils import (
    generate_date_range,
    get_seoul_timestamp,
    parse_date_from_timestamp,
)
from app.utils.initialization import ensure_collection_loaded

logger = logging.getLogger(__name__)


async def select_daily_cost_statistics(
    group_id: int, user_id: int, start_date: date, end_date: date
) -> List[Dict[str, Any]]:
    """
    사용자의 일별 비용 및 저장소 통계를 조회합니다.

    Args:
        group_id: 그룹 ID (컬렉션 식별용)
        user_id: 사용자 ID
        start_date: 시작 날짜
        end_date: 종료 날짜

    Returns:
        List[Dict[str, Any]]: Milvus에서 조회된 원시 데이터 목록

    Raises:
        Exception: Milvus 조회 중 오류 발생 시
    """
    collection_name = f"TB_{group_id}_meta"
    try:
        logger.info(
            f"비용 통계 조회 시작: user_id={user_id}, group_id={group_id}, {start_date} ~ {end_date}"
        )

        await ensure_collection_loaded(collection_name, "meta")

        # 조회할 필드 설정 (embedding_value 제외)
        output_fields = ["user_id", "cost", "summary_cost", "file_size", "end_date"]

        # 날짜 범위 타임스탬프 변환
        start_timestamp, _ = get_seoul_timestamp(start_date)
        _, end_timestamp = get_seoul_timestamp(end_date)

        logger.debug(f"타임스탬프 범위: {start_timestamp} ~ {end_timestamp}")

        # 쿼리 조건 설정
        # - 특정 사용자의 데이터만 조회
        # - 지정된 날짜 범위 내의 데이터만 조회
        expr = f"user_id == {user_id} and end_date >= {start_timestamp} and end_date <= {end_timestamp}"

        logger.debug(f"Milvus 쿼리 조건: {expr}")

        # Milvus에서 데이터 조회
        results = await async_query(
            collection_name=collection_name,
            filter=expr,
            output_fields=output_fields
        )

        logger.info(f"✅ Milvus 조회 완료: {len(results)}개 레코드 발견")

        # 실제 비용 데이터 로깅
        for i, record in enumerate(results[:3]):  # 처음 3개만 로깅
            cost = record.get("cost", 0)  # Optional: Milvus 조회 결과에서 없을 수 있음
            summary_cost = record.get("summary_cost", 0)  # Optional
            file_size = record.get("file_size", 0)  # Optional
            logger.info(
                f"  📊 레코드 [{i+1}] cost={cost}, summary_cost={summary_cost}, file_size={file_size}"
            )

        return results

    except Exception as e:
        logger.error(
            f"❌ 비용 통계 조회 실패: collection_name={collection_name}, 오류: {e}"
        )
        raise


async def aggregate_cost_data_by_date(
    raw_data: List[Dict[str, Any]], start_date: date, end_date: date
) -> Dict[str, Dict[str, float]]:
    """
    Milvus 원시 데이터를 날짜별로 집계합니다.

    Args:
        raw_data: Milvus에서 조회된 원시 데이터
        start_date: 시작 날짜
        end_date: 종료 날짜

    Returns:
        Dict[str, Dict[str, float]]: 날짜별 집계 데이터
            {
                "2024-01-01": {"total_cost": 125.50, "total_storage": 15728640},
                "2024-01-02": {"total_cost": 89.75, "total_storage": 8388608},
                ...
            }
    """
    try:
        logger.debug(f"데이터 집계 시작: {len(raw_data)}개 원시 레코드")

        # 날짜별 집계를 위한 딕셔너리 초기화
        daily_aggregates = defaultdict(
            lambda: {"total_cost": 0.0, "total_storage": 0, "document_count": 0}
        )

        # 원시 데이터를 날짜별로 집계
        for record in raw_data:
            try:
                # end_date 타임스탬프를 날짜로 변환
                end_timestamp = record.get("end_date", 0)  # Optional: Milvus 조회 결과
                record_date = parse_date_from_timestamp(end_timestamp)
                date_str = record_date.strftime("%Y-%m-%d")

                # 비용 계산: cost + summary_cost
                cost = float(record.get("cost", 0) or 0)  # Optional
                summary_cost = float(record.get("summary_cost", 0) or 0)  # Optional
                total_cost = cost + summary_cost

                # 저장소 크기
                file_size = int(record.get("file_size", 0) or 0)  # Optional

                # 날짜별 집계에 추가
                daily_aggregates[date_str]["total_cost"] += total_cost
                daily_aggregates[date_str]["total_storage"] += file_size
                daily_aggregates[date_str]["document_count"] += 1

                logger.info(
                    f"  💰 레코드 집계: {date_str}, cost={cost}, summary_cost={summary_cost}, total_cost={total_cost}, 크기={file_size}"
                )

            except Exception as e:
                logger.warning(f"⚠️ 레코드 처리 중 오류 (건너뜀): {record}, 오류: {e}")
                continue

        # 빈 날짜는 0으로 채우기 위해 전체 날짜 범위 생성
        all_dates = generate_date_range(start_date, end_date)

        # 최종 결과 생성 (빈 날짜 0으로 채움)
        result = {}
        for date_str in all_dates:
            if date_str in daily_aggregates:
                result[date_str] = daily_aggregates[date_str]
            else:
                result[date_str] = {
                    "total_cost": 0.0,
                    "total_storage": 0,
                    "document_count": 0,
                }

        # 최종 집계 결과 로깅
        total_final_cost = sum(day["total_cost"] for day in result.values())
        total_final_storage = sum(day["total_storage"] for day in result.values())
        total_final_documents = sum(day["document_count"] for day in result.values())

        logger.info(
            f"✅ 데이터 집계 완료: {len(result)}개 날짜, 실제 데이터 {len(daily_aggregates)}개 날짜"
        )
        logger.info(
            f"  🎯 최종 합계: 총 비용=${total_final_cost}, 총 저장소={total_final_storage} bytes, 총 문서={total_final_documents}개"
        )

        return result

    except Exception as e:
        logger.error(f"❌ 데이터 집계 실패: {e}")
        raise


async def calculate_summary_statistics(
    daily_data: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    """
    일별 데이터로부터 전체 요약 통계를 계산합니다.

    Args:
        daily_data: 날짜별 집계 데이터

    Returns:
        Dict[str, Any]: 요약 통계
            {
                "total_days": 31,
                "total_cost": 3875.25,
                "total_storage": 487784320,
                "avg_daily_cost": 125.01,
                "avg_daily_storage": 15735302
            }
    """
    try:
        total_days = len(daily_data)
        total_cost = sum(day_data["total_cost"] for day_data in daily_data.values())
        total_storage = sum(
            day_data["total_storage"] for day_data in daily_data.values()
        )
        total_documents = sum(
            day_data["document_count"] for day_data in daily_data.values()
        )

        # 평균 계산 (0으로 나누기 방지)
        avg_daily_cost = total_cost / total_days if total_days > 0 else 0.0
        avg_daily_storage = total_storage // total_days if total_days > 0 else 0
        avg_daily_documents = total_documents / total_days if total_days > 0 else 0.0

        summary = {
            "total_days": total_days,
            "total_cost": total_cost,
            "total_storage": total_storage,
            "total_documents": total_documents,
            "avg_daily_cost": avg_daily_cost,
            "avg_daily_storage": avg_daily_storage,
            "avg_daily_documents": round(avg_daily_documents, 2),
        }

        logger.debug(f"요약 통계 계산 완료: {summary}")
        return summary

    except Exception as e:
        logger.error(f"❌ 요약 통계 계산 실패: {e}")
        raise


async def select_cost_statistics_for_user(
    group_id: int, user_id: int, start_date: date, end_date: date
) -> Dict[str, Any]:
    """
    사용자의 기간별 비용 및 저장소 통계를 조회하고 집계합니다.

    Args:
        group_id: 그룹 ID
        user_id: 사용자 ID
        start_date: 시작 날짜
        end_date: 종료 날짜

    Returns:
        Dict[str, Any]: 완전히 집계된 통계 데이터
            {
                "daily_data": {...},
                "summary": {...}
            }
    """
    try:
        logger.info(f"✅ 사용자 비용 통계 조회 시작: user_id={user_id}")

        # 1. Milvus에서 원시 데이터 조회
        raw_data = await select_daily_cost_statistics(
            group_id, user_id, start_date, end_date
        )

        # 2. 날짜별 집계
        daily_data = await aggregate_cost_data_by_date(raw_data, start_date, end_date)

        # 3. 전체 요약 통계 계산
        summary = await calculate_summary_statistics(daily_data)

        result = {"daily_data": daily_data, "summary": summary}

        logger.info(
            f"✅ 사용자 비용 통계 조회 완료: user_id={user_id}, 총 {summary['total_days']}일, 총 비용 ${summary['total_cost']}"
        )
        return result

    except Exception as e:
        logger.error(f"❌ 사용자 비용 통계 조회 실패: user_id={user_id}, 오류: {e}")
        raise
