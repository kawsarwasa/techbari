import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError


class UnsafeOutboundURL(ValidationError):
    pass


def _public_ip(value):
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


def validate_outbound_url(value, *, resolve=False):
    url = str(value or "").strip()
    if not url:
        raise UnsafeOutboundURL("Outbound URL is missing.")
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise UnsafeOutboundURL("Outbound URL is invalid.") from exc

    allowed_schemes = {"https"} if getattr(settings, "INTEGRATION_REQUIRE_HTTPS", not settings.DEBUG) else {"http", "https"}
    if parsed.scheme.lower() not in allowed_schemes:
        raise UnsafeOutboundURL("Outbound integrations require HTTPS in production.")
    if parsed.username or parsed.password:
        raise UnsafeOutboundURL("Credentials must not be embedded in outbound URLs.")
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if not hostname:
        raise UnsafeOutboundURL("Outbound URL hostname is missing.")

    blocked_names = {"localhost", "localhost.localdomain"}
    if not settings.DEBUG and (hostname in blocked_names or hostname.endswith(".localhost")):
        raise UnsafeOutboundURL("Private/loopback integration destinations are not allowed.")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None and not settings.DEBUG and not literal.is_global:
        raise UnsafeOutboundURL("Private/loopback integration destinations are not allowed.")

    if resolve and not settings.DEBUG and literal is None:
        try:
            addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeOutboundURL("Outbound integration hostname could not be resolved.") from exc
        resolved = {entry[4][0].split("%", 1)[0] for entry in addresses if entry[4]}
        if not resolved or any(not _public_ip(address) for address in resolved):
            raise UnsafeOutboundURL("Outbound integration hostname resolves to a non-public address.")
    return url
