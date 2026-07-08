"""
RAGAS LLM 모델 마스터 CRUD

활성 모델 목록 조회, 모델 활성 여부 확인을 담당합니다.
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config.database.session import get_async_db_context
from app.entity.postgres.ragas_llm_model_entity import RagasLlmModel

logger = logging.getLogger(__name__)


class RagasLlmModelCRUD:
    """RAGAS LLM 모델 마스터 CRUD 클래스"""

    async def select_active_models(self) -> List[Dict[str, Any]]:
        """
        활성 모델 목록 조회

        Returns:
            활성 모델 리스트 (id, model_name, description)
        """
        try:
            async with get_async_db_context() as db:
                query = (
                    select(RagasLlmModel)
                    .where(RagasLlmModel.is_active.is_(True))
                    .order_by(RagasLlmModel.id)
                )
                result = await db.execute(query)
                models = result.scalars().all()

                return [
                    {
                        "id": m.id,
                        "model_name": m.model_name,
                        "description": m.description,
                    }
                    for m in models
                ]
        except SQLAlchemyError as e:
            logger.error(f"LLM 모델 목록 조회 실패: {e}")
            raise

    async def is_model_active(self, model_name: str) -> bool:
        """
        모델이 활성 상태인지 확인

        Args:
            model_name: 확인할 모델명

        Returns:
            활성이면 True, 미존재 또는 비활성이면 False
        """
        try:
            async with get_async_db_context() as db:
                query = select(RagasLlmModel).where(
                    RagasLlmModel.model_name == model_name
                )
                result = await db.execute(query)
                model = result.scalar_one_or_none()

                if model is None:
                    return False
                return model.is_active
        except SQLAlchemyError as e:
            logger.error(f"LLM 모델 확인 실패: {e}")
            raise
