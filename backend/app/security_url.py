from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeUrlError(ValueError):
    """Raised when a user-provided URL is not safe to fetch server-side."""


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _normalize_host(hostname: str | None) -> str:
    if not hostname:
        raise UnsafeUrlError("URL host is required.")
    host = hostname.rstrip(".").lower()
    if not host:
        raise UnsafeUrlError("URL host is required.")
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeUrlError("Local hosts are not allowed.")
    try:
        # Validate/normalize IDNs without changing the URL used by httpx.
        host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UnsafeUrlError("URL host is invalid.") from exc
    return host


async def _resolve_host(host: str, port: int | None) -> list[str]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        return [str(literal)]

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(
                host,
                port,
                type=socket.SOCK_STREAM,
            ),
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError("URL host could not be resolved.") from exc

    addresses = sorted({item[4][0] for item in infos})
    if not addresses:
        raise UnsafeUrlError("URL host could not be resolved.")
    return addresses


async def validate_public_http_url(url: str) -> str:
    """Validate that *url* is safe for server-side fetching.

    Only public HTTP(S) URLs are accepted. Private, local, reserved, multicast,
    link-local, and unspecified addresses are rejected after DNS resolution.
    """
    stripped = (url or "").strip()
    if not stripped:
        raise UnsafeUrlError("URL is required.")

    parts = urlsplit(stripped)
    if parts.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only http and https URLs are allowed.")
    if parts.username or parts.password:
        raise UnsafeUrlError("URL credentials are not allowed.")
    if not parts.netloc:
        raise UnsafeUrlError("URL host is required.")

    host = _normalize_host(parts.hostname)
    port = parts.port
    for address in await _resolve_host(host, port):
        if _is_blocked_ip(address):
            raise UnsafeUrlError("URL host resolves to a non-public address.")

    return stripped
