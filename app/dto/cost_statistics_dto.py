from pydantic import BaseModel, Field, field_validator
from typing import List
from datetime import date


# ------------------ Request DTOs ------------------
class CostStatisticsRequestDTO(BaseModel):
    """비용 및 저장소 통계 조회 요청 DTO"""

    start_date: date = Field(
        ..., description="시작 날짜 (YYYY-MM-DD 형식)", example="2024-01-01"
    )
    end_date: date = Field(
        ..., description="종료 날짜 (YYYY-MM-DD 형식)", example="2024-01-31"
    )

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        """날짜 범위 유효성 검증"""
        if v is not None and info.data.get("start_date") is not None:
            start_date = info.data["start_date"]
            if v < start_date:
                raise ValueError("종료 날짜는 시작 날짜보다 이후여야 합니다.")
        return v


# ------------------ Response DTOs ------------------
class DailyCostStatisticsDTO(BaseModel):
    """일별 비용 및 저장소 통계 DTO"""

    date: str = Field(..., description="날짜 (YYYY-MM-DD 형식)", example="2024-01-01")
    total_cost: float = Field(
        ..., description="해당 날짜의 총 비용 (달러 단위)", example=125.50
    )
    total_storage: int = Field(
        ..., description="해당 날짜의 총 저장 용량 (바이트 단위)", example=15728640
    )
    document_count: int = Field(
        ..., description="해당 날짜에 등록된 문서 개수", example=3
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-01-15",
                "total_cost": 125.50,
                "total_storage": 15728640,
                "document_count": 3
            }
        }


class CostStatisticsResponseDTO(BaseModel):
    """비용 및 저장소 통계 응답 DTO"""

    data: List[DailyCostStatisticsDTO] = Field(
        ..., description="일별 비용 및 저장소 통계 목록"
    )
    summary: dict = Field(
        ...,
        description="전체 요약 정보",
        example={
            "total_days": 31,
            "total_cost": 3875.25,
            "total_storage": 487784320,
            "total_documents": 93,
            "avg_daily_cost": 125.01,
            "avg_daily_storage": 15735302,
            "avg_daily_documents": 3.0,
        },
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "date": "2024-01-01",
                        "total_cost": 125.50,
                        "total_storage": 15728640,
                        "document_count": 3
                    },
                    {
                        "date": "2024-01-02",
                        "total_cost": 89.75,
                        "total_storage": 8388608,
                        "document_count": 2
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
                    "total_documents": 93,
                    "avg_daily_cost": 125.01,
                    "avg_daily_storage": 15735302,
                    "avg_daily_documents": 3.0
                }
            }
        }
