"""
테스트용 임베딩 모델 비용 데이터
"""

data = [
    {"model_name": "text-embedding-3-large", "input_cost_per_token": 1.3e-7},
    {"model_name": "text-embedding-3-small", "input_cost_per_token": 2e-8},
    {"model_name": "text-embedding-ada-002", "input_cost_per_token": 1e-7},
    {"model_name": "text-embedding-ada-002-v2", "input_cost_per_token": 1e-7},
    {"model_name": "azure/ada", "input_cost_per_token": 1e-7},
    {"model_name": "azure/text-embedding-ada-002", "input_cost_per_token": 1e-7},
    {"model_name": "azure/text-embedding-3-large", "input_cost_per_token": 1.3e-7},
    {"model_name": "azure/text-embedding-3-small", "input_cost_per_token": 2e-8},
    {"model_name": "azure_ai/Cohere-embed-v3-english", "input_cost_per_token": 1e-7},
    {
        "model_name": "azure_ai/Cohere-embed-v3-multilingual",
        "input_cost_per_token": 1e-7,
    },
    {"model_name": "mistral/mistral-embed", "input_cost_per_token": 1e-7},
    {"model_name": "text-embedding-004", "input_cost_per_token": 1e-7},
    {"model_name": "text-embedding-005", "input_cost_per_token": 1e-7},
    {"model_name": "text-multilingual-embedding-002", "input_cost_per_token": 1e-7},
    {"model_name": "textembedding-gecko", "input_cost_per_token": 1e-7},
    {"model_name": "textembedding-gecko-multilingual", "input_cost_per_token": 1e-7},
    {
        "model_name": "textembedding-gecko-multilingual@001",
        "input_cost_per_token": 1e-7,
    },
    {"model_name": "textembedding-gecko@001", "input_cost_per_token": 1e-7},
    {"model_name": "textembedding-gecko@003", "input_cost_per_token": 1e-7},
    {"model_name": "text-embedding-preview-0409", "input_cost_per_token": 6.25e-9},
    {
        "model_name": "text-multilingual-embedding-preview-0409",
        "input_cost_per_token": 6.25e-9,
    },
    {"model_name": "embed-english-light-v3.0", "input_cost_per_token": 1e-7},
    {"model_name": "embed-multilingual-v3.0", "input_cost_per_token": 1e-7},
    {"model_name": "embed-english-v2.0", "input_cost_per_token": 1e-7},
    {"model_name": "embed-english-light-v2.0", "input_cost_per_token": 1e-7},
    {"model_name": "embed-multilingual-v2.0", "input_cost_per_token": 1e-7},
    {"model_name": "embed-english-v3.0", "input_cost_per_token": 1e-7},
    {"model_name": "amazon.titan-embed-text-v1", "input_cost_per_token": 1e-7},
    {"model_name": "amazon.titan-embed-text-v2:0", "input_cost_per_token": 2e-7},
    {"model_name": "amazon.titan-embed-image-v1", "input_cost_per_token": 8e-7},
    {"model_name": "cohere.embed-english-v3", "input_cost_per_token": 1e-7},
    {"model_name": "cohere.embed-multilingual-v3", "input_cost_per_token": 1e-7},
    {"model_name": "together-ai-embedding-up-to-150m", "input_cost_per_token": 8e-9},
    {
        "model_name": "together-ai-embedding-151m-to-350m",
        "input_cost_per_token": 1.6e-8,
    },
    {
        "model_name": "fireworks_ai/nomic-ai/nomic-embed-text-v1.5",
        "input_cost_per_token": 8e-9,
    },
    {
        "model_name": "fireworks_ai/nomic-ai/nomic-embed-text-v1",
        "input_cost_per_token": 8e-9,
    },
    {
        "model_name": "fireworks_ai/WhereIsAI/UAE-Large-V1",
        "input_cost_per_token": 1.6e-8,
    },
    {"model_name": "fireworks_ai/thenlper/gte-large", "input_cost_per_token": 1.6e-8},
    {"model_name": "fireworks_ai/thenlper/gte-base", "input_cost_per_token": 8e-9},
]
