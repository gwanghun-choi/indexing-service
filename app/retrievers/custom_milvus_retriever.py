"""
커스텀 Milvus Retriever

PyMilvus AsyncMilvusClient를 사용하여 2단계 검색(Meta -> Vector)을 수행합니다.
커스텀 임베딩 클래스(라운드 로빈)와 호환됩니다.

LightRAG 통합:
- Entity 컬렉션 검색 (엔티티 유사도 기반)
- graph_info 메타데이터 포함
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.config.database.async_milvus import async_search
from app.utils.embedding import embed_query
from app.utils.initialization import ensure_collection_loaded

logger = logging.getLogger(__name__)


class CustomMilvusRetriever(BaseRetriever):
    """
    커스텀 Milvus Retriever

    2단계 검색 프로세스:
    1. Meta 컬렉션 검색 (문서 레벨 요약 + 필터링)
    2. Vector 컬렉션 검색 (청크 레벨 상세 검색)

    LightRAG 통합:
    - Entity 컬렉션 검색 지원
    - graph_info 메타데이터 포함
    """

    group_id: int
    total_role: List[int]
    limit: int
    category_filter: Optional[List[str]] = None
    hash_sha256_filter: Optional[List[str]] = None
    meta_score_threshold: float = 0.7
    # LightRAG 관련 옵션
    include_graph_search: bool = False
    graph_entity_keywords: Optional[List[str]] = None
    graph_max_hops: int = 1

    def _get_relevant_documents(self, query: str) -> List[Document]:
        """동기 검색"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._aget_relevant_documents(query))

    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """비동기 검색 (2단계 + 선택적 Graph 검색)"""
        try:
            # 1단계: 쿼리 임베딩 생성
            query_embedding = await embed_query(query)

            # 2단계: Meta 컬렉션 검색
            meta_docs_info = await self._search_meta_collection(query_embedding)

            # Graph 검색 결과 (선택적)
            graph_docs_info: Dict[str, Dict[str, Any]] = {}

            if self.include_graph_search and self.graph_entity_keywords:
                # Entity 검색을 통한 그래프 확장
                graph_docs_info = await self._search_entity_collection(
                    keywords=self.graph_entity_keywords,
                    max_hops=self.graph_max_hops,
                )
                logger.info(
                    f"Entity 검색 완료: {len(graph_docs_info)}개 문서 발견"
                )

            # Meta와 Graph 결과 합치기
            combined_docs_info = self._merge_search_results(
                meta_docs_info, graph_docs_info
            )

            if not combined_docs_info:
                logger.info(
                    f"검색 결과 없음 (Meta threshold >= {self.meta_score_threshold})"
                )
                return []

            # 3단계: Vector 컬렉션 검색
            hash_list = list(combined_docs_info.keys())
            vector_results = await self._search_vector_collection(
                query_embedding, hash_list
            )

            # 4단계: LangChain Document 변환 (graph_info 포함)
            documents = self._build_documents(vector_results, combined_docs_info)

            search_type = "Meta + Graph" if graph_docs_info else "Meta"
            logger.info(
                f"검색 완료: {len(documents)}개 문서 ({search_type} -> Vector)"
            )
            return documents

        except Exception as e:
            logger.error(f"검색 중 오류 발생: {e}")
            raise

    async def _search_meta_collection(
        self, query_embedding: List[float]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Meta 컬렉션 검색 및 필터링

        Returns:
            hash_sha256을 키로 하고 메타 정보(title, filename)를 값으로 하는 딕셔너리
        """
        try:
            # 필터 표현식 생성
            role_filter = " or ".join(
                [f"array_contains(role_ids, {rid})" for rid in self.total_role]
            )
            current_time = int(datetime.now(ZoneInfo("Asia/Seoul")).timestamp())
            expr = f"({role_filter}) and expiration_date > {current_time}"

            if self.category_filter:
                expr += f" and category in {self.category_filter}"
                logger.debug(f"카테고리 필터 적용: {self.category_filter}")
            if self.hash_sha256_filter:
                expr += f" and hash_sha256 in {self.hash_sha256_filter}"
                logger.debug(
                    f"해시 필터 적용: {len(self.hash_sha256_filter)}개 문서"
                )

            logger.debug(
                f"Meta 검색 필터: role_ids={self.total_role}, 만료일>{current_time}"
            )

            # 컬렉션 준비
            collection_name = f"TB_{self.group_id}_meta"
            await ensure_collection_loaded(collection_name, "meta")

            meta_limit = min(self.limit * 2, 50)

            # 검색 파라미터 설정 (COSINE 메트릭 사용)
            search_params = {"metric_type": "COSINE"}

            meta_results = await async_search(
                collection_name=collection_name,
                data=[query_embedding],
                anns_field="embedding_value",
                search_params=search_params,
                output_fields=["hash_sha256", "title", "filename"],
                limit=meta_limit,
                filter=expr,
            )

            # 결과 필터링 및 추출
            meta_docs_info = {}
            filtered_by_threshold = 0
            total_meta_results = len(meta_results[0]) if meta_results else 0

            if meta_results:
                for result in meta_results[0]:
                    entity = result["entity"]
                    hash_val = entity["hash_sha256"]
                    if hash_val:
                        distance = result.get("distance", 0)
                        if distance >= self.meta_score_threshold:
                            meta_docs_info[hash_val] = {
                                "title": entity["title"],
                                "filename": entity["filename"],
                            }
                        else:
                            filtered_by_threshold += 1

            logger.info(
                f"Meta 컬렉션 검색 완료: 총 {total_meta_results}개 -> "
                f"선별 {len(meta_docs_info)}개 문서 "
                f"(threshold({self.meta_score_threshold}) 미달 제외={filtered_by_threshold}개)"
            )

            return meta_docs_info

        except Exception as e:
            logger.error(f"Meta 컬렉션 검색 중 오류: {e}")
            raise

    async def _search_vector_collection(
        self, query_embedding: List[float], hash_list: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Vector 컬렉션 검색 (상세 청크 검색)
        """
        try:
            collection_name = f"TB_{self.group_id}_vector"
            await ensure_collection_loaded(collection_name, "vector")

            filter_expr = " or ".join([f'hash_sha256 == "{h}"' for h in hash_list])

            # 검색 파라미터 설정 (COSINE 메트릭 사용)
            search_params = {"metric_type": "COSINE"}

            vector_results = await async_search(
                collection_name=collection_name,
                data=[query_embedding],
                anns_field="embedding_value",
                search_params=search_params,
                filter=filter_expr,
                output_fields=[
                    "id",
                    "hash_sha256",
                    "parsed_text",
                    "page_number",
                    "chunk_index",
                    "filename",
                    "category",
                    "title",
                ],
                limit=self.limit,
            )

            # 결과를 리스트로 변환
            results = []
            if vector_results:
                for result in vector_results[0]:
                    entity = result["entity"]
                    results.append({
                        "id": result["id"],
                        "hash_sha256": entity["hash_sha256"],
                        "parsed_text": entity["parsed_text"],
                        "page_number": entity["page_number"],
                        "chunk_index": entity["chunk_index"],
                        "filename": entity["filename"],
                        "category": entity["category"],
                        "title": entity["title"],
                        "distance": result["distance"],
                    })

            logger.info(
                f"Vector 컬렉션 검색 완료: {len(hash_list)}개 문서에서 "
                f"{len(results)}개 청크 검색 (limit={self.limit})"
            )

            return results

        except Exception as e:
            logger.error(f"Vector 컬렉션 검색 중 오류: {e}")
            raise

    def _build_documents(
        self, vector_results: List[Dict[str, Any]], meta_docs_info: Dict[str, Dict[str, Any]]
    ) -> List[Document]:
        """
        검색 결과를 LangChain Document 객체로 변환

        Note: Vector 검색에서는 threshold 없이 topK 결과를 모두 반환.
              최종 threshold 필터링은 Hybrid Search 단계에서 수행.
        """
        documents = []
        seen_texts = set()

        for result in vector_results:
            hash_value = result["hash_sha256"]
            text = result["parsed_text"]

            if text in seen_texts or hash_value not in meta_docs_info:
                continue

            seen_texts.add(text)
            meta_info = meta_docs_info[hash_value]

            # 메타데이터 구성
            metadata = {
                "id": result["id"],
                "title": meta_info["title"],
                "filename": meta_info["filename"],
                "hash_sha256": hash_value,
                "page_number": result["page_number"],
                "chunk_index": result["chunk_index"],
                "score": float(result["distance"]),
                "category": result["category"],
            }

            # graph_info가 있으면 추가
            if "graph_info" in meta_info:
                metadata["graph_info"] = meta_info["graph_info"]

            documents.append(
                Document(
                    page_content=text,
                    metadata=metadata,
                )
            )

        return documents

    async def _search_entity_collection(
        self,
        keywords: List[str],
        max_hops: int = 1,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Entity 컬렉션 검색을 통한 그래프 확장

        Args:
            keywords: Low-level 키워드 (엔티티 이름)
            max_hops: 최대 탐색 홉 수

        Returns:
            hash_sha256을 키로 하고 메타 정보 + graph_info를 값으로 하는 딕셔너리
        """
        # 지연 임포트로 순환 참조 방지
        from app.crud.milvus import search_entities

        try:
            graph_docs_info: Dict[str, Dict[str, Any]] = {}
            matched_entities: List[Dict[str, Any]] = []

            # 1. 키워드로 엔티티 검색
            for keyword in keywords:
                entities = await search_entities(
                    group_id=self.group_id,
                    query=keyword,
                    role_ids=self.total_role,
                    top_k=10,
                )
                for entity in entities:
                    if entity not in matched_entities:
                        matched_entities.append(entity)

            if not matched_entities:
                logger.info(f"Entity 검색 결과 없음: keywords={keywords}")
                return {}

            logger.info(f"매칭된 엔티티 수: {len(matched_entities)}개")

            # 2. 매칭된 엔티티에서 그래프 탐색 (Multi-hop)
            for entity in matched_entities:
                # 필수 필드가 없으면 건너뛰기
                if "entity_name" not in entity or "source_hashes" not in entity:
                    logger.info(f"필수 필드 누락으로 건너뛰기: {entity}")
                    continue

                entity_name = entity["entity_name"]
                entity_type = entity["entity_type"]
                source_hashes = entity["source_hashes"]

                # entity_name이 빈 문자열이면 건너뛰기
                if not entity_name:
                    logger.info("entity_name 빈 문자열로 건너뛰기")
                    continue

                logger.info(
                    f"엔티티 처리: name='{entity_name}', type='{entity_type}', "
                    f"source_hashes={len(source_hashes)}개"
                )

                # 직접 연결된 문서 (0-hop)
                for hash_val in source_hashes:
                    if hash_val not in graph_docs_info:
                        graph_docs_info[hash_val] = {
                            "title": "",
                            "filename": "",
                            "graph_info": {
                                "matched_entity": {
                                    "name": entity_name,
                                    "type": entity_type,
                                },
                                "hop": 0,
                                "relation_path": [entity_name],
                            },
                        }

                # 관계 기반 멀티홉 탐색은 비활성화됨 (관계 CRUD 제거)

            return graph_docs_info

        except Exception as e:
            logger.error(f"Entity 컬렉션 검색 중 오류: {e}", exc_info=True)
            return {}

    def _merge_search_results(
        self,
        meta_docs_info: Dict[str, Dict[str, Any]],
        graph_docs_info: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Meta 검색 결과와 Graph 검색 결과 병합

        규칙: 해시가 겹칠 경우 Graph RAG 정보(graph_info)를 우선 포함

        Args:
            meta_docs_info: Meta 컬렉션 검색 결과
            graph_docs_info: Entity 컬렉션 검색 결과

        Returns:
            병합된 검색 결과
        """
        combined = dict(meta_docs_info)

        for hash_val, graph_info in graph_docs_info.items():
            if hash_val in combined:
                # Meta에도 있는 경우: graph_info만 추가
                combined[hash_val]["graph_info"] = graph_info.get("graph_info")
            else:
                # Graph에만 있는 경우: 전체 추가
                combined[hash_val] = graph_info

        return combined
