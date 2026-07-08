"""
하이브리드 검색 (Dense + Sparse)
Milvus(Dense)와 BM25(Sparse) 검색 결과를 직접 Union하고 가중치를 적용합니다.
"""

import gc
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from langchain_classic.retrievers import MultiQueryRetriever
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.config.settings import get_settings
from app.retrievers.custom_milvus_retriever import CustomMilvusRetriever
from app.service.opensearch_bm25_service import (
    create_opensearch_client,
    search_with_filter,
)
from app.utils.reranker_client import call_reranker_service

logger = logging.getLogger(__name__)

# MultiQuery custom prompt (generates noun/keyword-based search terms)
MULTI_QUERY_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""Generate 3 keyword-based search queries for vector database retrieval.
Respond in the same language as the question.

Rules:
- Use nouns/noun phrases only, no full sentences
- Remove particles, endings, and filler words
- Use synonyms for diverse perspectives
- 2-5 core words per query

Q: What are the requirements for working from home?
Output:
remote work requirements
work from home eligibility criteria
telecommuting qualifications

Q: 재택근무를 하기 위해 필요한 자격 요건은 무엇인가요?
Output:
재택근무 자격 요건
재택근무 신청 자격 기준
재택근무 필수 조건

Q: 연차 휴가를 신청하는 방법이 궁금합니다
Output:
연차 휴가 신청 방법
연차 신청 절차
휴가 신청 프로세스

