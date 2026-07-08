import logging
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv

from app.service.utils import get_tokenizer

# 로깅 설정
logger = logging.getLogger(__name__)
load_dotenv()


class EmbeddingModelRegistry:
    """
    임베딩 모델 정보 및 토큰화 관리 클래스

    토크나이저 매핑과 모델 정보를 관리하며, 임베딩 모델별 토큰 수 계산 기능 제공
    """

    # 상수 정의
    # provider별 토큰화 매핑
    tokenizer_map = {
        "openai": get_tokenizer.tokenize_tiktoken,
        "huggingface": get_tokenizer.tokenize_transformers,  # ⚠️ 추정치 반환 (transformers 비활성화됨)
        "ncp": get_tokenizer.tokenize_ncp,
        "azure": get_tokenizer.tokenize_tiktoken,
        "azure_ai": get_tokenizer.tokenize_tiktoken,
        "mistral": get_tokenizer.tokenize_tiktoken,
        "vertex_ai-embedding-entity": get_tokenizer.tokenize_tiktoken,
        "cohere": get_tokenizer.tokenize_tiktoken,
        "bedrock": get_tokenizer.tokenize_tiktoken,
        "together_ai": get_tokenizer.tokenize_tiktoken,
        "fireworks_ai-embedding-entity": get_tokenizer.tokenize_tiktoken,
        "databricks": get_tokenizer.tokenize_tiktoken,
        "voyage": get_tokenizer.tokenize_tiktoken,
    }

    def __init__(self, models: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        임베딩 모델 레지스트리 초기화

        Args:
            models: 초기 모델 정보 리스트 (선택 사항)
        """
        # 속성 정의
        # 모델명-provider 매핑을 저장할 딕셔너리
        self.model_provider_map: Dict[str, str] = {}
        # 모델 목록 초기화
        self.models: List[Dict[str, Any]] = models or []

        # 모델이 제공된 경우 초기화
        if models:
            self.initialize(models)

    # 공개 메서드
    async def initialize(self, models: List[Dict[str, Any]]) -> None:
        """
        임베딩 모델 정보를 초기화하고 모델-provider 매핑 구성

        Args:
            models: 임베딩 모델 정보 리스트
        """
        # 모델 목록 저장
        self.models = models

        # 모델-provider 매핑 초기화
        self.model_provider_map = {
            model["model_name"]: model["provider"] for model in models
        }

        logger.info(f"✅ 임베딩 모델 정보 초기화 완료: {len(models)}개 모델")

    async def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        모델 목록에서 특정 모델의 설정을 찾음

        Args:
            model_name: 모델 이름

        Returns:
            모델 설정 또는 None (모델을 찾지 못한 경우)
        """
        # 모델명 정확히 일치하는 경우
        for model in self.models:
            if model.get("model_name") == model_name:
                return model

        # 모델명이 provider/model_name 형식인 경우 처리
        if "/" in model_name:
            provider, base_model = model_name.split("/", 1)
            # provider 일치하고 base_model도 일치하는 모델 찾기
            for model in self.models:
                if model["provider"] == provider and base_model in model["model_name"]:
                    return model

        return None

    async def count_tokens(self, text: str, model_name: str) -> Optional[int]:
        """
        provider 기반 토크나이저를 사용하여 토큰 수 계산

        Args:
            text: 토큰화할 텍스트
            model_name: 모델 이름

        Returns:
            토큰 수 또는 None (지원되지 않는 provider인 경우)
        """
        try:
            # 텍스트가 비어있으면 0 반환
            if not text or len(text.strip()) == 0:
                return 0

            # 모델-provider 매핑에서 provider 조회
            provider = self.model_provider_map.get(model_name)

            # 모델-provider 매핑에 정보가 없으면 모델명에서 provider 추출 (provider/model_name 형식)
            if not provider and "/" in model_name:
                provider, _ = model_name.split("/", 1)

            # provider 정보가 없으면 기본값으로 openai 사용
            if not provider:
                provider = "openai"
                logger.warning(
                    f"⚠️ 모델 {model_name}의 provider 정보가 없어 openai로 기본 설정"
                )

            # provider에 맞는 토크나이저 함수 사용
            if provider in self.tokenizer_map:
                return await self.tokenizer_map[provider](text, model_name)
            else:
                # 지원되지 않는 provider는 OpenAI 토크나이저로 대체
                logger.warning(
                    f"⚠️ 지원되지 않는 provider '{provider}'를 위해 OpenAI 토크나이저 사용"
                )
                return await self.tokenizer_map["openai"](text, model_name)

        except Exception as e:
            logger.error(f"❌ 토큰화 중 오류 발생: {model_name}, {e}")
            return None


# 싱글톤 인스턴스 생성
model_registry = EmbeddingModelRegistry()


class CostSimulator:
    """
    비용 시뮬레이션을 위한 클래스

    문서 처리 비용을 계산하고 추정하는 기능 제공
    """

    def __init__(self) -> None:
        """
        비용 시뮬레이터 초기화
        """
        # 속성 정의
        # 싱글톤 인스턴스 참조
        self.registry: EmbeddingModelRegistry = model_registry
        # 모델명과 데이터 초기화
        self.model_name: Optional[str] = None
        self.model_data: Optional[Dict[str, Any]] = None

        logger.info("✅ 비용 시뮬레이터 초기화 완료")

    # 공개 메서드
    async def initialize_registry(self, models: List[Dict[str, Any]]) -> None:
        """
        모델 레지스트리 초기화 또는 업데이트

        Args:
            models: 모델 정보 리스트 (각 항목은 model_name, provider, input_cost_per_token 포함)

        Raises:
            ValueError: 모델 목록이 비어 있는 경우
        """
        if not models:
            raise ValueError("모델 목록이 비어 있습니다.")

        # 레지스트리 초기화
        await self.registry.initialize(models)
        logger.info(f"✅ 모델 레지스트리 업데이트: {len(models)}개 모델")

    async def select_model(self, model_name: str) -> None:
        """
        사용할 모델 변경

        Args:
            model_name: 새로 사용할 모델 이름

        Raises:
            ValueError: 모델 정보를 찾을 수 없는 경우
        """
        # 모델 데이터 가져오기
        model_data = await self.registry.get_model_config(model_name)
        if not model_data:
            logger.error(f"❌ 모델 정보를 찾을 수 없음: {model_name}")
            raise ValueError(f"Model information not found for: {model_name}")

        # 모델명과 모델 데이터 업데이트
        self.model_name = model_name
        self.model_data = model_data
        logger.info(f"✅ 모델 변경: {model_name}")

    async def count_tokens(self, text: str, model_name: Optional[str] = None) -> int:
        """
        문서의 토큰 수 계산 (provider 기반 토크나이저 사용)

        Args:
            text: 토큰화할 텍스트
            model_name: 사용할 모델 이름

        Returns:
            토큰 수

        Raises:
            ValueError: 모델 정보를 찾을 수 없는 경우
        """
        # 모델명이 지정되지 않은 경우 현재 선택된 모델 사용
        if model_name is None:
            await self._check_model_selected()
            model_name = self.model_name

        # provider 기반 토크나이저로 토큰 수 계산
        tokens = await self.registry.count_tokens(text, model_name)

        # 결과가 None이면 로그 기록하고 0 반환
        if tokens is None:
            logger.warning(
                f"⚠️ 모델 {model_name}에 대한 토큰 계산 실패: 지원되지 않는 provider 또는 모델"
            )
            return 0

        return tokens

    async def simulate_embedding_cost(
        self, tokens: int, model_name: Optional[str] = None
    ) -> float:
        """
        임베딩 비용 시뮬레이션

        Args:
            tokens: 토큰 수
            model_name: 사용할 모델 이름

        Returns:
            예상 비용 (USD)

        Raises:
            ValueError: 모델 정보를 찾을 수 없는 경우
        """
        # 토큰 수가 0이면 비용 계산 불가
        if tokens == 0:
            return 0.0

        # 모델 데이터 가져오기
        model_data = None
        if model_name is None:
            # 현재 선택된 모델 사용
            await self._check_model_selected()
            model_data = self.model_data
            model_name = self.model_name
        else:
            # 지정된 모델 정보 조회
            model_data = await self.registry.get_model_config(model_name)

        if not model_data:
            logger.error(f"❌ 모델 정보를 찾을 수 없음: {model_name}")
            raise ValueError(f"모델 정보를 찾을 수 없습니다: {model_name}")

        # 비용 계산
        cost_per_token = model_data["input_cost_per_token"]
        cost = tokens * cost_per_token

        logger.debug(f"🔍 비용 계산: {tokens} 토큰 × {cost_per_token} = ${cost}")
        return cost

    async def calculate_document_cost(
        self, text: str, model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        문서의 토큰 수 계산 및 비용 시뮬레이션을 한 번에 수행

        Args:
            text: 분석할 텍스트
            model_name: 사용할 모델 이름

        Returns:
            Dict[str, Any]: 토큰 수, 비용, 지원 여부 등의 정보

        Raises:
            ValueError: 모델 정보를 찾을 수 없는 경우
        """
        # 모델명이 지정되지 않은 경우 현재 선택된 모델 사용
        if model_name is None:
            await self._check_model_selected()
            model_name = self.model_name

        # 토큰 수 계산
        tokens = await self.count_tokens(text, model_name)

        # 비용 계산
        cost = await self.simulate_embedding_cost(tokens, model_name)

        logger.info(
            f"✅ 문서 비용 계산 완료: 모델={model_name}, 토큰={tokens}, 비용=${cost}"
        )

        return {
            "model_name": model_name,
            "tokens": tokens,
            "cost": cost,
        }

    # 비공개 메서드
    async def _check_model_selected(self) -> None:
        """
        현재 모델이 선택되었는지 확인

        Raises:
            ValueError: 모델이 선택되지 않은 경우
        """
        if self.model_name is None or self.model_data is None:
            logger.error(
                "❌ 모델이 선택되지 않았습니다. select_model()을 먼저 호출하세요."
            )
            raise ValueError(
                "모델이 선택되지 않았습니다. select_model()을 먼저 호출하세요."
            )


# 간편한 인터페이스 함수들
async def count_tokens(text: str, model_name: str) -> int:
    """
    토큰 계산 함수

    Args:
        text: 토큰화할 텍스트
        model_name: 모델 이름

    Returns:
        토큰 수 또는 0 (지원되지 않는 모델인 경우)
    """
    return await model_registry.count_tokens(text, model_name)
