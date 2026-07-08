from enum import Enum


class DocumentStatus(str, Enum):
    """
    문서 처리 상태 정의

    문서의 현재 처리 단계를 나타내는 상태값입니다.
    모든 파이프라인에서 일관되게 사용됩니다.
    """

    UPLOADING = "uploading"
    """문서 업로드 중 - 파이프라인 시작 단계"""

    REGISTERED = "registered"
    """메타데이터 등록 완료 - 임베딩 생성 전 상태 (분리 모드)"""

    RUNNING = "running"
    """임베딩 생성 중 - 파이프라인 실행 중 상태"""

    UPLOADED = "uploaded"
    """임베딩 완료 - 전체 처리 완료 상태"""

    FAILED = "failed"
    """처리 실패 - 오류로 인한 실패"""

    SKIPPED = "skipped"
    """처리 건너뜀 - 중복 문서 등으로 건너뜀"""

    OCR_REQUIRED = "ocr_required"
    """OCR 처리 필요 - 텍스트 추출 불가로 OCR 필요"""

    def __str__(self) -> str:
        """문자열 변환 시 값 반환"""
        return self.value

    @classmethod
    def from_string(cls, status: str) -> "DocumentStatus":
        """
        문자열로부터 DocumentStatus enum 생성

        Args:
            status: 상태 문자열

        Returns:
            DocumentStatus: 해당하는 enum 값

        Raises:
            ValueError: 유효하지 않은 상태값인 경우

        Example:
            >>> DocumentStatus.from_string("uploaded")
            <DocumentStatus.UPLOADED: 'uploaded'>
        """
        try:
            return cls(status)
        except ValueError:
            valid_statuses = ", ".join([s.value for s in cls])
            raise ValueError(
                f"유효하지 않은 문서 상태: '{status}'. " f"가능한 값: {valid_statuses}"
            )

    @classmethod
    def get_all_values(cls) -> list[str]:
        """
        모든 상태값을 리스트로 반환

        Returns:
            list[str]: 모든 상태값의 리스트

        Example:
            >>> DocumentStatus.get_all_values()
            ['uploading', 'registered', 'uploaded', 'failed', 'skipped', 'ocr_required']
        """
        return [status.value for status in cls]
