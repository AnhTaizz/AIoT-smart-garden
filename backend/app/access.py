"""Who may send pump commands (BC-02).

Control is decided only by the authenticated session: an `operator` session may
send commands from anywhere, including through an HTTPS tunnel; a `viewer`
session may read but gets 403. Client IP addresses, Cloudflare/forwarding
headers and CORS are not evidence of identity and are not consulted.

The BC-01 rule that refused every tunnelled command is gone: it was a stopgap
until real authentication existed.
"""

from typing import Literal

from pydantic import BaseModel

from .auth import Session


class ControlAccess(BaseModel):
    commands_allowed: bool
    reason: Literal["forbidden"] | None = None
    role: Literal["operator", "viewer"]


def control_access(session: Session) -> ControlAccess:
    if session.role == "operator":
        return ControlAccess(commands_allowed=True, role=session.role)
    return ControlAccess(commands_allowed=False, reason="forbidden", role=session.role)
