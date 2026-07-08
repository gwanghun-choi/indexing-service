from enum import Enum


class PipelineStage(str, Enum):
    """임베딩 파이프라인 단계 정의"""

    INITIALIZING = "initializing"  # 컬렉션 초기화 중
    DOWNLOADING = "downloading"  # 문서 다운로드 중
    METADATA_EXTRACT = "metadata_extract"  # 메타데이터 추출 중
    DUPLICATE_CHECK = "duplicate_check"  # 중복 확인 중
    METADATA_SAVE = "metadata_save"  # 메타데이터 저장 중
    VALIDATE_STATUS = "validate_status"  # 문서 상태 검증 중
    PARSING = "parsing"  # 문서 파싱 중
    SUMMARY_GENERATION = "summary_generation"  # 요약 생성 중
    PERSONA_FILTER = "persona_filter"  # 페르소나 필터링 중
    EMBEDDING = "embedding"  # 임베딩 생성 중
    TRANSFORMING = "transforming"  # 데이터 변환 중
    INSERTING = "inserting"  # DB 삽입 중
    FINALIZING = "finalizing"  # 최종화 중
    DUPLICATE = "duplicate"  # 중복 문서 감지
    OCR_REQUIRED = "ocr_required"  # OCR 필요


class PipelineStatus(str, Enum):
    """파이프라인 작업 상태"""

    IN_PROGRESS = "in_progress"  # 진행 중
    COMPLETED = "completed"  # 완료
    FAILED = "failed"  # 실패


# 각 Stage별 한글 설명 (프로그레스 바용)
STAGE_DESCRIPTIONS = {
    PipelineStage.INITIALIZING: "컬렉션 초기화 중",
    PipelineStage.DOWNLOADING: "문서 다운로드 중",
    PipelineStage.METADATA_EXTRACT: "메타데이터 추출 중",
    PipelineStage.DUPLICATE_CHECK: "중복 문서 확인 중",
    PipelineStage.METADATA_SAVE: "메타데이터 저장 중",
    PipelineStage.VALIDATE_STATUS: "문서 상태 검증 중",
    PipelineStage.PARSING: "문서 파싱 중",
    PipelineStage.SUMMARY_GENERATION: "요약 및 엔티티 추출 중",
    PipelineStage.PERSONA_FILTER: "페르소나 필터링 중",
    PipelineStage.EMBEDDING: "임베딩 생성 중",
    PipelineStage.TRANSFORMING: "데이터 변환 중",
    PipelineStage.INSERTING: "벡터 데이터 저장 중",
    PipelineStage.FINALIZING: "작업 완료 처리 중",
    PipelineStage.DUPLICATE: "중복 문서 감지됨",
    PipelineStage.OCR_REQUIRED: "OCR 처리 필요",
}
