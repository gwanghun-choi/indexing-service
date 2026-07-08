"""
사용자 정의 카테고리 CRUD

사용자별 카테고리의 생성, 조회, 수정, 삭제 작업을 담당합니다.
"""

import logging
from typing import Dict, List, Optional, Any

from sqlalchemy import select, func, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.config.database.session import get_async_db_context
from app.entity.postgres.user_category_entity import UserCategory

logger = logging.getLogger(__name__)


class UserCategoryCRUD:
    """
    사용자 정의 카테고리 CRUD 클래스

    사용자별 카테고리의 생성, 조회, 수정, 삭제 작업을 담당합니다.
    """

    async def create_category(
        self,
        user_id: int,
        group_id: int,
        name: str,
        description: Optional[str] = None,
        default_retention_period: int = 3,
        parent_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        새 카테고리를 생성합니다.

        Args:
            user_id: 소유자 사용자 ID
            group_id: 소속 그룹 ID
            name: 카테고리 이름
            description: 카테고리 설명
            default_retention_period: 만료기간 추천값 (년)
            parent_id: 부모 카테고리 ID (NULL이면 루트)

        Returns:
            Dict[str, Any]: 생성된 카테고리 정보

        Raises:
            ValueError: 부모 카테고리가 본인 소유가 아닌 경우
            IntegrityError: 중복된 카테고리 이름인 경우
        """
        try:
            async with get_async_db_context() as db:
                # 동일 이름 중복 체크 (PostgreSQL의 NULL 값 unique 제약조건 문제 대응)
                existing_query = select(UserCategory).where(
                    and_(
                        UserCategory.user_id == user_id,
                        UserCategory.name == name,
                        UserCategory.parent_id == parent_id
                        if parent_id is not None
                        else UserCategory.parent_id.is_(None),
                    )
                )
                existing_result = await db.execute(existing_query)
                existing = existing_result.scalar_one_or_none()

                if existing:
                    raise ValueError(
                        f"같은 부모 아래에 동일한 이름의 카테고리가 이미 존재합니다: {name}"
                    )

                # 부모 카테고리 검증 (있는 경우)
                parent_depth = 0
                parent_path = ""

                if parent_id is not None:
                    parent_query = select(UserCategory).where(
                        and_(
                            UserCategory.id == parent_id,
                            UserCategory.user_id == user_id,
                        )
                    )
                    parent_result = await db.execute(parent_query)
                    parent = parent_result.scalar_one_or_none()

                    if not parent:
                        raise ValueError(
                            f"부모 카테고리를 찾을 수 없거나 권한이 없습니다: parent_id={parent_id}"
                        )

                    parent_depth = parent.depth
                    parent_path = parent.path or str(parent.id)

                # 카테고리 생성
                depth = parent_depth + 1
                category = UserCategory(
                    user_id=user_id,
                    group_id=group_id,
                    name=name,
                    description=description,
                    default_retention_period=default_retention_period,
                    parent_id=parent_id,
                    depth=depth,
                    path="",  # 임시 값, ID 생성 후 업데이트
                )

                db.add(category)
                await db.flush()  # ID 생성을 위해 flush

                # path 업데이트
                if parent_path:
                    category.path = f"{parent_path}/{category.id}"
                else:
                    category.path = str(category.id)

                await db.commit()
                await db.refresh(category)

                logger.info(
                    f"카테고리 생성 완료: id={category.id}, user_id={user_id}, name={name}"
                )

                return category.to_dict()

        except IntegrityError as e:
            logger.error(f"카테고리 생성 실패 (중복): {e}")
            raise ValueError(
                f"같은 부모 아래에 동일한 이름의 카테고리가 이미 존재합니다: {name}"
            )
        except SQLAlchemyError as e:
            logger.error(f"카테고리 생성 실패: {e}")
            raise

    async def select_categories_by_user(
        self,
        user_id: int,
        parent_id: Optional[int] = None,
        include_all: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        사용자의 카테고리 목록을 조회합니다.

        Args:
            user_id: 사용자 ID
            parent_id: 부모 카테고리 ID 필터 (None이면 전체)
            include_all: True면 전체, False면 특정 parent_id만

        Returns:
            List[Dict[str, Any]]: 카테고리 목록
        """
        try:
            async with get_async_db_context() as db:
                query = select(UserCategory).where(UserCategory.user_id == user_id)

                if not include_all:
                    if parent_id is None:
                        query = query.where(UserCategory.parent_id.is_(None))
                    else:
                        query = query.where(UserCategory.parent_id == parent_id)

                query = query.order_by(UserCategory.depth, UserCategory.name)

                result = await db.execute(query)
                categories = result.scalars().all()

                return [cat.to_dict() for cat in categories]

        except SQLAlchemyError as e:
            logger.error(f"카테고리 목록 조회 실패: {e}")
            raise

    async def select_category_by_id(
        self,
        category_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        ID로 카테고리를 조회합니다.

        Args:
            category_id: 카테고리 ID
            user_id: 사용자 ID (지정 시 본인 소유 카테고리만 조회)

        Returns:
            Optional[Dict[str, Any]]: 카테고리 정보 (없으면 None)
        """
        try:
            async with get_async_db_context() as db:
                query = select(UserCategory).where(UserCategory.id == category_id)

                if user_id is not None:
                    query = query.where(UserCategory.user_id == user_id)

                result = await db.execute(query)
                category = result.scalar_one_or_none()

                if not category:
                    return None

                return category.to_dict()

        except SQLAlchemyError as e:
            logger.error(f"카테고리 조회 실패 (id={category_id}): {e}")
            raise

    async def update_category(
        self,
        category_id: int,
        user_id: int,
        update_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        카테고리를 수정합니다.

        Args:
            category_id: 카테고리 ID
            user_id: 사용자 ID (본인 소유 확인용)
            update_data: 수정할 데이터

        Returns:
            Optional[Dict[str, Any]]: 수정된 카테고리 정보 (없으면 None)

        Raises:
            ValueError: 중복된 이름으로 수정 시도
        """
        try:
            async with get_async_db_context() as db:
                query = select(UserCategory).where(
                    and_(
                        UserCategory.id == category_id,
                        UserCategory.user_id == user_id,
                    )
                )
                result = await db.execute(query)
                category = result.scalar_one_or_none()

                if not category:
                    return None

                # 수정 가능한 필드만 업데이트
                allowed_fields = {"name", "description", "default_retention_period"}

                for key, value in update_data.items():
                    if key in allowed_fields and value is not None:
                        setattr(category, key, value)

                await db.commit()
                await db.refresh(category)

                logger.info(f"카테고리 수정 완료: id={category_id}")

                return category.to_dict()

        except IntegrityError as e:
            logger.error(f"카테고리 수정 실패 (중복): {e}")
            raise ValueError(
                "같은 부모 아래에 동일한 이름의 카테고리가 이미 존재합니다."
            )
        except SQLAlchemyError as e:
            logger.error(f"카테고리 수정 실패: {e}")
            raise

    async def delete_category(
        self,
        category_id: int,
        user_id: int,
    ) -> bool:
        """
        카테고리를 삭제합니다.

        Args:
            category_id: 카테고리 ID
            user_id: 사용자 ID (본인 소유 확인용)

        Returns:
            bool: 삭제 성공 여부

        Raises:
            ValueError: 하위 카테고리가 존재하는 경우
        """
        try:
            async with get_async_db_context() as db:
                # 카테고리 조회
                query = select(UserCategory).where(
                    and_(
                        UserCategory.id == category_id,
                        UserCategory.user_id == user_id,
                    )
                )
                result = await db.execute(query)
                category = result.scalar_one_or_none()

                if not category:
                    return False

                # 하위 카테고리 존재 확인
                children_query = select(func.count()).where(
                    UserCategory.parent_id == category_id
                )
                children_result = await db.execute(children_query)
                children_count = children_result.scalar()

                if children_count > 0:
                    raise ValueError(
                        f"하위 카테고리가 {children_count}개 존재합니다. 먼저 삭제해주세요."
                    )

                # 삭제 실행
                await db.delete(category)
                await db.commit()

                logger.info(f"카테고리 삭제 완료: id={category_id}")

                return True

        except SQLAlchemyError as e:
            logger.error(f"카테고리 삭제 실패: {e}")
            raise

    async def select_category_tree(
        self,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """
        사용자의 카테고리를 트리 구조로 조회합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            List[Dict[str, Any]]: 루트 카테고리 목록 (하위 카테고리 포함)
        """
        try:
            async with get_async_db_context() as db:
                # 전체 카테고리 조회
                query = (
                    select(UserCategory)
                    .where(UserCategory.user_id == user_id)
                    .order_by(UserCategory.depth, UserCategory.name)
                )
                result = await db.execute(query)
                categories = result.scalars().all()

                # 트리 구조로 변환
                tree = self._build_tree(categories)

                return tree

        except SQLAlchemyError as e:
            logger.error(f"카테고리 트리 조회 실패: {e}")
            raise

    def _build_tree(
        self, categories: List[UserCategory]
    ) -> List[Dict[str, Any]]:
        """
        카테고리 목록을 트리 구조로 변환합니다.

        Args:
            categories: 카테고리 엔티티 목록

        Returns:
            List[Dict[str, Any]]: 트리 구조의 카테고리 목록
        """
        # ID별 카테고리 딕셔너리 생성
        category_map = {}
        for cat in categories:
            category_map[cat.id] = {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "depth": cat.depth,
                "default_retention_period": cat.default_retention_period,
                "document_count": 0,  # 추후 계산
                "children": [],
            }

        # 부모-자식 관계 연결
        root_categories = []
        for cat in categories:
            node = category_map[cat.id]
            if cat.parent_id is None:
                root_categories.append(node)
            elif cat.parent_id in category_map:
                category_map[cat.parent_id]["children"].append(node)

        return root_categories

    async def check_category_has_documents(
        self,
        user_id: int,
        group_id: int,
    ) -> int:
        """
        카테고리에 문서가 있는지 확인합니다.

        Note:
            이 메서드는 Milvus 조회가 필요하므로 Service 레이어에서 구현됩니다.
            여기서는 인터페이스만 정의합니다.

        Args:
            user_id: 사용자 ID
            group_id: 그룹 ID

        Returns:
            int: 문서 수
        """
        # Milvus 조회가 필요하므로 Service 레이어에서 구현
        return 0

    async def select_categories_by_names(
        self,
        user_id: int,
        names: List[str],
    ) -> List[Dict[str, Any]]:
        """
        이름 목록으로 카테고리를 조회합니다.

        Args:
            user_id: 사용자 ID
            names: 카테고리 이름 목록

        Returns:
            List[Dict[str, Any]]: 카테고리 목록
        """
        try:
            async with get_async_db_context() as db:
                query = select(UserCategory).where(
                    and_(
                        UserCategory.user_id == user_id,
                        UserCategory.name.in_(names),
                    )
                )
                result = await db.execute(query)
                categories = result.scalars().all()

                return [cat.to_dict() for cat in categories]

        except SQLAlchemyError as e:
            logger.error(f"카테고리 이름으로 조회 실패: {e}")
            raise


# 싱글톤 인스턴스
user_category_crud = UserCategoryCRUD()
