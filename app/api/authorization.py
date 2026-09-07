from collections.abc import Awaitable, Callable

from fastapi import Depends

from app.api.dependencies import get_current_user
from app.core.constants import PermissionEnum
from app.core.logging import get_logger
from app.core.permission import has_permission
from app.exceptions.custom import ForbiddenException
from app.models.user_model import User

logger = get_logger(__name__)


def require_permission(
    required_permission: PermissionEnum,
) -> Callable[..., Awaitable[User]]:

    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not has_permission(current_user.role, required_permission):
            logger.warning(
                "Permission denied for user | user_id=%s |role=%s | permission=%s",
                current_user.id,
                current_user.role,
                required_permission.value,
            )
            raise ForbiddenException(message="permission denied")

        return current_user

    return permission_checker