Q: {question}
Output:""",
)


class HybridSearchService:
    """
    하이브리드 검색 서비스

    Dense Vector (Milvus) + Sparse Vector (BM25)를 결합하여
    의미 기반 검색과 키워드 매칭을 동시에 수행합니다.

    리팩토링 후 변경사항:
    - EnsembleRetriever(RRF) 제거 → 직접 Union + 가중치 계산
    - BM25 점수 3단계 정규화 적용 (log1p → 분포 기반 게이트 → Min-Max)
    - threshold 파라미터로 최종 필터링
    """

    def __init__(self):
        """초기화"""
        self.settings = get_settings()
        self.os_client = create_opensearch_client()

    def cleanup(self):
        """리소스 정리 및 가비지 컬렉션"""
        if hasattr(self, "os_client") and self.os_client:
            self.os_client.close()
            logger.debug("✅ HybridSearch OpenSearch 연결 종료")

        gc.collect()
        logger.debug("✅ HybridSearchService 리소스 정리 및 GC 완료")

    async def search(
        self,
        query: str,
        group_id: int,
        total_role: List[int],
        limit: int,
        search_mode: str,
        dense_weight: float,
        sparse_weight: float,
        rerank_top_n: int,
        use_multi_query: bool,
        threshold: float,
        user_passport: str,
        category_filter: Optional[List[str]] = None,
        hash_sha256_filter: Optional[List[str]] = None,
        reranker: Optional[str] = None,
        cohere_api_key: Optional[str] = None,
        # Graph RAG 파라미터
        include_graph_search: bool = False,
        graph_entity_keywords: Optional[List[str]] = None,
        graph_max_hops: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 수행 (Dense + Sparse + MultiQuery + Reranker)

        리팩토링 후 변경된 흐름:
        1. Dense 검색 (Milvus): topK개 결과 + score
        2. BM25 검색 (Redis): topK개 결과 + 정규화된 score + 권한 필터
        3. Union: 두 결과 합치기 (중복 처리)
        4. 가중치 계산: dense_score * dense_weight + bm25_score * sparse_weight
        5. Threshold 필터링: score < threshold인 문서 제거
        6. TopK 반환

        Args:
            query: 검색 쿼리 (필수)
            group_id: 그룹 ID (필수)
            total_role: 역할 ID 리스트 (필수)
            limit: 반환할 최대 결과 수 (필수)
            search_mode: 검색 모드 (필수, 'hybrid' 또는 'dense')
            dense_weight: Dense 검색 가중치 (필수)
            sparse_weight: Sparse 검색 가중치 (필수)
            rerank_top_n: Reranker 최종 반환 개수 (필수)
            use_multi_query: MultiQueryRetriever 사용 여부 (필수)
            threshold: 최종 결과 필터링 threshold (기본값 0.0 = 필터링 없음)
            user_passport: x-user-passport 헤더 값 (필수, Reranker 인증용)
            category_filter: 카테고리 필터 (선택적)
            hash_sha256_filter: 해시 필터 (선택적)
            reranker: Reranker 선택 (선택적)
            cohere_api_key: Cohere API 키 (선택적)

        Returns:
            검색 결과 리스트
        """
        milvus_retriever = None
        multi_query_retriever = None
        llm = None

        try:
            logger.info(
                f"🔍 검색 시작 (mode={search_mode}): query='{query[:50]}...', group_id={group_id}"
            )

            # 1. Dense 검색 (Milvus) - score 포함 + Graph RAG 통합
            milvus_retriever = CustomMilvusRetriever(
                group_id=group_id,
                total_role=total_role,
                limit=limit,
                category_filter=category_filter,
                hash_sha256_filter=hash_sha256_filter,
                # Graph RAG 옵션
                include_graph_search=include_graph_search,
                graph_entity_keywords=graph_entity_keywords,
                graph_max_hops=graph_max_hops,
            )

            if include_graph_search:
                logger.info(
                    f"🕸️ Graph RAG 활성화: keywords={graph_entity_keywords}, max_hops={graph_max_hops}"
                )

            # MultiQueryRetriever 적용 (선택적)
            if use_multi_query:
                logger.info("🔄 MultiQueryRetriever 사용: LLM으로 쿼리 확장 중...")
                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0,
                    openai_api_key=self.settings.OPENAI_API_KEY,
                )
                multi_query_retriever = MultiQueryRetriever.from_llm(
                    retriever=milvus_retriever,
                    llm=llm,
                    prompt=MULTI_QUERY_PROMPT,
                )
                dense_documents = await multi_query_retriever.ainvoke(query)
                logger.info(
                    f"✅ MultiQueryRetriever 완료: {len(dense_documents)}개 문서"
                )
            else:
                dense_documents = await milvus_retriever.ainvoke(query)
                logger.info(f"📊 Dense 검색 완료: {len(dense_documents)}개 문서 반환")

            # 2. 검색 모드에 따른 분기 처리
            if search_mode == "dense":
                logger.info("📊 Dense 검색 모드: 벡터 유사도만 사용")
                # Dense 결과에 dense_score, sparse_score 추가 및 가중치 적용
                for doc in dense_documents:
                    doc.metadata["dense_score"] = doc.metadata["score"]
                    doc.metadata["sparse_score"] = 0.0
                    # Dense 가중치 적용
                    doc.metadata["score"] = doc.metadata["score"] * dense_weight
                final_documents = dense_documents

            else:
                # 3. BM25 검색 (OpenSearch + 권한 필터 적용)
                current_time = int(datetime.now(ZoneInfo("Asia/Seoul")).timestamp())

                bm25_results = search_with_filter(
                    client=self.os_client,
                    group_id=group_id,
                    query=query,
                    role_ids=total_role,
                    current_time=current_time,
                    top_k=limit,
                )

                logger.info(f"📊 BM25 검색 결과: {len(bm25_results)}개 문서")

                if not bm25_results:
                    logger.warning(
                        f"⚠️ BM25 검색 결과 없음: group_id={group_id} → Dense 결과만 사용"
                    )
                    # Dense 결과에 dense_score, sparse_score 추가 및 가중치 적용
                    for doc in dense_documents:
                        doc.metadata["dense_score"] = doc.metadata["score"]
                        doc.metadata["sparse_score"] = 0.0
                        # Dense 가중치 적용
                        doc.metadata["score"] = doc.metadata["score"] * dense_weight
                    final_documents = dense_documents
                else:
                    # 4. Union + 가중치 계산
                    union_results = self._union_results(
                        dense_docs=dense_documents,
                        bm25_results=bm25_results,
                        dense_weight=dense_weight,
                        sparse_weight=sparse_weight,
                    )
                    logger.info(f"📊 Union 결과: {len(union_results)}개 문서")

                    # 5. Threshold 필터링
                    filtered_results = self._apply_threshold(
                        results=union_results,
                        threshold=threshold,
                    )
                    logger.info(
                        f"📊 Threshold 필터링 후: {len(filtered_results)}개 문서 (threshold={threshold})"
                    )

                    # 결과를 Document 객체로 변환 (Reranker 호환용)
                    final_documents = []
                    for result in filtered_results:
                        doc_metadata = {
                            "id": result["id"],
                            "score": result["score"],
                            "dense_score": result["dense_score"],
                            "sparse_score": result["bm25_score"],
                            "hash_sha256": result["hash_sha256"],
                            "filename": result["filename"],
                            "page_number": result["page_number"],
                            "chunk_index": result["chunk_index"],
                            "title": result["title"],
                            "category": result["category"],
                        }
                        # graph_info가 있으면 추가
                        if "graph_info" in result:
                            doc_metadata["graph_info"] = result["graph_info"]

                        final_documents.append(
                            Document(page_content=result["parsed_text"], metadata=doc_metadata)
                        )

            # 6. Reranker 적용 (선택적)
            if reranker and final_documents:
                logger.info(f"🎯 Reranker 적용 시작: {reranker}, top_n={rerank_top_n}")
                final_documents = await self._apply_reranker(
                    query=query,
                    documents=final_documents,
                    reranker_type=reranker,
                    top_n=rerank_top_n,
                    user_passport=user_passport,
                    cohere_api_key=cohere_api_key,
                )
                logger.info(f"✅ Reranker 완료: {len(final_documents)}개 결과")

            # 7. 결과 변환
            final_limit = rerank_top_n if reranker else limit
            results = self._convert_documents_to_results(
                documents=final_documents,
                limit=final_limit,
                group_id=group_id,
                threshold=threshold,
            )

            logger.info(f"✅ 최종 검색 완료: {len(results)}개 결과")
            return results

        except Exception as e:
            logger.error(f"❌ 하이브리드 검색 실패: {e}")
            raise

        finally:
            if milvus_retriever:
                del milvus_retriever
            if multi_query_retriever:
                del multi_query_retriever
            if llm:
                del llm

            gc.collect()
            logger.debug("✅ 검색 완료 후 메모리 정리 (GC 실행)")

    def _union_results(
        self,
        dense_docs: List[Document],
        bm25_results: List[Dict[str, Any]],
        dense_weight: float,
        sparse_weight: float,
    ) -> List[Dict[str, Any]]:
        """
        Dense와 BM25 결과 Union 및 가중치 적용

        Args:
            dense_docs: Dense 검색 결과 (Document 리스트)
            bm25_results: BM25 검색 결과 (dict 리스트)
            dense_weight: Dense 가중치
            sparse_weight: BM25 가중치

        Returns:
            통합된 결과 리스트 (최종 score 포함)
        """
        # 키: parsed_text → 결과 딕셔너리
        result_map: Dict[str, Dict[str, Any]] = {}

        # 1. Dense 결과 추가
        for doc in dense_docs:
            metadata = doc.metadata
            key = doc.page_content

            result_item = {
                "id": metadata["id"],
                "parsed_text": doc.page_content,
                "hash_sha256": metadata["hash_sha256"],
                "filename": metadata["filename"],
                "page_number": metadata["page_number"],
                "chunk_index": metadata["chunk_index"],
                "title": metadata["title"],
                "category": metadata["category"],
                "dense_score": metadata["score"],
                "bm25_score": 0.0,  # BM25에 없으면 0
            }

            # graph_info가 있으면 추가
            if "graph_info" in metadata:
                result_item["graph_info"] = metadata["graph_info"]

            result_map[key] = result_item

        # 2. BM25 결과 추가/병합
        for bm25_item in bm25_results:
            bm25_doc = bm25_item["document"]
            key = bm25_doc.page_content

            if key in result_map:
                # 기존 Dense 결과에 BM25 점수 추가
                result_map[key]["bm25_score"] = bm25_item["score"]
            else:
                # BM25에만 있는 결과 추가
                result_map[key] = {
                    "id": bm25_item.get("id"),
                    "parsed_text": bm25_doc.page_content,
                    "hash_sha256": bm25_item["hash_sha256"],
                    "filename": bm25_item["filename"],
                    "page_number": bm25_item["page_number"],
                    "chunk_index": bm25_item["chunk_index"],
                    "title": bm25_item["title"],
                    "category": bm25_doc.metadata["category"],
                    "dense_score": 0.0,  # Dense에 없으면 0
                    "bm25_score": bm25_item["score"],
                }

        # 3. 가중치 적용 및 최종 점수 계산
        results = []
        for item in result_map.values():
            final_score = (
                item["dense_score"] * dense_weight + item["bm25_score"] * sparse_weight
            )
            item["score"] = final_score
            results.append(item)

        # 4. 점수 내림차순 정렬
        results.sort(key=lambda result: result["score"], reverse=True)

        return results

    def _apply_threshold(
        self,
        results: List[Dict[str, Any]],
        threshold: float,
    ) -> List[Dict[str, Any]]:
        """
        Threshold 기준으로 결과 필터링

        Args:
            results: 검색 결과 리스트
            threshold: 최소 점수 기준

        Returns:
            필터링된 결과 리스트
        """
        if threshold <= 0.0:
            return results

        filtered = [result for result in results if result["score"] >= threshold]

        logger.debug(
            f"📊 Threshold 필터링: {len(results)}개 → {len(filtered)}개 (threshold={threshold})"
        )

        return filtered

    async def _apply_reranker(
        self,
        query: str,
        documents: List[Document],
        reranker_type: str,
        top_n: int,
        user_passport: str,
        cohere_api_key: Optional[str] = None,
    ) -> List[Document]:
        """
        Reranker 적용 (원격 서비스 호출)

        Args:
            query: 검색 쿼리
            documents: 재정렬할 문서 리스트
            reranker_type: 'cohere' 또는 'flashrank'
            top_n: 최종 반환 개수
            user_passport: x-user-passport 헤더 값 (필수, 인증용)
            cohere_api_key: Cohere API 키 (reranker_type='cohere'인 경우 필수)

        Returns:
            재정렬된 Document 리스트
        """
        if not documents:
            return documents

        try:
            # Document를 dict로 변환
            doc_dicts = [
                {
                    "id": doc.metadata["id"],
                    "parsed_text": doc.page_content,
                    "hash_sha256": doc.metadata["hash_sha256"],
                    "filename": doc.metadata["filename"],
                    "page_number": doc.metadata["page_number"],
                    "chunk_index": doc.metadata["chunk_index"],
                    "title": doc.metadata["title"],
                    "category": doc.metadata["category"],
                    "score": doc.metadata["score"],
                    "dense_score": doc.metadata["dense_score"],
                    "sparse_score": doc.metadata["sparse_score"],
                }
                for doc in documents
            ]

            # 원격 서비스 호출
            result = await call_reranker_service(
                query=query,
                documents=doc_dicts,
                reranker_type=reranker_type,
                top_n=top_n,
                user_passport=user_passport,
                cohere_api_key=cohere_api_key,
            )

            # 응답을 Document로 변환
            reranked_docs = []
            for item in result["results"]:
                metadata = {
                    "id": item.get("id"),
                    "hash_sha256": item["hash_sha256"],
                    "filename": item["filename"],
                    "page_number": item["page_number"],
                    "chunk_index": item["chunk_index"],
                    "title": item["title"],
                    "category": item["category"],
                    "score": item["rerank_score"],
                    "dense_score": item["dense_score"],
                    "sparse_score": item["sparse_score"],
                    "rerank_score": item["rerank_score"],
                }
                reranked_docs.append(
                    Document(page_content=item["parsed_text"], metadata=metadata)
                )

            return reranked_docs

        except Exception as e:
            logger.error(f"❌ Reranker 서비스 호출 실패: {e}, 원본 결과 반환")
            return documents[:top_n]

    def _convert_documents_to_results(
        self,
        documents: List[Document],
        limit: int,
        group_id: int,
        threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        LangChain Document를 결과 형식으로 변환

        Args:
            documents: LangChain Document 리스트
            limit: 반환할 최대 결과 수
            group_id: 그룹 ID
            threshold: 최소 점수 기준

        Returns:
            변환된 결과 리스트
        """
        results = []
        seen_texts = set()  # 중복 제거

        for doc in documents:
            # 중복 제거
            text = doc.page_content
            if text in seen_texts:
                continue
            seen_texts.add(text)

            # 메타데이터 추출
            metadata = doc.metadata
            score = metadata["score"]

            # Threshold 필터링 (Dense 모드에서 사용)
            if threshold > 0.0 and score < threshold:
                continue

            result = {
                "id": metadata["id"],
                "score": score,
                "dense_score": metadata["dense_score"],
                "sparse_score": metadata["sparse_score"],
                "group_id": group_id,
                "filename": metadata["filename"],
                "parsed_text": text,
                "page_number": metadata["page_number"],
                "chunk_index": metadata["chunk_index"],
                "hash_sha256": metadata["hash_sha256"],
            }

            # graph_info가 있으면 포함
            if "graph_info" in metadata:
                result["graph_info"] = metadata["graph_info"]

            results.append(result)

            if len(results) >= limit:
                break

        # Score 내림차순 정렬
        results.sort(key=lambda result: result["score"], reverse=True)

        logger.debug(f"📊 변환 완료: {len(results)}개 결과")
        return results


def get_hybrid_search_service() -> HybridSearchService:
    """
    하이브리드 검색 서비스 인스턴스 생성

    Returns:
        HybridSearchService 인스턴스
    """
    return HybridSearchService()
