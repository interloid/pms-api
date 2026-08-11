from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session_model import Session


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session: Session) -> Session:
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session


    async def get_by_id(self, session_id: UUID) -> Session | None:
        stmt = select(Session).where(Session.id == session_id,)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


    async def get_active_by_id(self,session_id: UUID,now: datetime) -> Session | None:
        stmt = select(Session).where(
            Session.id == session_id,
            Session.expires_at > now,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
        
        
    async def delete(self, session: Session) -> None:
        await self.db.delete(session)
        await self.db.flush()


    async def delete_expired(self, now: datetime) -> None:
        stmt = delete(Session).where(Session.expires_at < now)
        await self.db.execute(stmt)

