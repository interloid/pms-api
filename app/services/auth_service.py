import hmac
from datetime import timedelta
from typing import NoReturn
from uuid import uuid4, UUID

from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from slugify import slugify
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import (
    hash_password,
    hash_passcode,
    verify_password,
)
from app.core.settings import settings
from app.exceptions.custom import (
    AppException,
    ConflictException,
    ForbiddenException,
    InternalServerException,
    UnauthorizedException,
)
from app.models.session_model import Session
from app.models.user_identity_model import UserIdentity
from app.models.user_model import User
from app.repositories import (
   SessionRepository,
   UserIdentityRepository,
   UserRepository,
   ProductRepository,
   ProductImageRepository,
   CategoryRepository
)
from app.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
    PasscodeLoginRequest,
)
from app.schemas.response import ApiResponse
from app.schemas.session_schema import SessionResponse
from app.schemas.user_schema import UserResponse
from app.utils.helpers import utc_now

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)
        self.user_identity_repo = UserIdentityRepository(db)

    async def _rollback(self) -> None:
        await self.db.rollback()


    async def login(self, login_data: LoginRequest) -> ApiResponse[LoginResponse]:

        try:
            
            user = await self.user_repo.get_by_email(login_data.email)
            if user is None:
                logger.warning("Invalid email or password | email=%s",login_data.email)
                raise UnauthorizedException(message="Invalid email or password")
            
            if user.hashed_password is None:
                logger.warning("Invalid email or password | email=%s",login_data.email)
                raise UnauthorizedException(message="Invalid email or password")
            
            if not verify_password(login_data.password,user.hashed_password):
                logger.warning("Invalid email or password | email=%s",login_data.email)
                raise UnauthorizedException(message="Invalid email or password")
            
            if not user.is_active:
                logger.warning("Invalid email or password | email=%s",login_data.email)
                raise UnauthorizedException(message="Invalid email or password")
            
            session = Session(
                user_id = user.id,
                expires_at = utc_now() + timedelta(days=settings.SESSION_EXPIRE_DAYS)
            )
            
            await self.session_repo.create(session)

            await self.db.commit()

        except AppException:
            await self._rollback()
            raise

        except Exception:
            await self._rollback()
            logger.exception("Unexpected error")
            raise

        return ApiResponse[LoginResponse](
            message="Login successful",
            data=LoginResponse(
                session_id=session.id,
                user=UserResponse(
                    id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_active=user.is_active,
                ),
            ),
        )

    

    async def logout(self, session_id: UUID):

        try:
            
            session = await self.session_repo.get_by_id(session_id)
            if session is None:
                logger.warning("Logout requested for non-existent session session_id=%s",session_id)
                return ApiResponse[None](
                    message="Logged out successfully",
                )
            
            await self.session_repo.delete(session)      
            await self.db.commit()
            
            logger.info(
                "User logged out successfully | session_id=%s",
                session_id,
            )

        except AppException:
            await self._rollback()
            raise

        except Exception:
            await self._rollback()
            logger.exception("Unexpected error while refreshing token")
            raise

        return ApiResponse[None](
            message="Logged out successfully",
        )


    async def get_current_session(self, session_id: UUID):
        
        try:
            session = await self.session_repo.get_active_by_id(session_id,now=utc_now())
            
            if session is None:
                logger.warning("Invalid or expired session | session_id=%s",
                session_id,
            )
                raise UnauthorizedException(message="Invalid or expired session")
            
            user = await self.user_repo.get_by_id(session.user_id)
            
            if user is None:
                logger.warning(
                    "User not found for session | session_id=%s",
                    session_id,
                )
                raise UnauthorizedException(message="Invalid session")
            
            if not user.is_active:
                logger.warning(
                    "Inactive user | user_id=%s",
                    user.id,
                )
                raise UnauthorizedException(message="Invalid session")

        except AppException:
            await self._rollback()
            raise

        except Exception:
            await self._rollback()
            logger.exception("Unexpected error")
            raise

        return ApiResponse[LoginResponse](
            message="Session retrieved successfully",
            data=LoginResponse(
                session_id=session.id,
                user=UserResponse(
                    id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_active=user.is_active,
                ),
            ),
        )
        


    async def login_passcode(self, login_data: PasscodeLoginRequest):

        try:
            passcode_hash = hash_passcode(login_data.passcode)

            user = await self.user_repo.get_by_passcode_hash(passcode_hash)

            if user is None:
                logger.warning("Invalid passcode login attempt")
                raise UnauthorizedException(message="Invalid passcode. Try again.")

            if not user.is_active:
                logger.warning(
                    "Passcode login failed: inactive user | user_id=%s",
                    user.id,
                )
                raise UnauthorizedException(message="Invalid passcode. Try again.")

            session = Session(
                user_id=user.id,
                expires_at=utc_now()
                + timedelta(
                    days=settings.SESSION_EXPIRE_DAYS,
                ),
            )

            await self.session_repo.create(session)

            await self.db.commit()
            

        except AppException:
            await self._rollback()
            raise

        except Exception:
            await self._rollback()
            logger.exception("Unexpected error")
            raise

        return ApiResponse[LoginResponse](
            message="Login successful",
            data=LoginResponse(
                session_id=session.id,
                user=UserResponse(
                    id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_active=user.is_active,
                ),
            ),
        )