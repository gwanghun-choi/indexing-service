"""
Celery Beat 스케줄 설정

주기적으로 실행할 태스크 스케줄을 정의합니다.
"""

from celery.schedules import crontab

# Celery Beat 스케줄 설정
beat_schedule = {
    # 매 분 정각에 스케줄 체크 및 실행 (정확한 시간 보장)
    "check-and-run-schedules": {
        "task": "check_and_run_schedules",
        "schedule": crontab(minute="*"),  # 매 분 00초 정각에 실행
        "options": {
            "expires": 50.0,  # 50초 후 만료 (다음 실행 전에 만료)
            "priority": 5,  # 우선순위 (높음)
        },
    },
    # 매일 새벽 3시에 오래된 실행 이력 정리
    "cleanup-old-execution-history": {
        "task": "cleanup_old_execution_history",
        "schedule": crontab(hour=3, minute=0),  # 매일 03:00
        "options": {
            "priority": 3,  # 우선순위 (중간)
        },
    },
    # 매 5분마다 stale RAGAS 평가(pending/running 정지) 정리 - 무한 로딩 방지
    "cleanup-stale-ragas-evaluations": {
        "task": "cleanup_stale_ragas_evaluations",
        "schedule": crontab(minute="*/5"),  # 매 5분
        "options": {
            "expires": 240.0,  # 4분 후 만료 (다음 실행 전)
            "priority": 3,
        },
    },
}


def get_beat_schedule():
    """
    Celery Beat 스케줄 반환

    Returns:
        dict: beat_schedule 딕셔너리
    """
    return beat_schedule
