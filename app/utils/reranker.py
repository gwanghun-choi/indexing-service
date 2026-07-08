from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

try:
    from pymilvus import WeightedRanker, RRFRanker

    RERANKER_AVAILABLE = True
except ImportError:
    logger.warning(
        "pymilvus not installed or does not support reranking, reranker functionality will be disabled"
    )
    RERANKER_AVAILABLE = False


class MilvusRerankerFactory:
    """Milvus 리랭커 생성 및 적용을 위한 팩토리 클래스 (싱글톤 패턴)

    Milvus의 두 가지 리랭킹 전략(WeightedRanker, RRFRanker)을 생성하고
    검색 결과에 적용하는 기능을 제공합니다.
    """

    # 클래스 변수 (상수)
    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "MilvusRerankerFactory":
        """싱글톤 인스턴스 생성"""
        if cls._instance is None:
            cls._instance = super(MilvusRerankerFactory, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """리랭커 팩토리 초기화"""
        # 이미 초기화된 경우 중복 초기화 방지
        if getattr(self, "_initialized", False):
            return

        self.available = RERANKER_AVAILABLE
        if not self.available:
            logger.warning("Milvus reranking functionality is not available ⚠️")

        self._initialized = True
        logger.debug("MilvusRerankerFactory initialized")

    def create_weighted_ranker(self, *weights: float) -> Optional[WeightedRanker]:
        """
        가중치 기반 리랭커 생성

        Milvus의 WeightedRanker는 여러 벡터 필드의 검색 결과를 가중치에 따라 결합합니다.
        각 벡터 필드에 중요도에 따라 가중치를 할당하고, 정규화된 점수에 가중치를 적용하여 최종 점수를 계산합니다.
        가중치 값은 0(최소 중요도)부터 1(최대 중요도)까지의 범위를 가지며, 최종 결합 점수에 영향을 줍니다.

        Args:
            *weights: 각 검색 결과에 적용할 가중치 값(들). AnnSearchRequest 개수와 동일해야 합니다.
                      예: create_weighted_ranker(0.8, 0.7, 0.5)

        Returns:
            WeightedRanker: Milvus hybrid_search()에 사용할 WeightedRanker 객체
                           또는 reranker 기능이 비활성화된 경우 None
        """
        if not self.available:
            logger.warning("Milvus reranking functionality is not available ⚠️")
            return None

        try:
            if not weights:
                weights = [0.8, 0.8]  # 기본 가중치

            ranker = WeightedRanker(*weights)
            logger.info(f"Created WeightedRanker with weights: {weights} ✅")
            return ranker
        except Exception as e:
            logger.error(f"Failed to create WeightedRanker: {e} ❌")
            return None

    def create_rrf_ranker(self, k: int = 60) -> Optional[RRFRanker]:
        """
        순위 기반 RRF(Reciprocal Rank Fusion) 리랭커 생성

        RRF는 여러 벡터 필드의 검색 결과를 순위에 기반하여 결합하는 방식으로,
        각 필드의 중요도가 명확하지 않거나 모든 필드에 동등한 고려가 필요할 때 적합합니다.

        RRF 알고리즘은 각 검색 결과의 순위에 따라 점수를 계산하고, k는 스무딩 파라미터로 작용합니다.
        일반적으로 k는 60으로 설정됩니다.

        Args:
            k: 스무딩 파라미터 (기본값: 60)

        Returns:
            RRFRanker: Milvus hybrid_search()에 사용할 RRFRanker 객체
                      또는 reranker 기능이 비활성화된 경우 None
        """
        if not self.available:
            logger.warning("Milvus reranking functionality is not available ⚠️")
            return None

        try:
            ranker = RRFRanker(k=k)
            logger.info(f"Created RRFRanker with k={k} ✅")
            return ranker
        except Exception as e:
            logger.error(f"Failed to create RRFRanker: {e} ❌")
            return None

    def apply_reranking(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        strategy: str = "weighted",
        weights: Optional[List[float]] = None,
        top_k: Optional[int] = None,
        rrf_k: int = 60,
    ) -> List[Dict[str, Any]]:
        """
        텍스트 기반 검색 결과에 리랭킹 적용

        Milvus 리랭킹 알고리즘의 개념을 일반 검색 결과에 적용합니다.

        Args:
            query: 사용자 쿼리
            documents: 검색 결과 목록
            strategy: 리랭킹 전략 ('weighted' 또는 'rrf')
            weights: 가중치 리스트 (weighted 전략 사용 시)
            top_k: 반환할 상위 결과 수 (None인 경우 모든 결과 반환)
            rrf_k: RRF 스무딩 파라미터 (rrf 전략 사용 시)

        Returns:
            List[Dict[str, Any]]: 리랭킹된 결과 목록
        """
        if not self.available or not documents:
            return documents

        try:
            logger.info(f"리랭킹 전략 적용: {strategy}")

            # 최대 결과 수 결정
            result_limit = min(top_k, len(documents)) if top_k else len(documents)

            # 리랭킹 전략에 따라 결과 재정렬
            if strategy.lower() == "weighted":
                # 가중치 기반 리랭킹 적용
                weight_value = weights[0] if weights and len(weights) > 0 else 0.8
                logger.debug(f"가중치 기반 리랭킹 적용: 가중치={weight_value}")

                # 점수 정규화 및 가중치 적용
                for doc in documents:
                    # 기존 점수를 [0,1] 범위로 정규화 (Milvus 문서 참조)
                    normalized_score = min(max(doc["score"], 0), 1)
                    # 가중치 적용
                    doc["score"] = normalized_score * weight_value

            elif strategy.lower() == "rrf":
                # RRF 기반 리랭킹 적용
                k_value = rrf_k if rrf_k else 60
                logger.debug(f"RRF 기반 리랭킹 적용: k={k_value}")

                # 기존 점수로 정렬
                documents_sorted = sorted(
                    documents, key=lambda doc: doc["score"], reverse=True
                )

                # RRF 점수 계산 및 적용
                for i, doc in enumerate(documents_sorted):
                    # RRF 공식: 1 / (rank + k)
                    rank = i + 1
                    doc["score"] = 1.0 / (rank + k_value)

                # documents 변수 업데이트
                documents = documents_sorted
            else:
                logger.warning(f"알 수 없는 리랭킹 전략: {strategy}, 원본 결과 반환 ⚠️")
                return documents

            # 결과 재정렬 및 제한
            reranked_results = sorted(
                documents, key=lambda doc: doc["score"], reverse=True
            )[:result_limit]

            logger.info(f"리랭킹 완료: 총 {len(reranked_results)}개 결과 ✅")
            return reranked_results

        except Exception as e:
            logger.error(f"리랭킹 적용 실패: {e} ❌")
            return documents  # 오류 발생 시 원본 결과 반환
