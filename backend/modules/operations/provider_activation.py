"""ServiceOperations' ProviderActivation (U8 plan Step 21; BR7.1–BR7.8, BR9.4, BR9.5,
BR9.7, BR9.14; functional spec "State machine — ProviderActivation").

One ledger entity per real provider (`provider-activation`, keyed by provider). This
component folds them, moves them by the machine, and implements the two ports the
adapters own (`integrations/provider_gate.py`), so no owner imports ServiceOperations:

- `ProviderGate`: `mode` (`synthetic`, `rehearsal` or `live`) and `state(provider)`,
  answered in the gate's vocabulary: `held` while held, `unavailable` while unconfigured
  or unavailable, otherwise `active` (a degraded provider still serves, with its
  limitations shown).
- `RehearsalRecipients`: whether an account, or a Notion connection, is the maintainer's.
  The profile names the maintainer by its v2 account (BR8.3); a connection is the
  maintainer's when the composition's `connection_owner` says that account owns it. The
  composition builds that read with `connection_owner_reader`: ApprovedExport's definer
  function `export.connection_owner`, called through ServiceOperations' own login, which
  answers a pending row's owner too, so the maintainer's first configure (checked on a
  candidate token that carries only its connection id) is known as the maintainer's. An
  owner read that fails reads as not the maintainer's, so the operation is held, and is
  logged as `provider.connection-owner-unread`.
- `FirstEffects`: `record_preview` below, and `approved_content`, the approved first
  effect's digest once the provider is active in live mode.

The machine, at a profile start (`start`):

- a provider without its secret is `unconfigured` (BR6.7);
- `models`, and every configured provider in rehearsal or a synthetic profile, is
  `active` (in rehearsal the adapters bind outward effects to the maintainer, BR7.5);
- in live mode an outward provider (`resend`, `notion`) or a sign-in provider (`google`,
  `orcid`) is `active` only while its approval still holds (below), otherwise `held`,
  shown as degraded with `first-effect-pending` or `sign-in-unverified` (BR7.3, BR7.8),
  with no approval fields;
- in live mode a sign-in provider whose real sign-in failed in the window (`unavailable`
  with `sign-in-verification-failed`) keeps exactly that record across v2's starts,
  until an abort or a rollback clears it for rehearsal or a declined decision returns
  it to held.

It leaves `held` only through your decision (`approve`): a MaintainerApproval in the
ledger for the provider's step (`provider-first-effect` or `provider-sign-in`), with the
subject `provider:<name>`, taken with the subject `cutover decide` showed (U8 plan
Step 106, CP-3). An approval holds only when it is bound to the current switch and is
the provider's latest decision:

- the current switch is the CutoverRecord while it is `switching`, `switched`,
  `settled` or `rolling-back` and holds `switchCheckedAt`; the shown subject's digest
  must be the approval's `subjectDigest`, the subject must name the provider's step,
  the provider and the current switch's `cutoverId`, and the approval must be recorded
  at or after `switchCheckedAt` (one CutoverRecord serves every switch, so the instant
  carries the binding);
- the latest decision is the last MaintainerApproval for the provider's step and
  subject reference, so a later decision supersedes an earlier one;
- an approved sign-in decision is applied only while the cutover is `switching` (the
  maintainer-only window);
- an outward provider's approved content is the subject's `previewDigest`, which must
  name a preview held in this switch. `record_preview` sets a preview file's
  modification time to the clock's instant each time the owning module records the
  held effect, so a preview's time says when its first effect was last held, and
  `previews_of(provider, since=...)` lists only the previews held since an instant: an
  earlier switch's preview, whose effect lived in a database the abort or the rollback
  recreated, is never approvable.

The owning module hands over the held effect's exact bytes, which are kept owner-only in
the profile's `evidence/previews/` folder under their own digest. A declining decision
returns an active provider to `held`, and a sign-in provider whose verification failed
to `held` too, so its real sign-in can be tried again in the same window; an approved
decision on the failed state is refused. An abort or a rollback clears `approvedAt`,
`approvalId` and `approvalContentHash` on every outward and sign-in provider
(`clear_approvals`), and the providers are evaluated again for the rehearsal mode the
profile returns to.

`bounds_lifted(provider)` answers BR7.6: true only in live mode, for an active provider
whose recorded approval is bound to the current switch, so it agrees with `state` until
a later decision is applied (`cutover provider-decision`) or the next live start writes
`held`. Every due-time comes from the injected clock.

`provider_word(activation, word, document)` is the service side of the cutover's three
provider words, the one code path the production tool's in-person words and the tests'
stage run: `provider-previews` (the previews held since the switch's check, or one's
exact content), `provider-decision` (`approve` with the decision's id and its shown
subject) and `provider-failed` (`fail_verification` while the cutover is switching).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from .cutover import KIND as CUTOVER_KIND
from .cutover import subject_digest
from .errors import OperationsError
from .ledger import utc_text

KIND = "provider-activation"
APPROVAL_KIND = "maintainer-approval"
PROVIDERS = ("google", "orcid", "resend", "models", "notion")
OUTWARD = ("resend", "notion")
SIGN_IN = ("google", "orcid")
MODES = ("synthetic", "rehearsal", "live")
STATES = ("unconfigured", "held", "active", "degraded", "unavailable")
STEPS = {**{name: "provider-first-effect" for name in OUTWARD},
         **{name: "provider-sign-in" for name in SIGN_IN}}
HELD_REASONS = {**{name: "first-effect-pending" for name in OUTWARD},
                **{name: "sign-in-unverified" for name in SIGN_IN}}
VERIFICATION_FAILED = "sign-in-verification-failed"
PREVIEW_SUFFIX = ".preview"
MAX_PREVIEW_BYTES = 2_000_000
MAX_PREVIEWS = 64
_APPROVAL_FIELDS = ("approvalContentHash", "approvalId", "approvedAt")
# The CutoverRecord's states in which a switch is current: an approval binds to it.
CURRENT_SWITCH = ("switching", "switched", "settled", "rolling-back")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)


def _instant(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _microseconds(moment: dt.datetime) -> int:
    """An aware instant as whole microseconds since the epoch, exactly."""
    return (moment - _EPOCH) // dt.timedelta(microseconds=1)


@dataclass(frozen=True)
class ActivationSettings:
    """What the profile says: its mode, the maintainer's account, the configured
    providers and the owner-only previews folder."""

    mode: str
    maintainer_account: UUID | None
    configured: frozenset[str]
    previews: Path | None = None

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError("activation mode outside its vocabulary")
        if not self.configured <= set(PROVIDERS):
            raise ValueError("configured providers outside the registered set")
        if self.mode == "live" and self.maintainer_account is None:
            raise ValueError("live mode needs the maintainer's account")

    @classmethod
    def from_profile(cls, profile, providers: dict[str, str]) -> ActivationSettings:
        """The production profile's mode and maintainer, or `synthetic` for every other
        profile. `providers` is the start check's `provider.<name>` configuration; Notion
        (each owner's own token) and the model runtime need no service secret."""
        configured = {"notion", "models"} | {
            capability.split(".", 1)[1]
            for capability, state in providers.items() if state == "configured"
        }
        production = getattr(profile, "is_production", False)
        return cls(
            mode=profile.mode if production else "synthetic",
            maintainer_account=getattr(profile, "maintainer_account", None),
            configured=frozenset(configured),
            previews=profile.root / "evidence" / "previews",
        )


OWNER_READ_LOGIN = "operations"


def connection_owner_reader(transactions) -> Callable[[UUID], UUID | None]:
    """The composition's `connection_owner`: the account that owns a Notion connection,
    pending rows included, or None for an unknown id. One short transaction under
    ServiceOperations' login, through ApprovedExport's definer function
    (`u8_export_connection_owner.sql`), the only privilege that login holds there."""

    def owner(connection_id: UUID) -> UUID | None:
        if not isinstance(connection_id, UUID):
            raise TypeError("a connection id is required")
        row = transactions.run(OWNER_READ_LOGIN, lambda conn: conn.execute(
            "SELECT export.connection_owner(%s) AS owner", (connection_id,)).fetchone())
        return None if row is None else row["owner"]

    return owner


def _known(provider: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError("provider outside the registered set")


class ProviderActivation:
    def __init__(self, ledger, settings: ActivationSettings, *, clock: Callable[[], dt.datetime],
                 connection_owner: Callable[[UUID], UUID | None] | None = None):
        self.ledger, self.settings, self.clock = ledger, settings, clock
        self._connection_owner = connection_owner

    # --- the ports ----------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self.settings.mode

    def state(self, provider: str) -> str:
        current = self.record(provider)
        value = current["state"] if current else (
            "active" if provider in self.settings.configured and self.mode != "live"
            else "unavailable")
        if value == "held":
            return "held"
        return "unavailable" if value in ("unconfigured", "unavailable") else "active"

    def is_maintainer_account(self, account_id) -> bool:
        maintainer = self.settings.maintainer_account
        return maintainer is not None and account_id == maintainer

    def is_maintainer_connection(self, connection_id) -> bool:
        if (self._connection_owner is None or connection_id is None
                or self.settings.maintainer_account is None):
            return False
        try:
            owner = self._connection_owner(connection_id)
        except Exception as error:  # fail closed: the operation is held, never sent
            from backend.log_events import log_exception

            log_exception("operations", "provider.connection-owner-unread", error)
            return False
        return self.is_maintainer_account(owner)

    # --- reading ------------------------------------------------------------------

    def record(self, provider: str) -> dict | None:
        _known(provider)
        return self.ledger.get(KIND, provider)

    def approved_content(self, provider: str) -> str | None:
        """The `FirstEffects` port: the digest of the first effect your decision approved,
        while the outward provider is active in live mode on that approval."""
        if provider not in OUTWARD or not self.bounds_lifted(provider):
            return None
        return self.record(provider).get("approvalContentHash")

    def bounds_lifted(self, provider: str) -> bool:
        """BR7.6: the unit bounds lift only in live mode, once the provider is active
        on a recorded approval bound to the current switch. A later decision recorded
        but not yet applied does not lower them: it takes effect when `cutover
        provider-decision` applies it or at the next live start, so this answer agrees
        with `state` meanwhile."""
        current = self.record(provider)
        return (
            self.mode == "live"
            and current is not None
            and current["state"] in ("active", "degraded")
            and "approvedAt" in current
            and self._bound_to_switch(provider, current)
        )

    # --- the binding of an approval (U8 plan Step 106(b), CP-3) ----------------------

    def _current_switch(self) -> dict | None:
        """The CutoverRecord while a switch is current (it holds `switchCheckedAt`),
        else None."""
        records = self.ledger.records(CUTOVER_KIND)
        if not records:
            return None
        record = records[-1]
        if record.get("state") in CURRENT_SWITCH and record.get("switchCheckedAt"):
            return record
        return None

    def _switch_checked(self) -> dt.datetime | None:
        record = self._current_switch()
        return None if record is None else _instant(record["switchCheckedAt"])

    def _latest_decision(self, provider: str) -> dict | None:
        """The last MaintainerApproval, in the ledger's order, for the provider's step
        and subject reference."""
        latest = None
        for approval in self.ledger.records(APPROVAL_KIND):
            if (approval.get("step") == STEPS.get(provider)
                    and approval.get("subjectRef") == "provider:" + provider):
                latest = approval
        return latest

    def _bound_to_switch(self, provider: str, record: Mapping) -> bool:
        """The record's approval is an approved decision for the provider, recorded at
        or after the current switch's check."""
        if provider not in STEPS or "approvedAt" not in record or "approvalId" not in record:
            return False
        if provider in OUTWARD and "approvalContentHash" not in record:
            return False
        checked = self._switch_checked()
        if checked is None:
            return False
        approval = self.ledger.get(APPROVAL_KIND, str(record["approvalId"]))
        return (
            approval is not None
            and approval["decision"] == "approved"
            and approval["step"] == STEPS[provider]
            and approval["subjectRef"] == "provider:" + provider
            and _instant(approval["recordedAt"]) >= checked
        )

    def _approval_holds(self, provider: str, record: Mapping) -> bool:
        """Bound to the current switch, and the provider's latest decision."""
        if not self._bound_to_switch(provider, record):
            return False
        latest = self._latest_decision(provider)
        return latest is not None and latest["approvalId"] == str(record["approvalId"])

    # --- the machine --------------------------------------------------------------

    @staticmethod
    def _verification_failed(provider: str, current: Mapping | None) -> bool:
        return (
            provider in SIGN_IN
            and current is not None
            and current.get("state") == "unavailable"
            and VERIFICATION_FAILED in current.get("limitations", [])
        )

    def _evaluated(self, provider: str, current: dict | None) -> dict:
        """The machine's answer at a profile start."""
        outward = provider in OUTWARD
        approval = {name: current[name] for name in _APPROVAL_FIELDS
                    if current and name in current}
        if provider not in self.settings.configured:
            return {"provider": provider, "outward": outward, "state": "unconfigured",
                    "limitations": []}
        if provider == "models" or self.mode != "live":
            return {"provider": provider, "outward": outward, "state": "active",
                    "limitations": [], **approval}
        if self._verification_failed(provider, current):
            # Kept across v2's starts until an abort or a rollback, or a declined
            # decision, moves it (BR7.8).
            return {"provider": provider, "outward": False, "state": "unavailable",
                    "limitations": [VERIFICATION_FAILED]}
        if current is not None and self._approval_holds(provider, current):
            return {"provider": provider, "outward": outward, "state": "active",
                    "limitations": [], **approval}
        return {"provider": provider, "outward": outward, "state": "held",
                "limitations": [HELD_REASONS[provider]]}

    def _write(self, provider: str, record: dict) -> dict:
        def step(view):
            current = view.get(KIND, provider)
            if current == record:
                return current
            view.append(KIND, record, expect_revision=view.revision(KIND, provider))
            return record

        return self.ledger.atomic(step)

    def start(self) -> dict[str, str]:
        """Evaluate every provider for the profile now starting; returns each state."""
        states = {}
        for provider in PROVIDERS:
            record = self._evaluated(provider, self.record(provider))
            states[provider] = self._write(provider, record)["state"]
        return states

    def approve(self, provider: str, approval_id: UUID, subject: Mapping) -> dict:
        """Your recorded decision (BR9.14), taken with the subject `cutover decide`
        showed, moves a held provider to active, or a declining one returns it to held.
        The decision must be bound to the current switch and be the provider's latest;
        each refusal changes nothing."""
        _known(provider)
        if provider not in STEPS:
            raise OperationsError("FAILED_PRECONDITION", current={"reasonKey": "not-held-by-you"})
        approval = self.ledger.get(APPROVAL_KIND, str(approval_id))
        if (
            approval is None
            or approval["step"] != STEPS[provider]
            or approval["subjectRef"] != "provider:" + provider
        ):
            raise OperationsError("CONFLICT", current={"reasonKey": "approval-subject-differs"})
        if (
            not isinstance(subject, Mapping)
            or subject_digest(subject) != approval["subjectDigest"]
            or subject.get("step") != STEPS[provider]
            or subject.get("provider") != provider
        ):
            raise OperationsError("CONFLICT", current={"reasonKey": "approval-subject-differs"})
        switch = self._current_switch()
        checked = self._switch_checked()
        if (
            switch is None
            or subject.get("cutoverId") != switch["cutoverId"]
            or _instant(approval["recordedAt"]) < checked
        ):
            raise OperationsError("CONFLICT",
                                  current={"reasonKey": "approval-outside-this-switch"})
        latest = self._latest_decision(provider)
        if latest is None or latest["approvalId"] != approval["approvalId"]:
            raise OperationsError("CONFLICT", current={"reasonKey": "approval-superseded"})
        current = self.record(provider)
        if approval["decision"] == "declined":
            return self._decline(provider, current)
        if provider in SIGN_IN and switch["state"] != "switching":
            raise OperationsError("CONFLICT",
                                  current={"reasonKey": "sign-in-outside-the-window"})
        if self.mode != "live" or current is None or current["state"] != "held":
            raise OperationsError("FAILED_PRECONDITION", current={"reasonKey": "provider-not-held"})
        content = subject.get("previewDigest")
        if provider in OUTWARD and content not in self.previews_of(provider, since=checked):
            raise OperationsError("CONFLICT", current={"reasonKey": "approval-subject-differs"})
        record = {"provider": provider, "outward": provider in OUTWARD, "state": "active",
                  "limitations": [], "approvalId": str(approval_id),
                  "approvedAt": utc_text(self.clock())}
        if provider in OUTWARD:
            record["approvalContentHash"] = content
        return self._write(provider, record)

    def _decline(self, provider: str, current: dict | None) -> dict:
        serving = current is not None and current["state"] in ("held", "active", "degraded")
        if self.mode != "live" or not (serving or self._verification_failed(provider, current)):
            raise OperationsError("FAILED_PRECONDITION", current={"reasonKey": "provider-not-held"})
        return self._write(provider, {"provider": provider, "outward": provider in OUTWARD,
                                      "state": "held", "limitations": [HELD_REASONS[provider]]})

    def fail_verification(self, provider: str) -> dict:
        """A held sign-in provider whose real sign-in failed stays unavailable at opening
        unless the switch aborts (BR7.8, BR9.4)."""
        current = self.record(provider)
        if provider not in SIGN_IN or current is None or current["state"] != "held":
            raise OperationsError("FAILED_PRECONDITION", current={"reasonKey": "provider-not-held"})
        return self._write(provider, {"provider": provider, "outward": False,
                                      "state": "unavailable",
                                      "limitations": [VERIFICATION_FAILED]})

    def report_service(self, provider: str, outcome: str, reason: str | None = None) -> dict:
        """An active provider that is unreachable, refusing or over its limit becomes
        degraded or unavailable with its reason, and active again once it serves
        (BR7.2). A held or unconfigured provider is not moved this way."""
        if outcome not in ("active", "degraded", "unavailable") or (
            (outcome == "active") != (reason is None)
        ):
            raise ValueError("service outcome outside its vocabulary")
        current = self.record(provider)
        if current is None or current["state"] not in ("active", "degraded", "unavailable") or (
            current["state"] == "unavailable" and VERIFICATION_FAILED in current["limitations"]
        ):
            raise OperationsError("FAILED_PRECONDITION",
                                  current={"reasonKey": "provider-not-serving"})
        if (outcome == "active" and self.mode == "live" and provider in STEPS
                and not self._approval_holds(provider, current)):
            # Serving again never activates a provider whose approval does not hold
            # (R-116's row "degraded, unavailable | serves again").
            return self._write(provider, {"provider": provider,
                                          "outward": provider in OUTWARD, "state": "held",
                                          "limitations": [HELD_REASONS[provider]]})
        record = {**current, "state": outcome, "limitations": [reason] if reason else []}
        return self._write(provider, record)

    def clear_approvals(self, *, mode: str = "rehearsal") -> dict[str, str]:
        """An abort or a rollback (BR9.5, BR9.7): every outward and sign-in provider's
        approval is cleared, and the providers are evaluated for the mode the profile
        returns to, so the next switch verifies each again in its own window."""
        if mode not in MODES:
            raise ValueError("activation mode outside its vocabulary")
        self.settings = ActivationSettings(mode, self.settings.maintainer_account,
                                           self.settings.configured, self.settings.previews)
        states = {}
        for provider in PROVIDERS:
            current = self.record(provider)
            if provider in STEPS and current is not None:
                current = {k: v for k, v in current.items() if k not in _APPROVAL_FIELDS}
            states[provider] = self._write(provider, self._evaluated(provider, current))["state"]
        return states

    # --- previews of held first effects ---------------------------------------------

    def record_preview(self, provider: str, content: bytes) -> str:
        """Keep a held first effect's exact content as its preview (BR7.3) and return its
        digest, the subject your decision approves. Only while an outward provider is
        held in live mode; the same bytes give the same file."""
        if provider not in OUTWARD or self.mode != "live" or self.state(provider) != "held":
            raise OperationsError("FAILED_PRECONDITION", current={"reasonKey": "provider-not-held"})
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_PREVIEW_BYTES:
            raise ValueError("a preview is the effect's bounded exact bytes")
        folder = self._previews_folder()
        digest = hashlib.sha256(content).hexdigest()
        path = folder / f"{provider}-{digest}{PREVIEW_SUFFIX}"
        if path.exists() or path.is_symlink():
            if self._read_preview(path) != digest:
                raise OperationsError("INTERNAL", current={"reasonKey": "preview-custody"})
            self._mark_held(path)
            return digest
        if len(list(folder.iterdir())) >= MAX_PREVIEWS:
            raise OperationsError("RESOURCE_EXHAUSTED", current={"reasonKey": "preview-capacity"})
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        self._mark_held(path)
        return digest

    def _mark_held(self, path: Path) -> None:
        """The preview's modification time says when its first effect was last held:
        the clock's instant, set exactly (whole microseconds, as nanoseconds)."""
        instant = _microseconds(self.clock()) * 1000
        os.utime(path, ns=(instant, instant), follow_symlinks=False)

    def previews_of(self, provider: str, *, since: dt.datetime | None = None) -> frozenset[str]:
        """The digests of the provider's recorded previews whose bytes still match; with
        `since`, only those held at or after that instant (their modification time)."""
        _known(provider)
        folder = self.settings.previews
        if folder is None or not folder.is_dir():
            return frozenset()
        floor = None if since is None else _microseconds(since)
        found = set()
        for path in sorted(folder.glob(f"{provider}-*{PREVIEW_SUFFIX}"))[:MAX_PREVIEWS]:
            digest = path.name[len(provider) + 1:-len(PREVIEW_SUFFIX)]
            if self._read_preview(path) != digest:
                continue
            if floor is not None and (path.lstat().st_mtime_ns + 500) // 1000 < floor:
                continue
            found.add(digest)
        return frozenset(found)

    def preview_content(self, provider: str, digest: str) -> bytes | None:
        """A preview held in the current switch, its exact bytes; else None (no
        current switch, a digest not of that form or not listed, or a preview whose
        custody fails)."""
        checked = self._switch_checked()
        if (checked is None or not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None
                or digest not in self.previews_of(provider, since=checked)):
            return None
        path = self.settings.previews / f"{provider}-{digest}{PREVIEW_SUFFIX}"
        if self._read_preview(path) != digest:
            return None
        content = path.read_bytes()
        return content if hashlib.sha256(content).hexdigest() == digest else None

    def _previews_folder(self) -> Path:
        folder = self.settings.previews
        if folder is None:
            raise OperationsError("FAILED_PRECONDITION",
                                  current={"reasonKey": "no-previews-folder"})
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise OperationsError("INTERNAL", current={"reasonKey": "preview-custody"})
        folder.mkdir(mode=0o700, parents=False, exist_ok=True)
        if folder.stat().st_mode & 0o077:
            raise OperationsError("INTERNAL", current={"reasonKey": "preview-custody"})
        return folder

    @staticmethod
    def _read_preview(path: Path) -> str | None:
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            return None
        return hashlib.sha256(path.read_bytes()[: MAX_PREVIEW_BYTES + 1]).hexdigest()


# --- the cutover's three provider words, their service side (U8 plan Step 106(b)) --------

PROVIDER_WORDS = ("provider-previews", "provider-decision", "provider-failed")


def _word_refused() -> OperationsError:
    return OperationsError("INVALID_INPUT", current={"reasonKey": "word-or-input-refused"})


def _provider_of(document: Mapping, allowed: tuple[str, ...]) -> str:
    provider = document.get("provider")
    if not isinstance(provider, str):
        raise _word_refused()
    if provider not in allowed:
        raise OperationsError("INVALID_INPUT",
                              current={"reasonKey": "provider-outside-its-word"})
    return provider


def _answer(record: Mapping) -> dict:
    answer = {"provider": record["provider"], "state": record["state"],
              "limitations": list(record.get("limitations", []))}
    for name in ("approvedAt", "approvalContentHash"):
        if name in record:
            answer[name] = record[name]
    return answer


def _previews_word(activation: ProviderActivation, document: Mapping) -> dict:
    if set(document) not in ({"provider"}, {"provider", "digest"}):
        raise _word_refused()
    provider = _provider_of(document, OUTWARD)
    checked = activation._switch_checked()
    if "digest" not in document:
        held = [] if checked is None else sorted(activation.previews_of(provider, since=checked))
        folder = activation.settings.previews
        return {"provider": provider, "previews": [
            {"digest": digest,
             "sizeBytes": (folder / f"{provider}-{digest}{PREVIEW_SUFFIX}").lstat().st_size}
            for digest in held]}
    digest = document["digest"]
    if not isinstance(digest, str):
        raise _word_refused()
    content = activation.preview_content(provider, digest)
    if content is None:
        raise OperationsError("CONFLICT", current={"reasonKey": "preview-not-recorded"})
    try:
        parsed = json.loads(content)
    except ValueError:
        raise OperationsError("CONFLICT", current={"reasonKey": "preview-not-json"}) from None
    return {"provider": provider, "digest": digest, "sizeBytes": len(content),
            "content": parsed}


def _decision_word(activation: ProviderActivation, document: Mapping) -> dict:
    if set(document) != {"provider", "approvalId", "subject"}:
        raise _word_refused()
    provider = _provider_of(document, (*SIGN_IN, *OUTWARD))
    subject, approval_id = document["subject"], document["approvalId"]
    if not isinstance(subject, dict) or subject.get("provider") != provider or (
        not isinstance(approval_id, str)
    ):
        raise _word_refused()
    try:
        approval = UUID(approval_id)
    except ValueError:
        raise _word_refused() from None
    return _answer(activation.approve(provider, approval, subject))


def _failed_word(activation: ProviderActivation, document: Mapping) -> dict:
    if set(document) != {"provider"}:
        raise _word_refused()
    provider = _provider_of(document, SIGN_IN)
    records = activation.ledger.records(CUTOVER_KIND)
    if not records or records[-1].get("state") != "switching":
        raise OperationsError("FAILED_PRECONDITION",
                              current={"reasonKey": "cutover-not-switching"})
    return _answer(activation.fail_verification(provider))


def provider_word(activation: ProviderActivation, word: str, document: Mapping) -> dict:
    """The service side of the cutover's three provider words over a started
    ProviderActivation: the one code path the production tool's in-person words and the
    tests' stage run. It never calls `start()`."""
    if word not in PROVIDER_WORDS or not isinstance(document, Mapping):
        raise _word_refused()
    if word == "provider-previews":
        return _previews_word(activation, document)
    if word == "provider-decision":
        return _decision_word(activation, document)
    return _failed_word(activation, document)
