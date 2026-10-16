"""Explicit outbound target admission; redirects require a new admission decision."""

import ipaddress
from urllib.parse import urlsplit

from .errors import ResearchError


def validate_target(url, *, allowed_hosts, resolved_addresses, redirected=False):
    try:
        target = urlsplit(url)
        valid_port = target.port in (None, 443)
    except (TypeError, ValueError):
        raise ResearchError("SOURCE_INELIGIBLE") from None
    if (
        redirected
        or target.scheme != "https"
        or not valid_port
        or target.username
        or target.password
        or not target.hostname
        or target.hostname not in allowed_hosts
        or target.fragment
    ):
        raise ResearchError("SOURCE_INELIGIBLE")
    if not resolved_addresses:
        raise ResearchError("DEPENDENCY_UNAVAILABLE")
    try:
        if any(not ipaddress.ip_address(address).is_global for address in resolved_addresses):
            raise ResearchError("SOURCE_INELIGIBLE")
    except ValueError:
        raise ResearchError("SOURCE_INELIGIBLE") from None
    # The network adapter must pin this admitted address set and disable redirects.
    return {"host": target.hostname, "addresses": tuple(resolved_addresses), "url": url}


def extract(content, media_type, *, limit=32768):
    if media_type == "application/pdf":
        return {
            "disposition": "unsupported",
            "text": None,
            "reason": "No approved bounded PDF extraction adapter in this synthetic profile.",
        }
    if media_type != "text/plain":
        return {"disposition": "unsupported", "text": None}
    try:
        text = content.decode("utf-8", errors="strict")
    except (UnicodeError, AttributeError):
        return {"disposition": "malformed", "text": None}
    if "\x00" in text or not text.strip():
        return {"disposition": "malformed", "text": None}
    truncated = len(content) > limit
    if truncated:
        text = content[:limit].decode("utf-8", errors="ignore")
    return {"disposition": "truncated" if truncated else "extracted", "text": text}
