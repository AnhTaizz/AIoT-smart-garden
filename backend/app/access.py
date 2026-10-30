"""Keep pump control local until the API has real access control (BC-02).

CORS only tells a browser which pages may read a response; any other HTTP
client ignores it. The API has no authentication yet, so a request that
arrived through a public tunnel or reverse proxy (Cloudflare, ngrok, ...) may
read telemetry and state but must not publish device commands. Requests from
the laptop itself, the Docker network or the trusted LAN keep working.

This is a guard rail, not authentication: it relies on proxies identifying
themselves, which Cloudflare always does and other common tunnels do through
X-Forwarded-For. Headers only ever make a request *more* restricted, so
spoofing them cannot unlock control.
"""

import ipaddress
from collections.abc import Mapping
from typing import Literal

from fastapi import Request
from pydantic import BaseModel

REMOTE_CONTROL_DISABLED = "remote_control_disabled"

# Cloudflare sets these on every proxied request; a client cannot remove them.
CLOUDFLARE_HEADERS = ("cf-connecting-ip", "cf-ray")


class ControlAccess(BaseModel):
    commands_allowed: bool
    reason: Literal["remote_control_disabled"] | None = None


def _is_local_address(value: str) -> bool | None:
    """True for loopback/private/link-local, False for public, None if unparsable."""
    text = value.strip().strip('"')
    if text.startswith("["):  # [IPv6] or [IPv6]:port
        text = text[1:].split("]", 1)[0]
    elif text.count(":") == 1:  # IPv4:port
        text = text.split(":", 1)[0]
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return not address.is_global


def _forwarded_for(value: str) -> list[str]:
    """Extract `for=` nodes from an RFC 7239 Forwarded header."""
    nodes = []
    for element in value.split(","):
        for pair in element.split(";"):
            key, _, node = pair.partition("=")
            if key.strip().lower() == "for":
                nodes.append(node)
    return nodes


def is_remote(headers: Mapping[str, str], client_host: str | None) -> bool:
    """Decide whether a request came from outside the laptop/LAN.

    Fails closed: a forwarding header that cannot be parsed counts as remote.
    """
    if any(name in headers for name in CLOUDFLARE_HEADERS):
        return True
    if "cloudflare" in headers.get("cdn-loop", "").lower():
        return True
    hops = [hop for hop in headers.get("x-forwarded-for", "").split(",") if hop.strip()]
    hops += _forwarded_for(headers.get("forwarded", ""))
    if headers.get("x-real-ip", "").strip():
        hops.append(headers["x-real-ip"])
    if any(_is_local_address(hop) is not True for hop in hops):
        return True
    # A real socket peer is always an IP; test transports may use a name.
    return client_host is not None and _is_local_address(client_host) is False


def control_access(request: Request) -> ControlAccess:
    client_host = request.client.host if request.client else None
    if is_remote(request.headers, client_host):
        return ControlAccess(commands_allowed=False, reason=REMOTE_CONTROL_DISABLED)
    return ControlAccess(commands_allowed=True)
