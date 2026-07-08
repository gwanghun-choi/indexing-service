"""
엔티티 타입 마스터 CRUD (PostgreSQL)

Admin이 관리하는 엔티티 타입 CRUD 함수
"""

import logging
from typing import List, Dict, Optional, Any

from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError

from app.config.database.session import get_async_db_context
from app.entity.postgres.entity_type_master_entity import EntityTypeMaster

logger = logging.getLogger(__name__)


# ------------------------------------------
# CREATE
# ------------------------------------------


async def create_entity_type(
    type_key: str,
    type_name: str,
    description: Optional[str] = None,
) -> int:
    """
    엔티티 타입 추가

    Args:
        type_key: 타입 키 (person, organization, ...)
        type_name: 타입 이름 (인물, 조직, ...)
        description: 타입 설명

    Returns:
        int: 생성된 타입 ID
    """
    try:
        async with get_async_db_context() as db:
            # 중복 확인
            existing = await select_entity_type_by_key(type_key)
            if existing:
                logger.info(f"✅ 엔티티 타입 '{type_key}' 이미 존재: id={existing['id']}")
                return existing["id"]

            entity_type = EntityTypeMaster(
                type_key=type_key,
                type_name=type_name,
                description=description,
            )

            db.add(entity_type)
            await db.commit()
            await db.refresh(entity_type)

            logger.info(f"✅ 엔티티 타입 추가: {type_key} ({type_name})")
            return entity_type.id

    except SQLAlchemyError as e:
        logger.error(f"❌ 엔티티 타입 추가 중 오류: {e}")
        raise


async def create_default_entity_types() -> List[int]:
    """
    기본 엔티티 타입들 추가

    Returns:
        List[int]: 생성된 타입 ID 리스트
    """
    default_types = [
        {"type_key": "person", "type_name": "인물", "description": "사람 이름, 직책"},
        {"type_key": "organization", "type_name": "조직", "description": "회사, 부서, 팀"},
        {"type_key": "location", "type_name": "장소", "description": "지역, 건물, 주소"},
        {"type_key": "event", "type_name": "이벤트", "description": "회의, 행사, 일정"},
        {"type_key": "project", "type_name": "프로젝트", "description": "프로젝트명, 과제"},
        {"type_key": "concept", "type_name": "개념", "description": "기술 용어, 정책"},
        {"type_key": "document", "type_name": "문서", "description": "보고서, 계약서 유형"},
        {"type_key": "date", "type_name": "날짜", "description": "기한, 기간"},
    ]

    type_ids = []
    for entity_type in default_types:
        type_id = await create_entity_type(
            type_key=entity_type["type_key"],
            type_name=entity_type["type_name"],
            description=entity_type["description"],
        )
        type_ids.append(type_id)

    logger.info(f"✅ {len(type_ids)}개 기본 엔티티 타입 추가 완료")
    return type_ids


# ------------------------------------------
# READ
# ------------------------------------------


async def select_entity_type_by_key(type_key: str) -> Optional[Dict[str, Any]]:
    """
    타입 키로 엔티티 타입 조회

    Args:
        type_key: 타입 키

    Returns:
        Optional[Dict]: 타입 정보 또는 None
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(
                select(EntityTypeMaster).where(EntityTypeMaster.type_key == type_key)
            )
            entity_type = result.scalar_one_or_none()

            if entity_type:
                return {
                    "id": entity_type.id,
                    "type_key": entity_type.type_key,
                    "type_name": entity_type.type_name,
                    "description": entity_type.description,
                }

            return None

    except SQLAlchemyError as e:
        logger.error(f"❌ 엔티티 타입 조회 중 오류: {e}")
        return None


async def select_all_entity_types() -> List[Dict[str, Any]]:
    """
    모든 엔티티 타입 조회

    Returns:
        List[Dict]: 엔티티 타입 목록
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(select(EntityTypeMaster))
            types = result.scalars().all()

            return [
                {
                    "id": t.id,
                    "type_key": t.type_key,
                    "type_name": t.type_name,
                    "description": t.description,
                }
                for t in types
            ]

    except SQLAlchemyError as e:
        logger.error(f"❌ 엔티티 타입 목록 조회 중 오류: {e}")
        return []


async def select_entity_types_for_prompt() -> str:
    """
    프롬프트용 엔티티 타입 문자열 생성

    Returns:
        str: "person(인물), organization(조직), ..." 형태
    """
    types = await select_all_entity_types()

    if not types:
        return "person(인물), organization(조직), project(프로젝트), location(장소), event(이벤트), concept(개념), document(문서), date(날짜)"

    return ", ".join([f"{t['type_key']}({t['type_name']})" for t in types])


# ------------------------------------------
# UPDATE
# ------------------------------------------


async def update_entity_type(
    type_id: int,
    update_data: Dict[str, Any],
) -> bool:
    """
    엔티티 타입 업데이트

    Args:
        type_id: 타입 ID
        update_data: 업데이트할 데이터

    Returns:
        bool: 성공 여부
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(
                select(EntityTypeMaster).where(EntityTypeMaster.id == type_id)
            )
            entity_type = result.scalar_one_or_none()

            if not entity_type:
                logger.warning(f"⚠️ 엔티티 타입을 찾을 수 없습니다: id={type_id}")
                return False

            for key, value in update_data.items():
                if hasattr(entity_type, key):
                    setattr(entity_type, key, value)

            await db.commit()

            logger.info(f"✅ 엔티티 타입 업데이트 완료: id={type_id}")
            return True

    except SQLAlchemyError as e:
        logger.error(f"❌ 엔티티 타입 업데이트 중 오류: {e}")
        return False


# ------------------------------------------
# DELETE
# ------------------------------------------


async def delete_entity_type(type_id: int) -> bool:
    """
    엔티티 타입 삭제

    Args:
        type_id: 타입 ID

    Returns:
        bool: 성공 여부
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(
                delete(EntityTypeMaster).where(EntityTypeMaster.id == type_id)
            )
            await db.commit()

            if result.rowcount > 0:
                logger.info(f"✅ 엔티티 타입 삭제 완료: id={type_id}")
                return True
            else:
                logger.warning(f"⚠️ 삭제할 엔티티 타입이 없습니다: id={type_id}")
                return False

    except SQLAlchemyError as e:
        logger.error(f"❌ 엔티티 타입 삭제 중 오류: {e}")
        return False


async def delete_entity_type_by_key(type_key: str) -> bool:
    """
    타입 키로 엔티티 타입 삭제

    Args:
        type_key: 타입 키

    Returns:
        bool: 성공 여부
    """
    try:
        async with get_async_db_context() as db:
            result = await db.execute(
                delete(EntityTypeMaster).where(EntityTypeMaster.type_key == type_key)
            )
            await db.commit()

            if result.rowcount > 0:
                logger.info(f"✅ 엔티티 타입 삭제 완료: type_key={type_key}")
                return True
            else:
                logger.warning(f"⚠️ 삭제할 엔티티 타입이 없습니다: type_key={type_key}")
                return False

    except SQLAlchemyError as e:
        logger.error(f"❌ 엔티티 타입 삭제 중 오류: {e}")
        return False
