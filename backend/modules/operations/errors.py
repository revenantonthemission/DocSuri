"""Typed, non-revealing refusals of ServiceOperations.

`OperationsError` holds a frozen code plus bounded structured facts, in the shape of
`backend.modules.export.errors.ExportError`. `LedgerDamaged` holds only a fixed
category token: it never carries a record, a line of the ledger file or a digest
taken from it, so no private content can travel with it (BR3.4, NFR3.9).
"""

from __future__ import annotations

import re

_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_CATEGORY = re.compile(r"[a-z][a-z0-9-]{0,63}")


class OperationsError(RuntimeError):
    """A domain refusal; the code is one of the operation's frozen error codes.

    `current` carries the bounded facts a caller needs to recover, such as the
    entity's current revision on a conflict. It never carries private text.
    """

    def __init__(self, code: str, *, current: dict | None = None):
        if not isinstance(code, str) or _CODE.fullmatch(code) is None:
            raise ValueError("operations error code must be a frozen upper-case code")
        if current is not None and not isinstance(current, dict):
            raise ValueError("operations error facts must be a mapping")
        super().__init__(code)
        self.code = code
        self.current = current


class LedgerDamaged(RuntimeError):
    """The ledger's chain does not verify up to its head.

    The message is a fixed category token (for example `chain-break`, `head-mismatch`
    or `truncated`), so no record content can travel with it.
    """

    def __init__(self, category: str = "ledger-damaged"):
        if not isinstance(category, str) or _CATEGORY.fullmatch(category) is None:
            category = "ledger-damaged"
        super().__init__(category)
        self.category = category
