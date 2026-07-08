from pydantic import BaseModel, Field
from typing import List, Dict
from enum import Enum


class FileUploadResponseDTO(BaseModel):
    """단일 파일 업로드 응답 DTO"""

    filename: str = Field(..., description="업로드된 파일 이름")
    path: str = Field(..., description="저장된 파일 경로")
    status: str = Field(default="uploaded", description="업로드 상태")
    message: str = Field(..., description="처리 결과 메시지")

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "디딤365_여비규정.pdf",
                "path": "users/1/20250130/디딤365_여비규정.pdf",
                "status": "uploaded",
                "message": "파일이 성공적으로 업로드되었습니다.",
            }
        }


class BatchFileUploadResponseDTO(BaseModel):
    """다중 파일 업로드 응답 DTO"""

    files: List[Dict[str, str]] = Field(..., description="업로드된 파일 목록")
    count: int = Field(..., description="업로드된 파일 수")
    status: str = Field(default="uploaded", description="업로드 상태")
    message: str = Field(..., description="처리 결과 메시지")

    class Config:
        json_schema_extra = {
            "example": {
                "files": [
                    {
                        "filename": "디딤365_여비규정.pdf",
                        "path": "users/1/20250130/디딤365_여비규정.pdf",
                        "status": "uploaded",
                    },
                    {
                        "filename": "근로계약서_양식.docx",
                        "path": "users/1/20250130/근로계약서_양식.docx",
                        "status": "uploaded",
                    },
                ],
                "count": 2,
                "status": "uploaded",
                "message": "2개의 파일이 성공적으로 업로드되었습니다.",
            }
        }


class DocumentCategory(str, Enum):
    """문서 카테고리"""

    고용세_기록 = "고용세 기록"
    계약_법률_문서 = "계약 및 법률 문서"
    규제_기록 = "규제 기록"
    기술_문서 = "기술 문서"
    영구_보존_문서 = "영구 보존 문서"
    인사_노무_기록 = "인사 및 노무 기록"
    재무_회계_기록 = "재무 및 회계 기록"
    세무_기록 = "세무 기록"
    전자메일_시스템_로그 = "전자메일 및 시스템 로그"
    참조_자료 = "참조 자료"
    프로젝트_문서 = "프로젝트 문서"
