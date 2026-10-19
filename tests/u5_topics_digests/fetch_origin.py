"""The `Origin` a browser sends on a page's own form POST, per the Fetch standard.

Fetch, "append a request `Origin` header", for a request whose response
tainting is not "cors" and whose mode is not "websocket" (an HTML form
submission is a "navigate" request), with a method other than GET or HEAD:
the serialized origin is the request's origin, except that the document's
referrer policy turns it into `null`:

- `no-referrer`: always `null`;
- `no-referrer-when-downgrade`, `strict-origin`, `strict-origin-when-cross-origin`:
  `null` when the origin is HTTPS and the target is not potentially trustworthy;
- `same-origin`: `null` when the target is cross-origin;
- any other policy: the origin.

Used so tests derive the browser's header from the `Referrer-Policy` a page was
actually served with, instead of asserting a hard-coded `Origin` value.
"""

from urllib.parse import urlsplit

NULL_ORIGIN = "null"
_DEFAULT_PORTS = {"https": 443, "http": 80}
_DOWNGRADE_POLICIES = frozenset(
    {"no-referrer-when-downgrade", "strict-origin", "strict-origin-when-cross-origin"}
)


def _origin_of(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    return parts.scheme, parts.hostname or "", parts.port or _DEFAULT_PORTS[parts.scheme]


def _serialize(url: str) -> str:
    scheme, host, port = _origin_of(url)
    return f"{scheme}://{host}" + ("" if port == _DEFAULT_PORTS[scheme] else f":{port}")


def _potentially_trustworthy(url: str) -> bool:
    scheme, host, _ = _origin_of(url)
    return scheme == "https" or host in ("localhost", "127.0.0.1")


def form_post_origin(referrer_policy: str, document_url: str, target_url: str) -> str:
    """The `Origin` header value for a form POST from `document_url` to `target_url`."""
    policy = referrer_policy.strip().lower()
    serialized = _serialize(document_url)
    if policy == "no-referrer":
        return NULL_ORIGIN
    if policy in _DOWNGRADE_POLICIES:
        if serialized.startswith("https:") and not _potentially_trustworthy(target_url):
            return NULL_ORIGIN
        return serialized
    if policy == "same-origin":
        return serialized if _origin_of(document_url) == _origin_of(target_url) else NULL_ORIGIN
    return serialized
