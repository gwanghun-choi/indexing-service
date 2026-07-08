from pydantic import BaseModel, Field
from typing import List, Optional


# ------------------ Request DTOs ------------------
class CalculateDocCostRequestDTO(BaseModel):
    """문서 비용 계산 요청 DTO"""

    model: str = Field(..., description="임베딩 모델 이름")
    file_path: str = Field(..., description="로컬 파일 경로")


class CalculateQueryCostRequestDTO(BaseModel):
    """쿼리 비용 계산 요청 DTO"""

    model: str = Field(..., description="임베딩 모델 이름")
    query: str = Field(..., description="분석할 텍스트")


# ------------------ Response DTOs ------------------
class CalculateCostResponseDTO(BaseModel):
    """비용 계산 응답 DTO"""

    tokens: int = Field(..., description="토큰 수")
    cost: float = Field(..., description="예상 비용")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tokens": 1250,
                "cost": 0.125
            }
        }


class ModelCostAnalysisDTO(BaseModel):
    """모델별 비용 분석 DTO"""

    model_name: str = Field(..., description="모델 이름")
    provider: str = Field(..., description="제공자")
    token_count: int = Field(..., description="문서의 토큰 수")
    cost: float = Field(..., description="예상 총 비용")
    cost_per_1k_tokens: float = Field(..., description="1000 토큰당 비용")
    max_input_tokens: int = Field(..., description="최대 입력 토큰 수")
    input_cost_per_token: float = Field(..., description="토큰당 입력 비용")


class EmbeddingModelDTO(BaseModel):
    """임베딩 모델 정보 DTO"""

    model_name: str = Field(..., description="모델 이름")
    provider: str = Field(..., description="모델 제공자")
    category: Optional[str] = Field(None, description="모델 카테고리")
    version: Optional[str] = Field(None, description="모델 버전")
    status: Optional[str] = Field(None, description="모델 상태")
    max_tokens: Optional[int] = Field(None, description="최대 토큰 수")
    max_input_tokens: Optional[int] = Field(None, description="최대 입력 토큰 수")
    input_cost_per_token: float = Field(..., description="토큰당 입력 비용")
    output_cost_per_token: Optional[float] = Field(None, description="토큰당 출력 비용")
    litellm_provider: Optional[str] = Field(None, description="LiteLLM 제공자")
    mode: Optional[str] = Field(None, description="모델 모드")
    total_usage_count: Optional[int] = Field(None, description="총 사용 횟수")
    successful_runs: Optional[int] = Field(None, description="성공 실행 횟수")
    created_at: Optional[str] = Field(None, description="생성 시간")
    updated_at: Optional[str] = Field(None, description="업데이트 시간")
    logo: Optional[str] = Field(None, description="로고 URL")
    source: Optional[str] = Field(None, description="소스")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "text-embedding-ada-002",
                "provider": "openai",
                "category": "embeddings",
                "version": "2",
                "status": "active",
                "max_tokens": 8191,
                "max_input_tokens": 8191,
                "input_cost_per_token": 0.0001,
                "output_cost_per_token": None,
                "litellm_provider": "text-embedding-ada-002",
                "mode": "embedding",
                "total_usage_count": 1523,
                "successful_runs": 1520,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "logo": "https://example.com/openai-logo.png",
                "source": "openai"
            }
        }


class EmbeddingModelListResponseDTO(BaseModel):
    """임베딩 모델 목록 응답 DTO"""

    models: List[EmbeddingModelDTO] = Field(..., description="임베딩 모델 목록")


class DocumentAnalysisResponseDTO(BaseModel):
    """문서 분석 결과 DTO"""

    model_name: str = Field(..., description="모델 이름")
    provider: str = Field(..., description="모델 제공자")
    input_cost_per_token: float = Field(..., description="토큰당 입력 비용")
    tokens: Optional[int] = Field(None, description="토큰 수")
    cost: Optional[float] = Field(None, description="예상 비용")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "text-embedding-ada-002",
                "provider": "openai",
                "input_cost_per_token": 0.0001,
                "tokens": 1250,
                "cost": 0.125
            }
        }
