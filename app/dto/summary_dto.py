"""메타 문서 수정 요청·응답 DTO"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class MetaDocUpdateRequestDTO(BaseModel):
    """메타 문서 수정 요청

    모든 필드가 Optional — 전달된 필드만 업데이트됩니다.
    summary 수정 시 임베딩이 자동 재생성됩니다.
    """

    title: Optional[str] = Field(default=None, description="문서 제목")
    category: Optional[str] = Field(default=None, description="문서 카테고리")
    expiration_date: Optional[int] = Field(default=None, description="문서 만료일 (Unix timestamp)")
    summary: Optional[str] = Field(default=None, max_length=5000, description="문서 요약 텍스트")

    @field_validator("summary")
    @classmethod
    def summary_must_not_be_blank(cls, v: Optional[str]) -> Optional[str]:
        """summary가 전달된 경우 공백만으로 구성될 수 없음"""
        if v is not None and not v.strip():
            raise ValueError("summary는 빈 문자열이거나 공백만으로 구성될 수 없습니다")
        return v


class MetaDocUpdateResponseDTO(BaseModel):
    """메타 문서 수정 응답

    embedding_value는 응답에 포함하지 않습니다 (AC-7).
    """

    id: int = Field(..., description="메타 문서 ID (Milvus PK)")
    title: str = Field(..., description="문서 제목")
    category: str = Field(..., description="문서 카테고리")
    expiration_date: int = Field(..., description="문서 만료일 (Unix timestamp)")
    summary: str = Field(..., description="문서 요약 텍스트")
    summary_token: int = Field(..., description="요약 토큰 수")
    summary_cost: float = Field(..., description="요약 비용 (달러)")
