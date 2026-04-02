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
        "write:case_status",
        "read:drivers",
        "write:case_notes",
    ],
    UserRole.READ_ONLY: [
        "read:dashboard",
        "read:kpi",
    ],
}
