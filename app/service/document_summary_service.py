"""
문서 요약 생성 서비스
LLM을 활용한 문서 요약 생성 및 유사도 검색 최적화 서비스
"""

import logging
import json
from typing import Dict, List, Any, Union

from openai import AsyncOpenAI

from app.prompts.document_summary_prompt import get_summary_prompt
from app.utils.llm_compat import needs_max_completion_tokens


# 로거 설정
logger = logging.getLogger(__name__)

# 타입 정의
ParsedContent = List[
    Dict[str, Union[int, str]]
]  # [{"page_number": int, "text": str}, ...]

# merge_parsed_content_to_text는 app/utils/document_utils.py로 이동됨
from app.utils.document_utils import merge_parsed_content_to_text  # noqa: E402, F401


class DocumentSummaryService:
    """
    문서 요약 생성 서비스

    LLM을 활용하여 문서의 요약을 생성하고, 유사도 검색에 최적화된
    형태로 변환하는 서비스를 제공합니다.
    """

    # 상수 정의
    DEFAULT_MODEL: str = "gpt-5.4-mini"
    DEFAULT_TEMPERATURE: float = 0.2

    # 모델별 최대 문서 길이 제한 (토큰 기준으로 계산)
    MODEL_CONTENT_LIMITS: Dict[str, int] = {
        "gpt-3.5-turbo": 50000,  # ~12,500 토큰 여유
        "gpt-4": 120000,  # ~30,000 토큰 여유
        "gpt-4-turbo": 400000,  # ~100,000 토큰 여유
        "gpt-4o": 400000,  # ~100,000 토큰 여유
        "gpt-4o-mini": 400000,  # ~100,000 토큰 여유
        "gpt-5.4-mini": 400000,  # 400k 컨텍스트 윈도우
    }

    # 한 응답에 summary(200-400자) + entities 배열 + JSON 구조를 함께 출력하므로
    # 요약 길이뿐 아니라 entities 수와 JSON overhead까지 토큰 예산에 포함해야 한다.
    # (800은 엔티티가 많은 문서에서 응답이 잘려 JSON이 깨지고 entities/키워드가 소실됨)
    UNIFIED_MAX_TOKENS: int = 2500

    # finish_reason=length(잘림) 감지 시 1회 재시도에 사용할 상향 토큰
    RETRY_MAX_TOKENS: int = 4000

    # JSON 파싱 실패 시 사용자에게 노출할 안전한 대체 요약 (깨진 원문 노출 방지)
    FALLBACK_SUMMARY: str = "## 요약\n문서 요약을 생성하지 못했습니다."

    # 기본 최대 문서 길이 (알 수 없는 모델용)
    DEFAULT_MAX_CONTENT_LENGTH: int = 50000

    def __init__(self, openai_client: AsyncOpenAI) -> None:
        """
        DocumentSummaryService 초기화

        Args:
            openai_client: OpenAI 비동기 클라이언트 인스턴스

        Raises:
            ValueError: openai_client가 None인 경우
        """
        if openai_client is None:
            raise ValueError("OpenAI 클라이언트는 필수입니다")

        self._openai_client = openai_client
        logger.info("✅ DocumentSummaryService 초기화 완료.")

    @property
    def openai_client(self) -> AsyncOpenAI:
        """OpenAI 클라이언트 인스턴스 반환"""
        return self._openai_client

    async def generate_summary(
        self,
        document_content: str,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> Dict[str, Any]:
        """
        문서 요약 생성

        주어진 문서 내용을 바탕으로 유사도 검색에 최적화된 요약을 생성합니다.
        Hallucination 방지를 위해 원본 문서 내용만을 사용하도록 제약합니다.
        통일된 max_tokens(2500)가 자동으로 설정됩니다.

        Args:
            document_content: 요약할 문서 내용
            model: 사용할 LLM 모델명 (기본값: gpt-3.5-turbo)
            temperature: 생성 온도 (기본값: 0.2, 일관성 중시)

        Returns:
            Dict[str, Any]: 생성된 문서 요약, 엔티티 및 토큰 사용량 정보
                - summary: 생성된 문서 요약 (한글, 마크다운 형식)
                - entities: 추출된 엔티티 목록 (List[Dict])
                - prompt_tokens: 입력 토큰 수
                - completion_tokens: 출력 토큰 수
                - total_tokens: 전체 토큰 수

        Raises:
            ValueError: 입력 매개변수가 유효하지 않은 경우
            Exception: LLM API 호출 실패 또는 기타 오류 발생 시

        Example:
            >>> service = DocumentSummaryService(openai_client)
            >>> result = await service.generate_summary("문서 내용...")
            >>> print(result["summary"])
            >>> print(f"사용된 토큰: {result['total_tokens']}")
        """
        try:
            # 통일된 max_tokens 설정
            max_tokens = self.UNIFIED_MAX_TOKENS

            # 입력 검증
            self._validate_input_parameters(
                document_content, model, max_tokens, temperature
            )

            # 프롬프트 생성
            prompt = get_summary_prompt(document_content)

            logger.info(
                f"문서 요약 생성 시작 - 모델: {model}, 통일된 토큰: {max_tokens} 🚀"
            )
            logger.debug(f"문서 내용 길이: {len(document_content)} 문자")

            # OpenAI API 호출
            response = await self._call_openai_api(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # 응답이 잘린 경우(finish_reason=length) 더 큰 토큰으로 1회 재시도
            if self._is_truncated(response):
                logger.warning(
                    f"요약 응답이 잘렸습니다(finish_reason=length, max_tokens={max_tokens}). "
                    f"max_tokens={self.RETRY_MAX_TOKENS}로 1회 재시도합니다."
                )
                response = await self._call_openai_api(
                    prompt=prompt,
                    model=model,
                    max_tokens=self.RETRY_MAX_TOKENS,
                    temperature=temperature,
                )
                if self._is_truncated(response):
                    logger.warning(
                        f"재시도에도 요약 응답이 잘렸습니다"
                        f"(max_tokens={self.RETRY_MAX_TOKENS}). "
                        "entities가 일부 소실될 수 있습니다."
                    )

            # 응답 추출 및 검증 (JSON 파싱)
            result = self._extract_and_validate_response(response)
            summary = result["summary"]
            entities = result["entities"]

            # 토큰 사용량 추출
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            logger.info(
                f"문서 요약 및 엔티티 추출 완료 - "
                f"요약 길이: {len(summary)} 문자, "
                f"엔티티 개수: {len(entities)}개, "
                f"토큰 사용량: {prompt_tokens} + {completion_tokens} = {total_tokens} ✅"
            )

            return {
                "summary": summary,
                "entities": entities,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }

        except ValueError as e:
            logger.error(f"입력 검증 오류: {str(e)} ❌")
            raise
        except Exception as e:
            logger.error(f"문서 요약 생성 실패: {str(e)} 💥")
            raise Exception(f"문서 요약 생성 중 오류가 발생했습니다: {str(e)}")

    # Private 메서드들

    def get_max_content_length(self, model: str) -> int:
        """
        모델별 최대 문서 길이 제한 반환

        Args:
            model: LLM 모델명

        Returns:
            int: 해당 모델의 최대 문서 길이 (문자 수)

        Example:
            >>> service.get_max_content_length("gpt-4")
            120000
        """
        return self.MODEL_CONTENT_LIMITS.get(model, self.DEFAULT_MAX_CONTENT_LENGTH)

    def _validate_input_parameters(
        self, document_content: str, model: str, max_tokens: int, temperature: float
    ) -> None:
        """입력 매개변수 검증"""
        if not document_content or not document_content.strip():
            raise ValueError("문서 내용은 빈 문자열일 수 없습니다")

        if len(document_content) > self.get_max_content_length(model):
            raise ValueError(
                f"{model} 모델에서는 최대 {self.get_max_content_length(model)}자까지 허용됩니다"
            )

        if not model or not model.strip():
            raise ValueError("모델명은 빈 문자열일 수 없습니다")

        if max_tokens <= 0:
            raise ValueError("max_tokens는 0보다 큰 값이어야 합니다")

        if not (0.0 <= temperature <= 2.0):
            raise ValueError("temperature는 0.0과 2.0 사이의 값이어야 합니다")

    async def _call_openai_api(
        self, prompt: str, model: str, max_tokens: int, temperature: float
    ) -> Any:
        """OpenAI API 호출"""
        try:
            # gpt-5.x, o-series 등 신규 모델은 max_completion_tokens 사용
            if needs_max_completion_tokens(model):
                token_param = {"max_completion_tokens": max_tokens}
            else:
                token_param = {"max_tokens": max_tokens}

            response = await self._openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
                **token_param,
            )
            return response

        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {str(e)} ❌")
            raise Exception(f"LLM API 호출 중 오류가 발생했습니다: {str(e)}")

    @staticmethod
    def _is_truncated(response: Any) -> bool:
        """응답이 토큰 한도로 잘렸는지(finish_reason=length) 여부를 반환한다."""
        return bool(response.choices) and response.choices[0].finish_reason == "length"

    def _extract_and_validate_response(self, response: Any) -> Dict[str, Any]:
        """API 응답에서 요약 및 엔티티 추출 및 검증"""
        try:
            if not response.choices:
                raise ValueError("API 응답에서 선택 항목을 찾을 수 없습니다")

            content = response.choices[0].message.content

            if not content or not content.strip():
                raise ValueError("생성된 응답이 비어있습니다")

            # JSON 파싱
            try:
                # 코드 블록으로 감싸진 경우 처리 (```json ... ```)
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]  # ```json 제거
                if content.startswith("```"):
                    content = content[3:]  # ``` 제거
                if content.endswith("```"):
                    content = content[:-3]  # ``` 제거

                content = content.strip()

                result = json.loads(content)

                # 필수 필드 검증
                if "summary" not in result:
                    raise ValueError("JSON 응답에 'summary' 필드가 없습니다")
                if "entities" not in result:
                    logger.warning(
                        "JSON 응답에 'entities' 필드가 없습니다. 빈 배열로 설정합니다."
                    )
                    result["entities"] = []

                # 요약이 비어있는지 검증
                if not result["summary"] or not result["summary"].strip():
                    raise ValueError("생성된 요약이 비어있습니다")

                # 엔티티가 리스트인지 검증
                if not isinstance(result["entities"], list):
                    logger.warning(
                        "엔티티가 리스트 형식이 아닙니다. 빈 배열로 설정합니다."
                    )
                    result["entities"] = []

                # 엔티티 검증 및 정제
                validated_entities = []
                valid_types = [
                    "person",
                    "organization",
                    "date",
                    "project",
                    "concept",
                    "document_type",
                    "category",
                ]

                for entity in result["entities"]:
                    if (
                        isinstance(entity, dict)
                        and "type" in entity
                        and "name" in entity
                    ):
                        entity_type = entity["type"].lower()
                        if entity_type in valid_types:
                            validated_entities.append(entity)
                        else:
                            logger.warning(f"유효하지 않은 엔티티 타입: {entity_type}")
                    else:
                        logger.warning(f"유효하지 않은 엔티티 형식: {entity}")

                result["entities"] = validated_entities

                logger.debug(
                    f"JSON 파싱 성공 - 요약: {len(result['summary'])} 문자, 엔티티: {len(result['entities'])}개"
                )

                return result

            except json.JSONDecodeError as e:
                preview = content[:200].replace("\n", " ")
                logger.error(f"JSON 파싱 실패: {str(e)} | content 앞부분(200자): {preview}")
                # 깨진 JSON 원문을 그대로 summary로 저장하지 않는다.
                # entities는 복구 불가하므로 빈 배열, summary는 안전한 대체 텍스트 사용.
                logger.warning(
                    "JSON 파싱 실패 - 깨진 원문 대신 안전한 대체 요약을 저장하고 "
                    "entities=[]로 설정합니다."
                )
                return {"summary": self.FALLBACK_SUMMARY, "entities": []}

        except Exception as e:
            logger.error(f"응답 추출 실패: {str(e)} ❌")
            raise Exception(f"API 응답 처리 중 오류가 발생했습니다: {str(e)}")
