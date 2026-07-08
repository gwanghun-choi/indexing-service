from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean

from app.config.database import Base


class UserActionLog(Base):
    """
    사용자 액션 로그 테이블

    모든 사용자의 API 요청과 액션을 추적하여 감사 로그를 제공합니다.
    문서 관련 작업, 검색, 업로드, 삭제 등 모든 사용자 활동을 기록합니다.
    """

    __tablename__ = "indexing_action_logs"
    __table_args__ = {"schema": "indexing"}

    # 기본 식별자
    id = Column(Integer, primary_key=True, autoincrement=True, comment="로그 ID")

    # 사용자 정보
    user_id = Column(Integer, nullable=True, comment="사용자 ID")
    group_id = Column(Integer, nullable=True, comment="그룹 ID")
    role_id = Column(Integer, nullable=True, comment="사용자 역할 ID")

    # 요청 정보
    action_type = Column(
        String(20),
        nullable=False,
        comment="액션 타입 (CREATE, READ, UPDATE, DELETE, SEARCH, UPLOAD, DOWNLOAD)",
    )
    endpoint = Column(String(200), nullable=False, comment="요청된 엔드포인트 경로")
    http_method = Column(
        String(10),
        nullable=False,
        comment="HTTP 메서드 (GET, POST, PUT, DELETE, WEBSOCKET)",
    )

    # 문서 관련 정보
    document_id = Column(String(100), nullable=True, comment="대상 문서 ID 또는 해시값")
    document_title = Column(String(255), nullable=True, comment="문서 제목")
    document_category = Column(String(100), nullable=True, comment="문서 카테고리")
    file_name = Column(String(255), nullable=True, comment="파일명")
    file_type = Column(String(30), nullable=True, comment="파일 타입")
    file_size = Column(Integer, nullable=True, comment="파일 크기 (바이트)")

    # 액션 세부 정보
    action_details = Column(JSON, nullable=True, comment="액션 세부 정보 (JSON 형태)")
    request_params = Column(
        JSON, nullable=True, comment="요청 파라미터 (쿼리, 필터 등)"
    )
    changes_made = Column(JSON, nullable=True, comment="변경 내용 (이전값 -> 새값)")

    # 검색 관련 정보 (검색 액션의 경우)
    search_query = Column(Text, nullable=True, comment="검색 쿼리")
    search_results_count = Column(Integer, nullable=True, comment="검색 결과 개수")
    use_reranker = Column(Boolean, nullable=True, comment="리랭커 사용 여부")

    # 결과 정보
    status_code = Column(Integer, nullable=True, comment="HTTP 응답 상태 코드")
    success = Column(
        String(10),
        nullable=False,
        default="SUCCESS",
        comment="성공 여부 (SUCCESS, FAILED, ERROR)",
    )
    error_message = Column(Text, nullable=True, comment="오류 메시지")
    error_type = Column(String(100), nullable=True, comment="오류 타입")

    # 비용 및 성능 정보
    tokens_used = Column(Integer, nullable=True, comment="사용된 토큰 수")
    cost_incurred = Column(String(20), nullable=True, comment="발생 비용 (USD)")
    processing_time_ms = Column(Integer, nullable=True, comment="처리 시간 (밀리초)")

    # 메타데이터
    ip_address = Column(String(45), nullable=True, comment="클라이언트 IP 주소")
    user_agent = Column(String(500), nullable=True, comment="사용자 에이전트")
    session_id = Column(String(100), nullable=True, comment="세션 ID")
    task_id = Column(String(100), nullable=True, comment="비동기 작업 ID")
    request_id = Column(String(100), nullable=True, comment="요청 추적 ID")

    # 시간 정보
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, comment="로그 생성 시간"
    )
    request_start_time = Column(DateTime, nullable=True, comment="요청 시작 시간")
    request_end_time = Column(DateTime, nullable=True, comment="요청 완료 시간")

    def __repr__(self) -> str:
        return (
            f"<UserActionLog("
            f"id={self.id!r}, "
            f"user_id={self.user_id!r}, "
            f"action_type={self.action_type!r}, "
            f"endpoint={self.endpoint!r}, "
            f"status_code={self.status_code!r}, "
            f"success={self.success!r}"
            f")>"
        )
