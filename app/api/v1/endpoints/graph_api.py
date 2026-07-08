"""
Graph RAG API

엔티티/관계 관리 및 Dual-Level 그래프 검색 API
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.crud.postgres import (
    delete_entity_type,
    select_all_entity_types,
    create_default_entity_types,
    create_entity_type as crud_create_entity_type,
    update_entity_type,
)
from app.dto.graph_dto import (
    DualLevelSearchRequestDTO,
    DualLevelSearchResponseDTO,
    EntityTypeCreateRequestDTO,
    EntityTypeDTO,
    EntityTypeUpdateRequestDTO,
)
from app.service.lightrag_service import search_graph_with_dual_level
from app.utils.auth_utils import get_parsed_jwt_data

logger = logging.getLogger(__name__)

router = APIRouter(
    responses={
        400: {"description": "잘못된 요청 - 요청 매개변수가 유효하지 않습니다."},
        401: {"description": "인증 실패 - 유효한 인증 정보가 필요합니다."},
        403: {"description": "권한 부족 - 요청된 작업에 대한 권한이 없습니다."},
        404: {"description": "찾을 수 없음 - 요청된 리소스가 존재하지 않습니다."},
        500: {"description": "서버 오류 - 서버 내부 오류가 발생했습니다."},
    },
)


# ============================================================
# Entity Type Management APIs (Admin)
# ============================================================


@router.get(
    "/entity-types",
    summary="엔티티 타입 목록 조회",
    response_model=List[EntityTypeDTO],
    description="""
**엔티티 타입 목록 조회**

Admin이 관리하는 엔티티 타입 목록을 조회합니다.
이 타입들은 문서 인덱싱 시 엔티티 추출 프롬프트에 동적으로 적용됩니다.
""",
)
async def get_entity_types(
    jwt_data: Dict = Depends(get_parsed_jwt_data),
) -> List[EntityTypeDTO]:
    """엔티티 타입 목록 조회"""
    try:
        types = await select_all_entity_types()
        return [EntityTypeDTO(**t) for t in types]

    except Exception as e:
        logger.error(f"엔티티 타입 조회 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/entity-types",
    summary="엔티티 타입 추가",
    response_model=Dict[str, Any],
    description="""
**엔티티 타입 추가 (Admin 전용)**

새로운 엔티티 타입을 추가합니다.
추가된 타입은 즉시 엔티티 추출 프롬프트에 반영됩니다.
""",
)
async def create_entity_type(
    request: EntityTypeCreateRequestDTO,
    jwt_data: Dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """엔티티 타입 추가"""
    try:
        type_id = await crud_create_entity_type(
            type_key=request.type_key,
            type_name=request.type_name,
            description=request.description,
        )

        return {
            "result": True,
            "message": f"엔티티 타입 '{request.type_key}' 추가 완료",
            "type_id": type_id,
        }

    except Exception as e:
        logger.error(f"엔티티 타입 추가 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/entity-types/{type_id}",
    summary="엔티티 타입 수정",
    response_model=Dict[str, Any],
    description="""
**엔티티 타입 수정 (Admin 전용)**

기존 엔티티 타입의 이름이나 설명을 수정합니다.
""",
)
async def update_entity_type_api(
    type_id: int,
    request: EntityTypeUpdateRequestDTO,
    jwt_data: Dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """엔티티 타입 수정"""
    try:
        update_data = {}
        if request.type_name is not None:
            update_data["type_name"] = request.type_name
        if request.description is not None:
            update_data["description"] = request.description

        if not update_data:
            raise HTTPException(status_code=400, detail="수정할 내용이 없습니다.")

        success = await update_entity_type(type_id, update_data)

        if success:
            return {
                "result": True,
                "message": f"엔티티 타입 수정 완료 (id={type_id})",
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"엔티티 타입을 찾을 수 없습니다: id={type_id}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"엔티티 타입 수정 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/entity-types/{type_id}",
    summary="엔티티 타입 삭제",
    response_model=Dict[str, Any],
    description="""
**엔티티 타입 삭제 (Admin 전용)**

엔티티 타입을 삭제합니다.
삭제 시 해당 타입으로 추출된 기존 엔티티들은 영향받지 않습니다.
""",
)
async def delete_entity_type_api(
    type_id: int,
    jwt_data: Dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """엔티티 타입 삭제"""
    try:
        success = await delete_entity_type(type_id)

        if success:
            return {
                "result": True,
                "message": f"엔티티 타입 삭제 완료 (id={type_id})",
            }
        else:
            raise HTTPException(
                status_code=404, detail=f"엔티티 타입을 찾을 수 없습니다: id={type_id}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"엔티티 타입 삭제 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/entity-types/initialize",
    summary="기본 엔티티 타입 초기화",
    response_model=Dict[str, Any],
    description="""
**기본 엔티티 타입 초기화 (Admin 전용)**

기본 엔티티 타입들(person, organization, location, event, project, concept, document, date)을
데이터베이스에 추가합니다. 이미 존재하는 타입은 건너뜁니다.
""",
)
async def initialize_default_entity_types(
    jwt_data: Dict = Depends(get_parsed_jwt_data),
) -> Dict[str, Any]:
    """기본 엔티티 타입 초기화"""
    try:
        type_ids = await create_default_entity_types()

        return {
            "result": True,
            "message": f"{len(type_ids)}개 기본 엔티티 타입 초기화 완료",
            "type_ids": type_ids,
        }

    except Exception as e:
        logger.error(f"기본 엔티티 타입 초기화 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Graph Search APIs
# ============================================================


@router.post(
    "/search/dual-level",
    summary="Dual-Level 그래프 검색",
    response_model=DualLevelSearchResponseDTO,
    description="""
**Dual-Level 그래프 검색 (LightRAG 방식)**

쿼리에서 Low-level(엔티티)과 High-level(주제/관계) 키워드를 추출하여
그래프 기반 검색을 수행합니다.

## 검색 흐름
1. 쿼리에서 Dual-Level 키워드 추출
   - Low-level: 구체적인 엔티티 이름, 날짜, 장소 등
   - High-level: 추상적인 주제, 관계, 개념 등
2. Low-level 키워드로 엔티티 검색 (정확 매칭)
3. 매칭된 엔티티에서 Multi-hop 그래프 탐색
4. 결과 통합 및 반환

## 사용 예시
```bash
curl -X POST "/api/v1/graph/search/dual-level" \\
  -H "Authorization: Bearer {token}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "홍길동이 참여한 AI 프로젝트 관련 문서",
    "max_hops": 2,
    "relation_types": ["participates_in", "authored_by"]
  }'
```
""",
)
async def search_dual_level(
    request: DualLevelSearchRequestDTO,
    jwt_data: Dict = Depends(get_parsed_jwt_data),
) -> DualLevelSearchResponseDTO:
    """Dual-Level 그래프 검색"""
    try:
        group_id = jwt_data.get("group_id")
        if not group_id:
            raise HTTPException(status_code=400, detail="group_id가 필요합니다.")

        result = await search_graph_with_dual_level(
            query=request.query,
            group_id=group_id,
            max_hops=request.max_hops,
            relation_types=request.relation_types,
        )

        return DualLevelSearchResponseDTO(
            keywords=result.get("keywords", {"low_level": [], "high_level": []}),
            entity_matches=result.get("entity_matches", []),
            graph_results=result.get("graph_results", []),
            total_results=result.get("total_results", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dual-Level 검색 중 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

