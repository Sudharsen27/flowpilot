"""Outbound webhook HTTP with SSRF protection.

Only public HTTPS targets are allowed. The hostname is resolved once, every
resolved address must be globally routable, and the TCP connection is made to
that checked address while TLS still verifies the certificate for the
hostname. This closes the DNS-rebinding gap between "check" and "connect".
Redirects are never followed and response bodies are discarded.
"""

from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

import certifi

CONNECT_TIMEOUT_SECONDS = 5.0
RESPONSE_TIMEOUT_SECONDS = 10.0
MAX_URL_LENGTH = 500
_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet")


class WebhookTargetError(Exception):
    """A safe, user-facing reason a URL cannot be used or reached."""


@dataclass(frozen=True)
class WebhookTarget:
    hostname: str
    port: int
    path: str


@dataclass(frozen=True)
class WebhookResponse:
    status_code: int


WebhookSender = Callable[[str, bytes, Mapping[str, str]], WebhookResponse]
Resolver = Callable[[str, int], list[str]]


def parse_webhook_url(url: str) -> WebhookTarget:
    """Validate the URL shape. Does not touch the network."""
    if len(url) > MAX_URL_LENGTH:
        raise WebhookTargetError("The URL is too long")
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise WebhookTargetError("The URL is not valid") from exc
    if parts.scheme != "https":
        raise WebhookTargetError("The URL must start with https://")
    if parts.username is not None or parts.password is not None:
        raise WebhookTargetError("The URL must not contain a username or password")
    hostname = (parts.hostname or "").rstrip(".").lower()
    if not hostname:
        raise WebhookTargetError("The URL must include a host name")
    if parts.fragment:
        raise WebhookTargetError("The URL must not contain a # fragment")
    if hostname == "localhost" or hostname.endswith(_BLOCKED_SUFFIXES) or "." not in hostname:
        if not _is_ip_literal(hostname):
            raise WebhookTargetError("The URL must point to a public internet address")
    if _is_ip_literal(hostname) and not _is_public(hostname):
        raise WebhookTargetError("The URL must point to a public internet address")
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return WebhookTarget(hostname=hostname, port=port or 443, path=path)


def resolve_public_addresses(hostname: str, port: int) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError) as exc:
        raise WebhookTargetError("The host name could not be found") from exc
    addresses = list(dict.fromkeys(str(info[4][0]) for info in infos))
    if not addresses:
        raise WebhookTargetError("The host name could not be found")
    if not all(_is_public(address) for address in addresses):
        raise WebhookTargetError("The URL resolves to a private or internal network address")
    return addresses


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, address: str, target: WebhookTarget, context: ssl.SSLContext) -> None:
        super().__init__(target.hostname, target.port, timeout=CONNECT_TIMEOUT_SECONDS)
        self._address = address
        self._ssl_context = context

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._address, self.port), timeout=CONNECT_TIMEOUT_SECONDS
        )
        sock.settimeout(RESPONSE_TIMEOUT_SECONDS)
        self.sock = self._ssl_context.wrap_socket(sock, server_hostname=self.host)


def send_webhook(
    url: str,
    body: bytes,
    headers: Mapping[str, str],
    *,
    resolver: Resolver = resolve_public_addresses,
) -> WebhookResponse:
    target = parse_webhook_url(url)
    address = resolver(target.hostname, target.port)[0]
    context = ssl.create_default_context(cafile=certifi.where())
    connection = _PinnedHTTPSConnection(address, target, context)
    try:
        connection.request("POST", target.path, body=body, headers=dict(headers))
        response = connection.getresponse()
        response.read(1024)
        return WebhookResponse(status_code=response.status)
    except ssl.SSLError as exc:
        raise WebhookTargetError("The TLS certificate could not be verified") from exc
    except TimeoutError as exc:
        raise WebhookTargetError("The endpoint did not respond in time") from exc
    except OSError as exc:
        raise WebhookTargetError("Could not connect to the endpoint") from exc
    except http.client.HTTPException as exc:
        raise WebhookTargetError("The endpoint sent an invalid response") from exc
    finally:
        connection.close()


def _is_ip_literal(value: str) -> bool:
    try:
        ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return False
    return True


def _is_public(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0].strip("[]"))
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_global and not address.is_multicast
