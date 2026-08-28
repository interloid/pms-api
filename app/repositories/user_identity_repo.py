from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_identity_model import UserIdentity


class UserIdentityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, identity: UserIdentity) -> UserIdentity:
        self.db.add(identity)
        await self.db.flush()
        await self.db.refresh(identity)
        return identity

    async def get_by_provider_identity(
        self, provider: str, provider_user_id: str
    ) -> UserIdentity | None:

        stmt = select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_user_id == provider_user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: UUID) -> list[UserIdentity]:
        stmt = select(UserIdentity).where(
            UserIdentity.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, identity: UserIdentity) -> None:
        await self.db.delete(identity)
        await self.db.flush()
