"""Shared arrangements for PlatformControl's bound-operation tests (U8 plan Step 28).

A journey uses the composed realm's PlatformControl store, logins and authorities (as its
tool provisioned them), with its own state and effects folders under the test's
temporary folder, so the realm's platform profile, services and tunnel routing are never
changed by a test. `Records` is the ledger view the preconditions read (`get`,
`records`), holding exactly the records a case states.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
import uuid
from pathlib import Path

from backend.local_profile import private_bytes
from docsuri_ops.arrangement.paths import DatabaseNames
from docsuri_ops.u8_platform.drivers import canonical
from docsuri_ops.u8_platform.platform_profile import REALM_LABELS, U8PlatformProfile
from docsuri_ops.u8_platform.u8_protocols import Facts, load_revision, realm_operator

NAMES = DatabaseNames("docsuri_u8")
KEYS = {
    "recovery-request": "recoveryRequestId", "maintainer-approval": "approvalId",
    "backup-set": "backupId", "retained-copy": "copyId", "ledger-copy": "ledgerCopyId",
    "cutover-record": "cutoverId",
}


class Records:
    """The ledger records one case states, read as the preconditions read the ledger."""

    def __init__(self, **kinds: list[dict]):
        self._kinds = {kind.replace("_", "-"): list(items) for kind, items in kinds.items()}

    def with_record(self, kind: str, record: dict) -> Records:
        kinds = {name: list(items) for name, items in self._kinds.items()}
        kinds.setdefault(kind, []).append(record)
        copy = Records()
        copy._kinds = kinds
        return copy

    def records(self, kind: str) -> list[dict]:
        return list(self._kinds.get(kind, []))

    def get(self, kind: str, key) -> dict | None:
        field = KEYS[kind]
        return next((item for item in self._kinds.get(kind, []) if item.get(field) == key),
                    None)


NOW = dt.datetime(2026, 10, 22, 12, 0, tzinfo=dt.UTC)
# The realm's store outlives a test session, and a key it has bound replays its receipt:
# every idempotency key carries this session's token so a re-run binds afresh.
RUN = uuid.uuid4().hex


def facts(*, mode: str = "rehearsal", admission: str = "maintainer-only",
          rehearsal: str | None = None, ledger: Records | None = None,
          databases: set[str] | None = None, now: dt.datetime = NOW) -> Facts:
    return Facts(NAMES, mode, admission, rehearsal, ledger or Records(), now,
                 lambda: set(databases or ()), REALM_LABELS)


def protocol(name: str):
    found = load_revision().by_name(name)
    assert found is not None, name
    return found


def _private_file(path: Path, value: object) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value))


@dataclasses.dataclass
class Journey:
    profile: U8PlatformProfile
    root: Path
    config: dict

    @property
    def state(self) -> Path:
        return self.profile.state_root

    def set_profile(self, **fields) -> None:
        current = json.loads((self.state / "profile.json").read_bytes())
        _private_file(self.state / "profile.json", {**current, **fields})

    def read_state(self, *parts: str) -> dict | None:
        path = self.state.joinpath(*parts)
        return json.loads(path.read_bytes()) if path.exists() else None

    def tunnel(self) -> dict | None:
        path = self.root / "tunnel-active.json"
        return json.loads(path.read_bytes()) if path.exists() else None

    def operator(self, role: str = "operator", *, ledger=None, clock=None, **options):
        return realm_operator(self.profile, role, ledger or Records(),
                              clock=clock or (lambda: NOW), **options)


DECISION_INPUTS = {"step": "production-restore", "subjectRef": "subject-1",
                   "subjectDigest": "e" * 64, "decision": "approved"}


class RealmReceipts:
    """Real receipts from the realm's store, read back as the ledger component reads
    them: each `add` executes one operation through the realm's operator (a decision for
    `platform.decision.record`, an isolation check otherwise; a `failed` outcome through
    U7's injected permission failure), and `read` is the service account's reader."""

    def __init__(self, journey: Journey, reader):
        self.journey, self.reader = journey, reader

    def add(self, operation: str, *, outcome: str = "succeeded",
            inputs: dict | None = None) -> dict:
        """`inputs` are a decision's own (`DECISION_INPUTS` when none are given)."""
        decision = operation == "platform.decision.record"
        name, target, inputs = (
            (operation, "decisions", inputs or DECISION_INPUTS) if decision
            else ("platform.isolation.check", "isolation", {"via": "in-person"})
        )
        receipt = self.journey.operator().execute(
            name, target, inputs, key=f"receipts-{uuid.uuid4().hex}",
            injected_fault=None if outcome == "succeeded" else "permission")
        assert receipt["outcome"] == outcome, receipt
        return dict(self.reader.read(receipt["operationId"]))

    def read(self, operation_id: str):
        return self.reader.read(operation_id)


def journey(tmp_path: Path, realm, *, mode: str = "rehearsal",
            admission: str = "maintainer-only", rehearsal: str | None = None,
            **config) -> Journey:
    """A journey on the realm's store with its own platform state and effects."""
    base = U8PlatformProfile.realm(Path(realm.root))
    root = tmp_path / "journey"
    root.mkdir(mode=0o700, parents=True)
    profile = dataclasses.replace(base, state_root=root / "state",
                                  effects_root=root / "effects")
    driver = json.loads(private_bytes(base.effects_root / "driver.json"))
    driver = {**driver, "stateRoot": str(profile.state_root), "tunnelRoot": str(root),
              **config}
    _private_file(profile.effects_root / "driver.json", driver)
    _private_file(profile.state_root / "profile.json", {
        "mode": mode, "admission": admission, "rehearsalDatabase": rehearsal,
        "backupVolume": {"identity": f"standin-{base.run_id}"},
    })
    return Journey(profile, root, driver)
