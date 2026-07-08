"""
문서 요약을 위한 프롬프트 템플릿
유사도 검색 최적화를 위한 문서 요약 생성용 프롬프트
"""

from typing import Final

# 상수 정의
DOCUMENT_SUMMARY_PROMPT: Final[
    str
] = """You are a document summarization expert. Analyze the given document and create a summary optimized for similarity search. **Please write your response in Korean using Markdown format.**

## Guidelines:

### 1. Core Content
- Clearly describe main topic and purpose
- Include all key concepts, terms, and keywords
- Include specific content and data

### 2. Search Optimization
- Include keywords users likely to search for
- Use synonyms and related terms appropriately
- Include terms indicating document type/field

### 3. Structured Summary Format (in Korean with Markdown):
```markdown
## 문서 주제
[한 문장으로 핵심 주제]

## 한줄 요약
[핵심 정보를 포함한 간결한 한 문장 요약]

## 주요 내용
- [구체적인 내용 항목 1]
- [구체적인 내용 항목 2]
- [구체적인 내용 항목 3]
- [필요시 추가 항목]

## 핵심 키워드
`키워드1`, `키워드2`, `키워드3`, `키워드4`, `키워드5`
```

### 4. Length & Style
- Total length: 200-400 Korean characters
- Clear and concise writing
- Balance technical and general terms
- Use proper Markdown formatting (headers, lists, code blocks for keywords)

### 5. Markdown Requirements
- Use `##` for main sections
- Use `-` for bullet points
- Use backticks `` ` `` for keywords

### 6. Similarity Search Optimization
- Include specific numbers, dates, and technical terms when present
- Add synonyms and alternative terms in parentheses
- Include document structure information (chapters, sections, etc.)
- Mention key entities (organizations, people, locations, products)

## CRITICAL CONSTRAINTS:
- **ONLY use information explicitly stated in the provided document**
- **DO NOT add, infer, or imagine any information not directly present in the source**
- **DO NOT include external knowledge or assumptions**
- **If information is unclear or missing, do not guess or fill in gaps**
- **Stick strictly to facts and content from the original document**

## Document Content:
{document_content}

## Output Format (JSON):
You must provide your response as a valid JSON object with two fields: "summary" and "entities".

### 1. Summary Field:
Create an optimized document summary in Korean Markdown format following the above guidelines.

### 2. Entities Field:
Extract entities from the document and categorize them into 7 types:
- **PERSON**: Names of people (authors, stakeholders, mentioned individuals)
- **ORGANIZATION**: Organization names (departments, teams, companies, external vendors)
- **DATE**: Dates (creation date, deadlines, periods, event dates)
- **PROJECT**: Project names or task names
- **CONCEPT**: Key concepts/topics (digital transformation, AI, automation, etc.)
- **DOCUMENT_TYPE**: Document types (proposal, meeting minutes, contract, report)
- **CATEGORY**: Document categories (regulations, manuals, technical docs, proposals)

Each entity should be a JSON object with:
- "type": one of the 7 types above (lowercase)
- "name": the entity name
- "role": (optional) additional context

**Response format:**
```json
{{
  "summary": "## 문서 주제\\n[content]\\n\\n## 한줄 요약\\n[content]\\n\\n## 주요 내용\\n- [item]\\n\\n## 핵심 키워드\\n`keyword1`, `keyword2`",
  "entities": [
    {{"type": "person", "name": "홍길동", "role": "작성자"}},
    {{"type": "organization", "name": "마케팅팀"}},
    {{"type": "date", "name": "2025-01-15"}},
    {{"type": "project", "name": "신제품 출시"}},
    {{"type": "concept", "name": "디지털 전환"}},
    {{"type": "document_type", "name": "제안서"}},
    {{"type": "category", "name": "기획서"}}
  ]
}}
```

**IMPORTANT**: 
- Return ONLY the JSON object, no other text
- Ensure valid JSON format (proper escaping of special characters, newlines as \\n)
- Extract entities ONLY from the document content
- If no entities found for a type, simply omit them from the array"""

# 한글 번역 주석
PROMPT_TRANSLATION_COMMENT: Final[
    str
] = """
한글 번역 (프롬프트 내용):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

당신은 문서 요약 전문가입니다. 주어진 문서를 분석하여 유사도 검색에 최적화된 요약을 작성해주세요. **한국어로 마크다운 형식을 사용하여 응답해주세요.**

## 지침:

### 1. 핵심 내용
- 주요 주제와 목적을 명확히 설명
- 모든 핵심 개념, 용어, 키워드 포함
- 구체적인 내용과 데이터 포함

### 2. 검색 최적화
- 사용자가 검색할 가능성이 높은 키워드 포함
- 동의어와 관련 용어를 적절히 사용
- 문서 유형/분야를 나타내는 용어 포함

### 3. 구조화된 요약 형식 (한국어 마크다운):
```markdown
## 문서 주제
[한 문장으로 핵심 주제]

## 한줄 요약
[핵심 정보를 포함한 간결한 한 문장 요약]

## 주요 내용
- [구체적인 내용 항목 1]
- [구체적인 내용 항목 2]
- [구체적인 내용 항목 3]
- [필요시 추가 항목]

## 핵심 키워드
`키워드1`, `키워드2`, `키워드3`, `키워드4`, `키워드5`
```

### 4. 길이 및 스타일
- 전체 길이: 200-400 한국어 문자
- 명확하고 간결한 작성
- 전문 용어와 일반 용어의 균형
- 적절한 마크다운 형식 사용 (헤더, 리스트, 키워드용 코드 블록)

### 5. 마크다운 요구사항
- 주요 섹션에는 `##` 사용
- 불릿 포인트에는 `-` 사용
- 키워드에는 백틱 `` ` `` 사용

### 6. 유사도 검색 최적화
- 주어진 숫자, 날짜, 기술 용어 포함
- 동의어와 대체 용어 추가
- 문서 구조 정보 포함 (장, 절, 등)
- 주요 엔티티 언급 (조직, 인물, 장소, 제품)

## 중요한 제약 사항:
- **제공된 문서에 명시적으로 기술된 정보만 사용**
- **원본에 직접 제시되지 않은 정보를 추가, 추론, 상상하지 말 것**
- **외부 지식이나 가정을 포함하지 말 것**
- **정보가 불분명하거나 누락된 경우 추측하지 말 것**
- **원본 문서의 사실과 내용에만 엄격히 제한**

## 문서 내용:
{문서_내용}

## 요약 (한국어 마크다운):
위 지침에 따라 최적화된 문서 요약을 작성하세요. 기억하세요: 제공된 문서의 정보만 사용하고 적절한 마크다운 형식으로 출력하세요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


def get_summary_prompt(document_content: str) -> str:
    """
    문서 내용에 따라 최적화된 요약 프롬프트를 반환

    토큰 절약을 위해 영문 프롬프트를 사용하되 한글 출력을 지시하는 방식으로
    구현되었습니다. 유사도 검색에 최적화된 구조화된 요약을 생성합니다.

    Args:
        document_content: 요약할 문서 내용. 빈 문자열은 허용되지 않습니다.

    Returns:
        str: 완성된 프롬프트 (영문 프롬프트 + 한글 출력 지시)

    Raises:
        ValueError: document_content가 빈 문자열이거나 None인 경우

    Example:
        >>> prompt = get_summary_prompt("문서 내용...")
        >>> print(len(prompt))  # 프롬프트 길이 확인
    """
    if not document_content or not document_content.strip():
        raise ValueError("문서 내용은 빈 문자열일 수 없습니다")

    return DOCUMENT_SUMMARY_PROMPT.format(document_content=document_content.strip())
