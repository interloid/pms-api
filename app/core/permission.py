from app.core.constants import ROLE_PERMISSIONS, PermissionEnum, RoleEnum


def has_permission(role: RoleEnum, permission: PermissionEnum) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, frozenset())
    return permission in permissions
