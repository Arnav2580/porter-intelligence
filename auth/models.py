"""User roles and permissions."""

from enum import Enum
from typing import Dict, List


class UserRole(str, Enum):
    ADMIN = "admin"
    OPS_MANAGER = "ops_manager"
    OPS_ANALYST = "ops_analyst"
    READ_ONLY = "read_only"


ROLE_PERMISSIONS: Dict[UserRole, List[str]] = {
    UserRole.ADMIN: [
        "read:all",
        "write:all",
        "delete:all",
        "manage:users",
    ],
    UserRole.OPS_MANAGER: [
        "read:all",
        "write:cases",
        "write:driver_actions",
        "read:reports",
    ],
    UserRole.OPS_ANALYST: [
        "read:cases",
        "read:kpi",
        "read:drivers",
        "write:case_status",
        "write:case_notes",
        "write:driver_actions",
    ],
    UserRole.READ_ONLY: [
        "read:dashboard",
        "read:kpi",
    ],
}
