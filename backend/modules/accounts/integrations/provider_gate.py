"""Two ports the provider adapters own, wired by the composition (U8 plan Step 21; A7,
BR7.3, BR7.5, BR7.8, NFR2.2).

- `ProviderGate` answers, for one provider, whether an outward effect may go now:
  `active`, `held` or `unavailable`, and the profile's mode (`synthetic`, `rehearsal` or
  `live`). The adapters read it before every effect.
- `RehearsalRecipients` answers whether a recipient account, or a Notion connection, is
  the maintainer's own. In rehearsal every other recipient or connection is held as not
  permitted (BR7.5).
- `FirstEffects` takes a held provider's first effect as its preview and answers the
  digest your decision approved (BR7.3).

ServiceOperations' `ProviderActivation` implements both from the ledger and the profile
(Step 21). The ports live with the adapters, as the email allowance's does, so no owner
imports ServiceOperations and the component graph stays as components.md has it.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable
from uuid import UUID

PROVIDERS = ("google", "orcid", "resend", "notion", "models")
STATES = ("active", "held", "unavailable")
MODES = ("synthetic", "rehearsal", "live")


@runtime_checkable
class ProviderGate(Protocol):
    @property
    def mode(self) -> str: ...

    def state(self, provider: str) -> str: ...


@runtime_checkable
class RehearsalRecipients(Protocol):
    def is_maintainer_account(self, account_id: UUID) -> bool: ...

    def is_maintainer_connection(self, connection_id: UUID) -> bool: ...


@runtime_checkable
class FirstEffects(Protocol):
    """A held outward provider's first effect (BR7.3): the owning module records the
    effect's exact content, addressed to the maintainer, as its preview and gets the
    digest your decision approves; `approved_content` is that approved digest once the
    provider is active in live mode, else None."""

    def record_preview(self, provider: str, content: bytes) -> str: ...

    def approved_content(self, provider: str) -> str | None: ...


def require_state(gate: ProviderGate, provider: str) -> str:
    """The gate's answer for `provider`, refusing an answer outside the vocabulary."""
    if provider not in PROVIDERS:
        raise ValueError("provider outside the registered set")
    answer = gate.state(provider)
    if answer not in STATES or gate.mode not in MODES:
        raise ValueError("provider gate answer outside its vocabulary")
    return answer


def gate_active(gate: ProviderGate, provider: str = "resend") -> bool:
    """Whether the gate lets `provider` send now."""
    return require_state(gate, provider) == "active"


def rehearsal_refuses(gate, recipients, account_id) -> bool:
    """The rehearsal bound (BR7.5, NFR2.2): in rehearsal mode a message to any account
    but the maintainer's is held as not permitted. Without a gate nothing changes."""
    if gate is None or gate.mode != "rehearsal":
        return False
    return (
        recipients is None
        or account_id is None
        or not recipients.is_maintainer_account(account_id)
    )


def preview_bytes(value: dict) -> bytes:
    """The canonical bytes of a preview, so the same content always has the same digest."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
