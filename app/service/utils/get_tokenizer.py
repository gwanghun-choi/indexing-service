import logging

import tiktoken
import aiohttp

# ❌ transformers 라이브러리 비활성화 (메모리 절감: ~500MB-1GB)
# from transformers import AutoTokenizer

from app.config.settings import settings

# 로깅 설정
logger = logging.getLogger(__name__)


class TokenizerService:
    """
    다양한 모델을 위한 토큰화 서비스 제공 클래스
    """

    @classmethod
    async def tokenize_tiktoken(cls, text: str, model: str) -> int:
        """
        tiktoken 모델용 토큰화
        적용 모델: OpenAI, ...

        Args:
            text: 토큰화할 텍스트
            model: 모델 이름

        Returns:
            int: 토큰 수

        Raises:
            Exception: 토큰화 과정에서 오류 발생 시
        """
        logger.info(f"✅ OpenAI 토크나이저로 {model} 모델 토큰화 중")

        try:
            encoding = tiktoken.encoding_for_model(model)
            tokens = encoding.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"❌ OpenAI 토큰화 중 오류 발생: {e}")
            return 0

    @classmethod
    async def tokenize_transformers(cls, text: str, model: str) -> int:
        """
        transformers 모델용 토큰화 (현재 비활성화)

        ⚠️ transformers 라이브러리가 비활성화되어 간단한 추정치를 반환합니다.
        HuggingFace 모델을 사용하지 않으므로 공백 기반 토큰 수를 추정합니다.

        Args:
            text: 토큰화할 텍스트
            model: 모델 이름

        Returns:
            int: 추정 토큰 수

        Note:
            transformers 라이브러리는 메모리 절감을 위해 비활성화되었습니다.
            정확한 토큰 수가 필요한 경우 transformers import를 다시 활성화하세요.
        """
        logger.warning(
            f"⚠️ HuggingFace 토크나이저가 비활성화되어 있습니다. "
            f"모델 {model}에 대한 추정 토큰 수를 반환합니다."
        )

        # 간단한 추정: 공백 기준 단어 수 * 1.5 (평균적인 토큰/단어 비율)
        estimated_tokens = int(len(text.split()) * 1.5)
        logger.info(f"📊 추정 토큰 수: {estimated_tokens}개")
        return estimated_tokens

        # ❌ 원본 코드 (transformers 라이브러리 비활성화로 주석처리)
        # try:
        #     tokenizer = AutoTokenizer.from_pretrained(model)
        #     tokens = tokenizer.encode(text)
        #     return len(tokens)
        # except Exception as e:
        #     logger.error(f"❌ HuggingFace 토큰화 중 오류 발생: {e}")
        #     return 0

    @classmethod
    async def tokenize_ncp(cls, text: str, model: str) -> int:
        """
        NCP 모델용 토큰화 (NCP API 사용)

        Args:
            text: 토큰화할 텍스트
            model: 모델 이름

        Returns:
            int: 토큰 수

        Raises:
            Exception: API 호출 실패 또는 오류 발생 시
        """
        logger.info(f"✅ NCP 토크나이저로 {model} 모델 토큰화 중")

        # NCP API 호출
        try:
            # 비동기 직접 호출로 변경
            token_count = await cls._call_ncp_tokenizer_api(text)

            # API 호출 결과가 있으면 반환
            if token_count is not None:
                logger.info(
                    f"✅ NCP API로 {model} 모델 토큰화 완료: {token_count}개 토큰"
                )
                return token_count
            else:
                # API 호출 결과가 없으면 예외 발생
                raise Exception("NCP API 호출 실패: 토큰 수를 계산할 수 없습니다.")
        except Exception as e:
            logger.error(f"❌ NCP 토큰화 API 호출 중 오류 발생: {e}")
            return 0

    @staticmethod
    async def _call_ncp_tokenizer_api(text: str) -> int:
        """
        NCP 토큰 계산기 API 호출

        Args:
            text: 토큰화할 텍스트

        Returns:
            int: 토큰 수 또는 None (API 호출 실패 시)
        """
        if not settings.NCP_API_KEY:
            logger.warning("⚠️ NCP API 키가 설정되지 않았습니다")
            return None

        # 상수 정의
        NCP_API_URL = "{base_url}/v1/api-tools/embedding/v2/tokenize"

        url = NCP_API_URL.format(base_url=settings.HCX_API_BASE)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.NCP_API_KEY}",
        }
        payload = {"text": text}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "result" in data and "numTokens" in data["result"]:
                            return data["result"]["numTokens"]
                        else:
                            logger.warning(f"⚠️ NCP API 응답 형식 오류: {data}")
                    else:
                        logger.warning(
                            f"⚠️ NCP API 호출 실패: 상태 코드 {response.status}"
                        )
                        error_text = await response.text()
                        logger.warning(f"응답 내용: {error_text}")
        except Exception as e:
            logger.error(f"❌ NCP API 호출 중 오류 발생: {e}")

        return None


# 기존 함수 이름으로 클래스 메소드 제공 (비동기 함수로 변경)
async def tokenize_tiktoken(text: str, model: str) -> int:
    return await TokenizerService.tokenize_tiktoken(text, model)


async def tokenize_transformers(text: str, model: str) -> int:
    return await TokenizerService.tokenize_transformers(text, model)


async def tokenize_ncp(text: str, model: str) -> int:
    return await TokenizerService.tokenize_ncp(text, model)
