from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID

from authlib.integrations.httpx_client import AsyncOAuth2Client
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.oauth.client import get_oauth_client
from app.core.oauth.config import OAUTH_PROVIDERS
from app.core.oauth.state import generate_oauth_state
from app.core.passcode import (
    delete_passcode,
    delete_passcode_attempts,
    generate_passcode,
    get_passcode,
    get_passcode_attempts,
    increment_passcode_attempts,
    store_passcode,
)
from app.core.security import (
    verify_passcode,
    verify_password,
)
from app.core.settings import settings
from app.exceptions.custom import (
    AppException,
    NotFoundException,
    UnauthorizedException,
)
from app.models.session_model import Session
from app.models.user_identity_model import UserIdentity
from app.models.user_model import User
from app.repositories import (
    OAuthStateRepository,
    SessionRepository,
    UserIdentityRepository,
    UserRepository,
)
from app.schemas.auth_schema import (
    LoginRequest,
    LoginResponse,
)
from app.schemas.response import ApiResponse
from app.schemas.user_schema import UserResponse
from app.services.email_services import send_passcode_email
from app.utils.helpers import utc_now

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)
        self.user_identity_repo = UserIdentityRepository(db)
        self.oauth_state_repo = OAuthStateRepository(redis)

    async def _rollback(self) -> None:
        await self.db.rollback()

    async def login(self, login_data: LoginRequest) -> ApiResponse[LoginResponse]:

        try:
            user = await self.user_repo.get_by_email(login_data.email)
            if user is None:
                logger.warning("Invalid email or password | email=%s", login_data.email)
                raise UnauthorizedException(message="Invalid email or password")

            if user.hashed_password is None:
                logger.warning("Invalid email or password | email=%s", login_data.email)
                raise UnauthorizedException(message="Invalid email or password")

            if not verify_password(login_data.password, user.hashed_password):
                logger.warning("Invalid email or password | email=%s", login_data.email)
                raise UnauthorizedException(message="Invalid email or password")

            if not user.is_active:
                logger.warning("Invalid email or password | email=%s", login_data.email)
                raise UnauthorizedException(message="Invalid email or password")

            session = Session(
                user_id=user.id,
                expires_at=utc_now() + timedelta(days=settings.SESSION_EXPIRE_DAYS),
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
                logger.warning(
                    "Logout requested for non-existent session session_id=%s",
                    session_id,
                )
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
            session = await self.session_repo.get_active_by_id(
                session_id, now=utc_now()
            )

            if session is None:
                logger.warning(
                    "Invalid or expired session | session_id=%s",
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

            # return user

        except Exception:
            # await self._rollback()
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

    async def request_passcode(
        self,
        *,
        email: str,
        redis: Redis,
    ) -> None:

        user = await self.user_repo.get_by_email(email)

        if user is not None and not user.is_active:
            raise UnauthorizedException(
                message="Invalid or expired passcode.",
            )

        await delete_passcode_attempts(
            redis=redis,
            email=email,
        )

        passcode = generate_passcode()

        await store_passcode(
            redis=redis,
            email=email,
            passcode=passcode,
        )

        await send_passcode_email(
            to_email=email,
            first_name=user.first_name if user else "User",
            passcode=passcode,
            expiry_minutes=5,
        )

    async def verify_email_passcode(
        self,
        *,
        email: str,
        passcode: str,
        redis: Redis,
    ) -> ApiResponse[LoginResponse]:

        try:
            user = await self.user_repo.get_by_email(email)

            if user is not None and not user.is_active:
                logger.warning("Invalid email passcode verification attempt")

                raise UnauthorizedException(
                    message="Invalid or expired passcode.",
                )

            attempts = await get_passcode_attempts(
                redis=redis,
                email=email,
            )

            if attempts >= settings.PASSCODE_MAX_ATTEMPTS:
                logger.warning(
                    "Passcode verification attempts exceeded | email=%s",
                    email,
                )

                raise UnauthorizedException(
                    message="Too many attempts. Request a new passcode.",
                )

            stored_hash = await get_passcode(
                redis=redis,
                email=email,
            )

            if stored_hash is None:
                raise UnauthorizedException(
                    message="Invalid or expired passcode.",
                )

            if not verify_passcode(
                passcode,
                stored_hash,
            ):
                await increment_passcode_attempts(
                    redis=redis,
                    email=email,
                )

                raise UnauthorizedException(
                    message="Invalid or expired passcode.",
                )

            await delete_passcode(
                redis=redis,
                email=email,
            )

            await delete_passcode_attempts(
                redis=redis,
                email=email,
            )
            if user is None:
                user = User(
                    email=email,
                    first_name="User",
                    last_name="",
                    is_active=True,
                )
                
                await self.user_repo.create(user)
               

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

            logger.exception("Unexpected error during email passcode verification")

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

    async def start_oauth(self, provider: str) -> str:

        try:
            config = OAUTH_PROVIDERS.get(provider)

            if config is None:
                logger.warning(
                    "Unsupported OAuth provider | provider=%s",
                    provider,
                )
                raise NotFoundException(
                    message="OAuth provider not supported",
                )

            state = generate_oauth_state()

            await self.oauth_state_repo.create(
                state=state,
                provider=provider,
                ttl=settings.OAUTH_STATE_EXPIRE_SECONDS,
            )

            params = {
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(config.scopes),
                "state": state,
            }

            authorization_url = f"{config.authorization_url}?{urlencode(params)}"

            logger.info(
                "OAuth authorization started | provider=%s",
                provider,
            )

            return authorization_url

        except AppException:
            raise

        except Exception:
            logger.exception(
                "Unexpected error while starting OAuth | provider=%s",
                provider,
            )
            raise

    async def validate_oauth_state(
        self,
        provider: str,
        state: str,
    ) -> None:
        stored_provider = await self.oauth_state_repo.consume(state)

        if stored_provider is None:
            logger.warning(
                "Invalid or expired OAuth state | provider=%s",
                provider,
            )
            raise UnauthorizedException(
                message="Invalid or expired OAuth state",
            )

        if stored_provider != provider:
            logger.warning(
                "OAuth provider mismatch | expected=%s actual=%s",
                stored_provider,
                provider,
            )
            raise UnauthorizedException(
                message="Invalid OAuth state",
            )

    async def oauth_callback(
        self,
        provider: str,
        code: str,
        state: str,
    ):
        try:
            await self.validate_oauth_state(
                provider=provider,
                state=state,
            )

            config = OAUTH_PROVIDERS.get(provider)

            if config is None:
                raise NotFoundException(
                    message="OAuth provider not supported",
                )

            client = get_oauth_client(provider)
            logger.info(
                "Exchanging OAuth code for token | provider=%s",
                provider,
            )

            await client.fetch_token(
                url=config.token_url,
                code=code,
                redirect_uri=config.redirect_uri,
            )

            logger.info(
                "OAuth token exchange successful | provider=%s",
                provider,
            )

            userinfo_response = await client.get(config.userinfo_url)

            logger.info(
                "OAuth userinfo response | provider=%s status=%s",
                provider,
                userinfo_response.status_code,
            )

            userinfo_response.raise_for_status()

            userinfo = userinfo_response.json()

            userinfo_response.raise_for_status()

            if provider == "github":
                provider_user_id = str(userinfo["id"])

                email = await self.get_github_email(client)

                full_name = userinfo.get("name") or userinfo.get("login", "")
                name_parts = full_name.split(maxsplit=1)

                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""

            elif provider == "google":
                provider_user_id = userinfo["sub"]

                email = userinfo.get("email")

                if not email:
                    raise UnauthorizedException(
                        message="Google account does not provide an email",
                    )

                if userinfo.get("email_verified") is not True:
                    raise UnauthorizedException(
                        message="Google email is not verified",
                    )

                first_name = userinfo.get("given_name", "")
                last_name = userinfo.get("family_name", "")

            elif provider == "microsoft":
                provider_user_id = userinfo["sub"]

                email = userinfo.get("email") or userinfo.get("preferred_username")

                if not email:
                    raise UnauthorizedException(
                        message="Microsoft account does not provide an email",
                    )

                full_name = userinfo.get("name", "")
                name_parts = full_name.split(maxsplit=1)

                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""

            else:
                raise NotFoundException(
                    message="OAuth provider not supported",
                )

            identity = await self.user_identity_repo.get_by_provider_identity(
                provider=provider,
                provider_user_id=provider_user_id,
            )

            if identity is not None:
                user = await self.user_repo.get_by_id(identity.user_id)

                if user is None:
                    raise NotFoundException(
                        message="User associated with OAuth identity not found",
                    )

            else:
                user = await self.user_repo.get_by_email(email)

                if user is None:
                    user = User(
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                    )

                    user = await self.user_repo.create(user)

                identity = UserIdentity(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    email=email,
                )

                await self.user_identity_repo.create(identity)

            logger.info(
                "OAuth user info | provider=%s provider_user_id=%s email=%s",
                provider,
                provider_user_id,
                email,
            )

            session = Session(
                user_id=user.id,
                expires_at=utc_now() + timedelta(days=settings.SESSION_EXPIRE_DAYS),
            )

            await self.session_repo.create(session)

            await self.db.commit()

            return ApiResponse(
                message=f"{provider.capitalize()} authentication successful",
                data={
                    "session_id": str(session.id),
                },
            )

        except AppException:
            await self._rollback()
            raise

        except Exception:
            await self._rollback()

            logger.exception(
                "Unexpected OAuth callback error | provider=%s",
                provider,
            )

            raise

    # async def get_google_user_info(
    #     self,
    #     access_token: str,
    # ) -> dict[str, Any]:

    #     try:
    #         client = get_oauth_client()

    #         response = await client.get(
    #             "https://openidconnect.googleapis.com/v1/userinfo",
    #             token={
    #                 "access_token": access_token,
    #                 "token_type": "Bearer",
    #             },
    #         )

    #         response.raise_for_status()

    #         user_info = response.json()

    #         logger.info(
    #             "Google user information retrieved successfully",
    #         )

    #         return user_info

    #     except Exception:
    #         logger.exception(
    #             "Failed to retrieve Google user information",
    #         )
    #         raise

    async def get_github_email(self, client: AsyncOAuth2Client) -> str:
        response = await client.get(
            "https://api.github.com/user/emails",
            headers={
                "Accept": "application/vnd.github+json",
            },
        )

        response.raise_for_status()

        emails = response.json()

        for email_data in emails:
            if email_data.get("primary") and email_data.get("verified"):
                return email_data["email"]

        for email_data in emails:
            if email_data.get("verified"):
                return email_data["email"]

        raise UnauthorizedException(
            message="No verified email found for GitHub account",
        )
