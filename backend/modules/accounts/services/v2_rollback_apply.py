"""v1's side of a rollback: v2's lifecycle outcomes applied through v1's own account code
(U8 plan Step 27; BR9.13, A6 `platform.v1.lifecycle.apply`).

Only `platform.v1.lifecycle.apply` runs this module, with v1's runtime from v1's fixed
checkout. For each account v2 changed while it served, it applies the outcome the way
v1's own account code does it:

- `erase`: v1's soft deletion, due at once (`DEACTIVATED`, a deletion record whose
  `purge_after` is now), so v1's own purge job erases the account through its own path;
- `withdraw`: `DEACTIVATED`, with no deletion record, so v1 keeps the data;
- `reactivate`: v1's own reactivation when a deletion record waits, else `ACTIVE`.

Then every v1 session ends: each listed account's sessions are invalidated through v1's
`SessionManager`, so nobody continues in v1 under a session from before the switch.
Input is one bounded JSON object on standard input; one JSON result is written.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime

from ..models import AccountStatus

OUTCOMES = ("erase", "withdraw", "reactivate")
MAX_INPUT = 4 * 1024 * 1024
MAX_ACCOUNTS = 100_000


class ApplyRefused(ValueError):
    """The input is outside its form; nothing was applied."""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def validate(document: dict) -> tuple[list[dict], list[str]]:
    if not isinstance(document, dict) or set(document) != {"outcomes", "accounts"}:
        raise ApplyRefused("input-field-refused")
    outcomes, accounts = document["outcomes"], document["accounts"]
    if not isinstance(outcomes, list) or not isinstance(accounts, list) or (
        len(accounts) > MAX_ACCOUNTS or len(outcomes) > MAX_ACCOUNTS
    ):
        raise ApplyRefused("input-field-refused")
    for item in outcomes:
        if not isinstance(item, dict) or set(item) != {"v1AccountId", "outcome"} or (
            item["outcome"] not in OUTCOMES or not isinstance(item["v1AccountId"], str)
        ):
            raise ApplyRefused("outcome-refused")
    if not all(isinstance(item, str) and item for item in accounts):
        raise ApplyRefused("account-refused")
    return outcomes, accounts


class RollbackApplier:
    def __init__(self, credential_repo, session_manager, deletion_service, *, clock=_now):
        self.repo, self.sessions, self.deletion = credential_repo, session_manager, deletion_service
        self.clock = clock

    async def _apply_one(self, account_id: str, outcome: str) -> str:
        account = self.repo.get_by_id(account_id)
        if account is None:
            return "absent"
        if outcome == "reactivate":
            if self.repo.get_account_deletion(account_id) is not None:
                await self.deletion.reactivate(account_id)
            else:
                account.status = AccountStatus.ACTIVE.value
                self.repo.update_account(account)
            return "reactivated"
        account.status = AccountStatus.DEACTIVATED.value
        self.repo.update_account(account)
        if outcome == "erase":
            self.repo.create_account_deletion(account_id, self.clock())
            return "erased"
        return "withdrawn"

    async def apply(self, document: dict) -> dict:
        outcomes, accounts = validate(document)
        applied: dict[str, int] = {}
        try:
            for item in outcomes:
                state = await self._apply_one(item["v1AccountId"], item["outcome"])
                applied[state] = applied.get(state, 0) + 1
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        for account_id in sorted(set(accounts) | {item["v1AccountId"] for item in outcomes}):
            await self.sessions.invalidate_all_for_user(account_id)
        return {"applied": applied, "sessionsEnded": len(set(accounts))}


def _v1_applier():  # pragma: no cover - v1's runtime only, from v1's fixed checkout
    from backend.config import Settings
    from backend.db import make_engine
    from sqlalchemy.orm import sessionmaker

    from ..controller import get_session_repo
    from ..repository.credential import CredentialRepository
    from .account_deletion import AccountDeletionService
    from .session_manager import SessionManager

    settings = Settings.from_env()
    session = sessionmaker(bind=make_engine(settings.database_url), future=True)()
    repo = CredentialRepository(session)
    sessions = SessionManager(get_session_repo())
    return RollbackApplier(repo, sessions, AccountDeletionService(repo, sessions))


def main() -> int:  # pragma: no cover - the entry `platform.v1.lifecycle.apply` runs
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    try:
        if len(raw) > MAX_INPUT:
            raise ApplyRefused("input-too-large")
        result = asyncio.run(_v1_applier().apply(json.loads(raw)))
    except (ApplyRefused, ValueError) as refused:
        sys.stdout.write(json.dumps({"ok": False, "reason": str(refused)}) + "\n")
        return 1
    sys.stdout.write(json.dumps({"ok": True, **result}) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
