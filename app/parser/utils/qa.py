import os
from dotenv import load_dotenv
from pdf2image import convert_from_path
from langchain_openai import ChatOpenAI
from langchain_teddynote.models import MultiModal
from tqdm import tqdm

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

VISION_API_URL = "https://api.openai.com/v1/chat/completions"


def chunk_text(text: str, chunk_size: int = 4000) -> list:
    """
    한글 문서를 대략적인 문자수(4000자) 단위로 나눠 청크를 생성.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end
    return chunks


def convert_document_to_images(file_path: str) -> list:
    ext = os.path.splitext(file_path)[1].lower()

    if ext != ".pdf":
        raise ValueError("현재 예시에서는 PDF만 지원합니다. 다른 포맷은 별도 처리 필요")

    images = convert_from_path(file_path, dpi=200)
    image_paths = []
    for i, img in enumerate(images):
        output_image_path = f"/tmp/converted_page_{i+1}.png"
        img.save(output_image_path, "PNG")
        image_paths.append(output_image_path)

    return image_paths


def create_llm() -> ChatOpenAI:
    """
    공통적으로 사용하는 LLM 객체 생성 함수.
    """
    return ChatOpenAI(
        temperature=0.1,
        max_tokens=2048,
        model_name="gpt-4o",
    )


def build_user_prompt(qa_size: int, text_content: str = None) -> str:
    """
    Q/A 생성을 위한 프롬프트를 구성하는 함수.
    """
    common_requirements = f"""문서의 내용을 바탕으로 한국어 질문과 답변(Q/A) 데이터를 최대 {qa_size}개 이하로 다양하고 많이 생성해주세요.

**요구사항:**
1. **질문과 답변 형식**: 모든 질문과 답변은 'Q:'와 'A:' 형식만 사용하며, 그 외의 숫자나 기타 구분 기호는 사용하지 않습니다.
2. **다양성**: 다양한 주제와 깊이의 질문과 답변을 생성해 주세요. 질문은 이해 수준에 따라 쉽거나 어렵게 구성될 수 있습니다.
3. **내용 기반**: 문서(또는 텍스트)에 존재하는 정보만 활용하여 질문과 답변을 생성해 주세요. 추측이나 문서에 없는 내용은 포함하지 마세요.
4. **형식 유지**: 순수한 Q/A 형식으로만 작성되도록 주의해 주세요.
"""

    if text_content:
        return f"""{common_requirements}
<텍스트 내용>
{text_content}
</텍스트 내용>
"""
    return common_requirements


def generate_qa_from_image(image_path: str, qa_size: int) -> str:
    """
    단일 이미지에 대해 Q&A를 생성하는 함수.
    """
    llm = create_llm()
    multimodal_llm = MultiModal(llm)
    user_prompt = build_user_prompt(qa_size=qa_size, text_content=None)

    response = multimodal_llm.invoke(
        image_url=image_path, user_prompt=user_prompt, display_image=False
    )
    return response


def generate_qa_from_text_chunk(text_chunk: str, qa_size: int) -> str:
    """
    텍스트 청크에 대해 Q&A를 생성하는 함수.
    """
    llm = create_llm()
    user_prompt = build_user_prompt(qa_size=qa_size, text_content=text_chunk)
    response = llm.invoke(user_prompt)
    return response


def generate_qa_from_document(file_path: str, qa_size: int = 20) -> str:
    """
    주어진 문서(pdf 또는 txt)에 대해 Q/A 데이터를 생성하는 함수.
    qa_size를 통해 생성할 최대 Q/A 개수를 지정할 수 있음.
    기본값은 20.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        image_paths = convert_document_to_images(file_path)
        all_qa_data = []

        # PDF 이미지 처리 진행 상황 표시
        for image_path in tqdm(image_paths, desc="Processing PDF Pages"):
            page_qa = generate_qa_from_image(image_path, qa_size=qa_size)
            all_qa_data.append(page_qa)

        # 이미지 파일 정리
        for image_path in image_paths:
            if os.path.exists(image_path):
                os.remove(image_path)

        return "\n\n".join(all_qa_data)

    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text_content = f.read()

        text_chunks = chunk_text(text_content, chunk_size=4000)
        chunk_qa_list = []

        # 텍스트 청크 처리 진행 상황 표시
        for chunk in tqdm(text_chunks, desc="Processing Text Chunks"):
            chunk_qa = generate_qa_from_text_chunk(chunk, qa_size=qa_size)
            chunk_qa_list.append(chunk_qa)

        return "\n\n".join(chunk_qa_list)

    else:
        raise ValueError(
            "지원하지 않는 파일 형식입니다. PDF 또는 TXT 파일을 제공하세요."
        )
