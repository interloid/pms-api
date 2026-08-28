from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID,uuid4

from authlib.integrations.httpx_client import AsyncOAuth2Client
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.oauth.client import get_oauth_client
from app.core.oauth.config import OAUTH_PROVIDERS
from app.core.oauth.state import generate_oauth_state
from app.core.passcode import (
    check_passcode_request_limit,
    delete_passcode,
    generate_passcode,
    get_passcode,
    get_passcode_attempt_ttl,
    get_passcode_attempts,
    increment_passcode_attempts,
    reset_passcode_attempts,
    store_passcode,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_passcode,
    verify_password,
    decode_token,
    hash_refresh_token,
    validate_access_token_payload,
)
from app.core.settings import settings
from app.exceptions.custom import (
    AppException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    TooManyRequestsException,
)
from app.models.refresh_token_model import RefreshToken
from app.models.user_identity_model import UserIdentity
from app.models.user_model import User
from app.repositories import (
    OAuthStateRepository,
    RefreshTokenRepository,
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
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.user_repo = UserRepository(db)
        self.refresh_token_repo = RefreshTokenRepository(db)
        self.user_identity_repo = UserIdentityRepository(db)
        self.oauth_state_repo = OAuthStateRepository(redis)

    async def _rollback(self) -> None:
        await self.db.rollback()

    async def login(self, login_data: LoginRequest) -> tuple[ApiResponse[LoginResponse], str, int]:

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

            
            access_token = create_access_token({
                "sub": str(user.id),
            })
            raw_refresh_token = create_refresh_token()
            token_hash = hash_refresh_token(raw_refresh_token)
            
            expire_days = (
                settings.REMEMBER_ME_EXPIRE_DAYS
                if login_data.remember_me
                else settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
            
            refresh_expires_at = (
                utc_now()+timedelta(days=expire_days)
            )
            
            refresh_token = RefreshToken(
                user_id=user.id,
                family_id=uuid4(),
                token_hash=token_hash,
                expires_at=refresh_expires_at,
                is_revoked=False
            )
            
            await self.refresh_token_repo.create(refresh_token)
            
            logger.info("User created Successfully | user_id=%s", user.id)


        except AppException:
            await self._rollback()
            raise

        except Exception:
            await self._rollback()
            logger.exception("Unexpected error")
            raise

        result =  ApiResponse[LoginResponse](
            message="Login successful",
            data=LoginResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=(settings.ACCESS_TOKEN_EXPIRE_MINUTES*60),
                user=UserResponse(
                    id=user.id,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_active=user.is_active,
                ),
            ),
        )
        max_age = expire_days * 24 * 60 * 60
        return result, raw_refresh_token, max_age

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

        now = utc_now()

        session = await self.session_repo.get_active_by_id(
            session_id,
            now=now,
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

        if session.remember_me:
            absolute_expiration = session.created_at + timedelta(
                days=settings.REMEMBER_ME_EXPIRE_DAYS
            )

            renew_threshold = timedelta(days=1)

            if session.expires_at - now <= renew_threshold:
                new_expiration = min(
                    now + timedelta(days=settings.SESSION_EXPIRE_DAYS),
                    absolute_expiration,
                )

                if new_expiration > session.expires_at:
                    session.expires_at = new_expiration
                    await self.db.commit()

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
        client_ip: str,
        redis: Redis,
    ) -> None:

        email = email.strip().lower()

        user = await self.user_repo.get_by_email(email)

        if user is not None and not user.is_active:
            logger.warning("Invalid email passcode verification attempt")
            raise UnauthorizedException(
                message="Invalid email passcode verification attempt.",
            )

        await check_passcode_request_limit(
            redis=redis,
            email=email,
            client_ip=client_ip,
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
            email = email.strip().lower()

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
                retry_after_seconds = await get_passcode_attempt_ttl(
                    redis=redis,
                    email=email,
                )

                logger.warning(
                    "Passcode verification attempts exceeded | email=%s",
                    email,
                )

                raise TooManyRequestsException(
                    message="Too many attempts. Request a new passcode.",
                    details={
                        "attempts_used": attempts,
                        "max_attempts": settings.PASSCODE_MAX_ATTEMPTS,
                        "remaining_attempts": 0,
                        "retry_after_seconds": retry_after_seconds,
                    },
                )

            stored_hash = await get_passcode(
                redis=redis,
                email=email,
            )

            if stored_hash is None:
                logger.warning("Invalid or expired passcode")
                raise UnauthorizedException(
                    message="Invalid or expired passcode.",
                )

            if not verify_passcode(
                passcode,
                stored_hash,
            ):
                attempts = await increment_passcode_attempts(
                    redis=redis,
                    email=email,
                )

                remaining_attempts = max(
                    settings.PASSCODE_MAX_ATTEMPTS - attempts,
                    0,
                )
                retry_after_seconds = await get_passcode_attempt_ttl(
                    redis=redis,
                    email=email,
                )

                details = {
                    "attempts_used": attempts,
                    "max_attempts": settings.PASSCODE_MAX_ATTEMPTS,
                    "remaining_attempts": remaining_attempts,
                    "retry_after_seconds": retry_after_seconds,
                }

                if attempts >= settings.PASSCODE_MAX_ATTEMPTS:
                    logger.warning(
                        "Passcode verification attempts exceeded | email=%s",
                        email,
                    )
                    raise TooManyRequestsException(
                        message="Too many attempts. Request a new passcode.",
                        details=details,
                    )

                logger.warning("Invalid or expired passcode")
                raise UnauthorizedException(
                    message="Invalid or expired passcode.",
                    details=details,
                )

            await delete_passcode(
                redis=redis,
                email=email,
            )

            await reset_passcode_attempts(
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
            logger.info("User created Successfully | email=%s", email)

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
                logger.warning("OAuth provider not supported | provider=%s", provider)
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
                    logger.warning(
                        "Google account does not provide email | email=%s", email
                    )
                    raise UnauthorizedException(
                        message="Google account does not provide an email",
                    )

                if userinfo.get("email_verified") is not True:
                    logger.warning("Google email is not verified | email=%s", email)
                    raise UnauthorizedException(
                        message="Google email is not verified",
                    )

                first_name = userinfo.get("given_name", "")
                last_name = userinfo.get("family_name", "")

            elif provider == "microsoft":
                provider_user_id = userinfo["sub"]

                email = userinfo.get("email")

                if not email:
                    logger.warning(
                        "Microsoft account does not provide an email| email=%s", email
                    )
                    raise UnauthorizedException(
                        message="Microsoft account does not provide an email",
                    )

                full_name = userinfo.get("name", "")
                name_parts = full_name.split(maxsplit=1)

                first_name = name_parts[0] if name_parts else ""
                last_name = name_parts[1] if len(name_parts) > 1 else ""

            else:
                logger.warning("OAuth provider not supported")
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
                    logger.warning(
                        "User associated with OAuth identity not found| user=%s", user
                    )
                    raise NotFoundException(
                        message="User associated with OAuth identity not found",
                    )

            else:
                user = await self.user_repo.get_by_email(email)

                if user is not None:
                    logger.warning(
                        "An account with this email already exists| user=%s", user
                    )
                    raise ConflictException(
                        message=(
                            "An account with this email already exists. "
                            "Kindly sign in with the existing account."
                        ),
                    )

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

            if not user.is_active:
                logger.warning("User account is inactive| user=%s", user)
                raise UnauthorizedException(message="User account is inactive")

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

        logger.warning("No verified email found for GitHub account | emails=%s", emails)

        raise UnauthorizedException(
            message="No verified email found for GitHub account",
        )
