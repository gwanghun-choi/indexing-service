from datetime import date, datetime, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

# 기본 시간대 설정
SEOUL_TZ = ZoneInfo("Asia/Seoul")


def get_seoul_timestamp(target_date: date) -> Tuple[int, int]:
    """
    주어진 날짜의 서울 시간대 기준 시작/종료 타임스탬프를 반환합니다.

    Args:
        target_date: 변환할 날짜

    Returns:
        Tuple[int, int]: (시작_타임스탬프, 종료_타임스탬프)
            - 시작: 해당 날짜 00:00:00 KST
            - 종료: 해당 날짜 23:59:59 KST
    """
    try:
        # 시작 시간: 해당 날짜 00:00:00 KST
        start_datetime = datetime.combine(
            target_date, datetime.min.time(), tzinfo=SEOUL_TZ
        )
        start_timestamp = int(start_datetime.timestamp())

        # 종료 시간: 해당 날짜 23:59:59 KST
        end_datetime = datetime.combine(
            target_date, datetime.max.time(), tzinfo=SEOUL_TZ
        )
        end_timestamp = int(end_datetime.timestamp())

        logger.debug(
            f"날짜 {target_date} 타임스탬프 변환: {start_timestamp} ~ {end_timestamp}"
        )
        return start_timestamp, end_timestamp

    except Exception as e:
        logger.error(f"타임스탬프 변환 실패: {target_date}, 오류: {e}")
        raise ValueError(f"날짜 타임스탬프 변환 실패: {e}")


def generate_date_range(start_date: date, end_date: date) -> List[str]:
    """
    시작일부터 종료일까지의 모든 날짜 문자열 리스트를 생성합니다.

    Args:
        start_date: 시작 날짜
        end_date: 종료 날짜

    Returns:
        List[str]: YYYY-MM-DD 형식의 날짜 문자열 리스트

    Raises:
        ValueError: 잘못된 날짜 범위인 경우
    """
    if end_date < start_date:
        raise ValueError("종료 날짜는 시작 날짜보다 이후여야 합니다.")

    date_list = []
    current_date = start_date

    while current_date <= end_date:
        date_list.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    logger.debug(f"날짜 범위 생성: {len(date_list)}개 날짜 ({start_date} ~ {end_date})")
    return date_list


def validate_date_range(start_date: date, end_date: date) -> None:
    """
    날짜 범위의 유효성을 검증합니다.

    Args:
        start_date: 시작 날짜
        end_date: 종료 날짜

    Raises:
        ValueError: 유효하지 않은 날짜 범위인 경우
    """
    if end_date < start_date:
        raise ValueError("종료 날짜는 시작 날짜보다 이후여야 합니다.")

    # 미래 날짜 제한 (오늘 이후의 날짜는 조회 불가)
    today = datetime.now(SEOUL_TZ).date()
    if start_date > today:
        raise ValueError("시작 날짜는 오늘 이후일 수 없습니다.")

    if end_date > today:
        logger.warning(
            f"종료 날짜가 오늘({today})보다 미래입니다. 오늘까지만 조회됩니다."
        )


def parse_date_from_timestamp(timestamp: int) -> date:
    """
    Unix 타임스탬프를 서울 시간대 기준 날짜로 변환합니다.

    Args:
        timestamp: Unix 타임스탬프 (초 단위)

    Returns:
        date: 서울 시간대 기준 날짜
    """
    try:
        # 타임스탬프를 서울 시간대 datetime으로 변환
        date_obj = datetime.fromtimestamp(timestamp, tz=SEOUL_TZ)
        return date_obj.date()
    except Exception as e:
        logger.error(f"타임스탬프 파싱 실패: {timestamp}, 오류: {e}")
        raise ValueError(f"타임스탬프 파싱 실패: {e}")

