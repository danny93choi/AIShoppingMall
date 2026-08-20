from enum import StrEnum

from commerce_agent.application.tenant_context import TenantContext


class Permission(StrEnum):
    VIEW = "view"
    RUN_DISCOVERY = "run_discovery"
    DECIDE_RECOMMENDATION = "decide_recommendation"
    MANAGE_INTEGRATIONS = "manage_integrations"
    MANAGE_SECURITY = "manage_security"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "viewer": frozenset({Permission.VIEW}),
    "analyst": frozenset({Permission.VIEW, Permission.RUN_DISCOVERY}),
    "operator": frozenset(
        {Permission.VIEW, Permission.RUN_DISCOVERY, Permission.DECIDE_RECOMMENDATION}
    ),
    "admin": frozenset(
        {
            Permission.VIEW,
            Permission.RUN_DISCOVERY,
            Permission.DECIDE_RECOMMENDATION,
            Permission.MANAGE_INTEGRATIONS,
        }
    ),
    "owner": frozenset(Permission),
}


def require_permission(context: TenantContext, permission: Permission) -> None:
    allowed = {value for role in context.roles for value in ROLE_PERMISSIONS.get(role, ())}
    if permission not in allowed:
        raise PermissionError(f"permission required: {permission}")
