"""Typed, non-revealing refusals at the export boundary.

Neither type ever carries a token, a sealed envelope, key material or provider text:
`ExportError` holds a frozen code plus bounded structured facts, and
`ProtectionUnavailable` holds only a fixed category token.
"""

import re

_CATEGORY = re.compile(r"[a-z][a-z0-9-]{0,63}")


class ExportError(RuntimeError):
    """A domain refusal; the code is one of the operation's frozen error codes.

    `retry_after` is the whole number of seconds until exporting is possible again.
    Only the 20-per-hour bind refusal sets it; the boundary writes it as the body field
    `retryAfterSeconds`, never as a `Retry-After` header.
    """

    def __init__(
        self,
        code: str,
        *,
        current: dict | None = None,
        retry_after: int | None = None,
    ):
        if retry_after is not None and (type(retry_after) is not int or retry_after <= 0):
            raise ValueError("retry_after must be a whole positive number of seconds")
        super().__init__(code)
        self.code = code
        self.current = current
        self.retry_after = retry_after


class ProtectionUnavailable(RuntimeError):
    """Every token-custody fault: key folder, key file, envelope or key count.

    The message is a fixed category token, so no secret, path content or exception text
    can travel with it.
    """

    def __init__(self, category: str = "protection-unavailable"):
        if not isinstance(category, str) or _CATEGORY.fullmatch(category) is None:
            category = "protection-unavailable"
        super().__init__(category)
        self.category = category
