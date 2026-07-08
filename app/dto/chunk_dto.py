"""청크 수정 요청·응답 DTO"""

from pydantic import BaseModel, Field


class ChunkUpdateRequestDTO(BaseModel):
    """청크 텍스트 수정 요청"""

    parsed_text: str = Field(..., min_length=1, description="수정할 청크 텍스트")


class ChunkUpdateResponseDTO(BaseModel):
    """청크 텍스트 수정 응답"""

    id: int = Field(..., description="벡터 ID (Milvus PK)")
    parsed_text: str = Field(..., description="수정된 청크 텍스트")
    chunk_index: int = Field(..., description="청크 인덱스")
    page_number: int = Field(..., description="페이지 번호")
    hash_sha256: str = Field(..., description="문서 해시")
    title: str = Field(..., description="문서 제목")
    filename: str = Field(..., description="파일명")
    bm25_sync_status: str = Field(default="success", description="OpenSearch 동기화 상태")
