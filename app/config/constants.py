"""
애플리케이션 상수 정의
"""

# 허용되는 파일 확장자
ALLOWED_EXTENSIONS = {
    "txt",
    "pdf",
    "docx",
    "xlsx",
    "xls",
    "ppt",
    "pptx",
    "jpg",
    "jpeg",
    "png",
    "mp3",
    "mp4",
}

# 기본 벡터 차원 수
DEFAULT_VECTOR_DIMENSION = 1536

# 임베딩 제공자 목록
EMBEDDING_PROVIDERS = {
    "openai": "OpenAI Embeddings",
    "azure": "Azure OpenAI Embeddings",
    "huggingface": "HuggingFace Embeddings",
    "cohere": "Cohere Embeddings",
    "ncp": "Naver Cloud Platform",
    "bedrock": "AWS Bedrock Embeddings",
}

# 인덱스 타입
INDEX_TYPES = ["FLAT", "IVF_FLAT", "IVF_SQ8", "IVF_PQ", "HNSW", "ANNOY"]

# 메트릭 타입
METRIC_TYPES = ["L2", "IP", "COSINE", "HAMMING", "JACCARD", "TANIMOTO"]
