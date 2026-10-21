"""The export service: the eleven browser operations of C09 2.1.0 (Workflows 1–3, 6, 7).

`ExportService` is synchronous; the routes call it through `run_in_threadpool`. Every
method takes the server-derived `Authority` first and the request value as
`read_payload` produced it (the generated `*Http` model dumped in JSON mode, with absent
optional fields left out). Operations that keep an idempotency record also take the
request's `Idempotency-Key` as `operation`. Each method returns the camelCase wire form
of its output model (`views`), ready for `wire.<Model>.model_validate`.

Refusals:

- a domain refusal raises `ExportError` with a code from the operation's own frozen
  list (approve and execute keep CAPACITY_EXHAUSTED's `retry_after`);
- a foreign or absent record raises `LookupError`, which the shared boundary answers as
  NOT_FOUND, the same for both (BR7.1);
- a refused session surfaces as psycopg `InsufficientPrivilege` from the store's guard.

Notion is reached only through the adapter's read operations (identify, list, read
one page). Each adapter operation runs in its own event loop through `asyncio.run`; the
service never writes to Notion (BR2.2): only the export lane does.
"""

import asyncio
import contextlib
import datetime as dt
import re
from collections.abc import Callable, Mapping
from urllib.parse import urlsplit
from uuid import UUID

from backend.u6_policy import ExportPolicy

from .binding import BindingCheck, BoundFacts, read_source
from .classification import (
    NOT_CONNECTED,
    NOT_READABLE,
    OK,
    PROTECTION_UNAVAILABLE,
    TOKEN_INVALID,
    normalise_id,
)
from .connection_store import ConnectionSlot, SealedToken
from .errors import ExportError, ProtectionUnavailable
from .notion_session import CandidateToken, StoredConnection
from .preview_store import PreviewFacts, RenderedRevision
from .rendering import (
    binding_hash,
    build_page_body,
    check_limits,
    content_hash,
    derive_title,
    marker_for,
    project_text,
)
from .store_support import Replay, invalid, is_hex64, replay_input_hash
from .views import (
    FORMAT_REVISION,
    approval_view,
    connection_view,
    destination_entry,
    effect_view,
    history_view,
    preview_view,
    replayed_connection_view,
)

# The approval-validity policy recorded on every approval (BR3.5): valid exactly while
# its binding holds; no time-based expiry.
APPROVAL_VALIDITY_POLICY = {"policyId": "u6-approval-validity", "revision": "1"}
# The assumption the owner accepts when settling (BR4.5), as a fixed key.
SETTLE_ASSUMPTIONS = {
    "delivered": "owner-confirmed-page-present",
    "not-delivered": "owner-accepts-possible-second-copy",
}
# Identification answers that refuse a configure, with their code (BR1.2).
IDENTIFY_REFUSALS = {
    TOKEN_INVALID: "INVALID_TOKEN",
    NOT_READABLE: "INVALID_TOKEN",
    PROTECTION_UNAVAILABLE: "POLICY_UNRESOLVED",
}
# Definite changes found on a continue that answer with their own code (BR3.7).
CONTINUE_CODES = ("SOURCE_INELIGIBLE", "FORBIDDEN")
# A provisional marker as long as any real one, for the size check before rendering.
_PROBE_MARKER_REVISION = 999_999_999
_PROBE_PREVIEW = UUID(int=(1 << 128) - 1)
_NOTION_HOSTS = ("notion.so", "www.notion.so")
_PAGE_ID_TAIL = re.compile(r"(?:^|-)[0-9a-f]{32}$")
_REMOTE_URL_LIMIT = 2048
_REVISION = re.compile(r"[1-9][0-9]{0,9}")


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# -- argument checks (INVALID_ARGUMENT before any transaction) ---------------------------


def _uuid(value, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value) if isinstance(value, str) else invalid(field)
    except ValueError:
        invalid(field)


def _optional_uuid(value, field: str) -> UUID | None:
    return None if value is None else _uuid(value, field)


def _revision(value, field: str) -> int:
    """A wire revision: a decimal string (or integer) of at least 1."""
    if type(value) is int and value >= 1:
        return value
    if isinstance(value, str) and _REVISION.fullmatch(value):
        return int(value)
    invalid(field)


def _hash(value, field: str) -> str:
    if not is_hex64(value):
        invalid(field)
    return value


def _mapping(value, field: str) -> Mapping:
    if not isinstance(value, Mapping):
        invalid(field)
    return value


def notion_page_link(value) -> str:
    """BR4.7: an owner-supplied link is accepted only as a Notion page link: an https URL
    on a Notion host whose last path segment ends in a 32-hex page id."""
    if not isinstance(value, str) or not 1 <= len(value) <= _REMOTE_URL_LIMIT:
        invalid("remoteUrl")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        invalid("remoteUrl")
    host = (parts.hostname or "").lower()
    segment = parts.path.rstrip("/").rsplit("/", 1)[-1]
    if (
        parts.scheme != "https"
        or parts.username is not None
        or parts.password is not None
        or port not in (None, 443)
        or not (host in _NOTION_HOSTS or host.endswith(".notion.site"))
        or _PAGE_ID_TAIL.search(segment) is None
    ):
        invalid("remoteUrl")
    return value


class ExportService:
    def __init__(
        self,
        transactions,
        repository,
        adapter,
        vault,
        research,
        policy: ExportPolicy,
        clock: Callable[[], dt.datetime] = _utc_now,
    ):
        if not isinstance(policy, ExportPolicy):
            raise TypeError("an ExportPolicy is required")
        if repository.policy != policy or adapter.policy != policy:
            raise ValueError("the repository, adapter and service must share one policy")
        self.transactions = transactions
        self.repository = repository
        self.adapter = adapter
        self.vault = vault
        self.research = research
        self.policy = policy
        self.clock = clock
        self.binding = BindingCheck(repository, adapter, research, policy)

    # -- shared steps ----------------------------------------------------------------

    def _now(self) -> dt.datetime:
        now = self.clock()
        if not isinstance(now, dt.datetime) or now.tzinfo is None:
            raise ValueError("the clock must give an aware time")
        return now

    @staticmethod
    def _run(operation):
        """One adapter operation, in its own event loop (the routes' threadpool)."""
        return asyncio.run(operation)

    def _require_policy(self, value, field: str) -> None:
        """BR8.3: the only accepted policy reference is the export capability's."""
        if _mapping(value, field) != self.policy.reference():
            raise ExportError("POLICY_UNRESOLVED", current={"field": field})

    def _token(self, value) -> str:
        """BR1.2's minimal shape check; the value is never echoed."""
        token = value.strip() if isinstance(value, str) else ""
        if not token or len(token) > self.policy.token_max_length or not token.isprintable():
            invalid("token")
        return token

    def _effect(self, authority, effect_id: UUID, now: dt.datetime | None = None) -> dict:
        return effect_view(
            self.repository.read_effect(authority, effect_id, now=now or self._now())
        )

    # -- connection (Workflows 1 and 2) ------------------------------------------------

    def read_connection(self, authority, value: Mapping) -> dict:
        """A7: the owner's connection; absent and pending read as NOT_FOUND."""
        connection_id = _optional_uuid(value.get("connectionId"), "connectionId")
        return connection_view(
            self.repository.read_connection(authority, connection_id), self.policy
        )

    def configure(self, authority, value: Mapping, *, operation) -> dict:
        """BR1.1–BR1.3 and R-13/R-14: check, reserve, identify, seal, store."""
        token = self._token(value.get("token"))
        expected = value.get("expectedRevision")
        expected = None if expected is None else _revision(expected, "expectedRevision")
        self._require_policy(value.get("credentialPolicy"), "credentialPolicy")
        replay = Replay(_uuid(operation, "operationKey"), replay_input_hash(dict(value)))
        recorded = self.repository.configure_replay(authority, replay)
        if recorded is not None:
            return self._replayed_configure(authority, recorded)
        now = self._now()
        slot = self.repository.reserve_connection(authority, expected, now=now)
        stored = self._check_and_store(authority, slot, token, replay, now)
        if stored["replayed"]:
            return self._replayed_configure(authority, stored["response"])
        return connection_view(self.repository.read_connection(authority), self.policy)

    def _check_and_store(self, authority, slot: ConnectionSlot, token: str, replay, now) -> dict:
        settled = False
        try:
            identified = self._run(
                self.adapter.identify(
                    CandidateToken(slot.connection_id, token), gate_key=slot.connection_id
                )
            )
            if identified.category != OK:
                code = IDENTIFY_REFUSALS.get(identified.category, "DEPENDENCY_UNAVAILABLE")
                self._refuse_configure(authority, slot, replay, code)
                settled = True
                raise ExportError(code)
            sealed = self._seal(authority, slot, token, identified, now)
            stored = self.repository.store_configured(authority, slot, sealed, replay, now=now)
            settled = True
            return stored
        finally:
            if slot.pending and not settled:
                # R-02: release only the reservation this check still holds. If the
                # release itself fails, the takeover and the stale-pending sweep remove
                # the row; the original outcome is what the owner must see.
                with contextlib.suppress(Exception):
                    self.repository.release_pending(authority, slot.holder)

    def _refuse_configure(self, authority, slot: ConnectionSlot, replay, code: str) -> None:
        """Store nothing. A definite refusal keeps its replay record (code only)."""
        refusal = (replay, code) if code == "INVALID_TOKEN" else None
        if slot.pending:
            self.repository.release_pending(authority, slot.holder, refusal=refusal)
        elif refusal is not None:
            self.repository.record_configure_refusal(authority, replay, code)

    def _seal(self, authority, slot: ConnectionSlot, token: str, identified, now) -> SealedToken:
        failed = False
        try:
            envelope, version = self.vault.seal(
                token,
                account_id=authority.account_id,
                connection_id=slot.connection_id,
                revision=slot.next_revision,
            )
        except ProtectionUnavailable:
            failed = True
        if failed:
            raise ExportError("POLICY_UNRESOLVED", current={"field": "credentialProtection"})
        return SealedToken(
            envelope=envelope,
            key_version=version,
            workspace_name=identified.workspace_name,
            workspace_id=identified.workspace_id,
            connection_user_id=identified.integration_id,
            validated_at=now,
        )

    def _replayed_configure(self, authority, recorded: Mapping) -> dict:
        """A replay returns the original: its refusal code, or its connection."""
        if "code" in recorded:
            raise ExportError(recorded["code"])
        with contextlib.suppress(LookupError):
            row = self.repository.read_connection(authority)
            if (
                str(row["id"]) == recorded["connectionId"]
                and row["revision"] == recorded["revision"]
            ):
                return connection_view(row, self.policy)
        return replayed_connection_view(recorded, str(authority.account_id), self.policy)

    def disconnect(self, authority, value: Mapping) -> dict:
        """BR1.4: clear the token, advance the revision and end older pending work. A
        repeat returns the disconnected connection."""
        connection_id = _optional_uuid(value.get("connectionId"), "connectionId")
        result = self.repository.disconnect(authority, connection_id, now=self._now())
        return connection_view(result["connection"], self.policy)

    # -- destinations (BR1.5, BR8.2, A1, S2) --------------------------------------------

    def list_destinations(self, authority, value: Mapping) -> dict:
        connection_id = _optional_uuid(value.get("connectionId"), "connectionId")
        row = self.repository.read_connection(authority, connection_id)
        if row["state"] == "unavailable":
            raise ExportError("POLICY_UNRESOLVED", current={"field": "credentialProtection"})
        if row["state"] != "connected":
            raise ExportError("NOT_FOUND")
        listing = self._run(
            self.adapter.list_destinations(
                StoredConnection(authority.account_id, row["id"]),
                creation_capability=row["creation_capability"],
                last_destination_id=row["last_destination_id"],
                gate_key=row["id"],
            )
        )
        if listing.category in (TOKEN_INVALID, NOT_CONNECTED):
            raise ExportError("NOT_FOUND")
        if listing.category == PROTECTION_UNAVAILABLE:
            raise ExportError("POLICY_UNRESOLVED", current={"field": "credentialProtection"})
        view = {
            "connectionId": str(row["id"]),
            "connectionRevision": str(row["revision"]),
            "destinations": [self._entry(row, item, listing) for item in listing.destinations],
            "listingComplete": bool(listing.complete),
        }
        if listing.last_destination_id is not None:
            view["lastDestinationId"] = listing.last_destination_id
        return view

    def _entry(self, row, item, listing) -> dict:
        readable = item.readable
        if item.destination_id == listing.last_destination_id:
            # Only a successful direct read makes the preselection usable (BR1.5).
            readable = listing.last_destination_readable is True
        capability = row["creation_capability"]
        activation = self.policy.activation_destination_id
        allowed = activation is None or item.destination_id == activation
        return destination_entry(
            connection_id=str(row["id"]),
            workspace_id=row["workspace_id"],
            destination_id=item.destination_id,
            title=item.title,
            context=item.context,
            readable=readable,
            creation_capability=capability,
            writable=allowed and readable is not False and capability != "refused",
        )

    # -- preview (BR2.1–BR2.5) ------------------------------------------------------------

    def prepare_preview(self, authority, value: Mapping) -> dict:
        source = self._source_reference(value.get("source"))
        destination = _mapping(value.get("destination"), "destination")
        self._require_policy(value.get("renderPolicy"), "renderPolicy")
        destination_id = normalise_id(destination.get("parentPageId"))
        if destination_id is None:
            invalid("parentPageId")
        activation = self.policy.activation_destination_id
        if activation is not None and destination_id != activation:
            raise ExportError("FORBIDDEN", current={"field": "destination"})
        row = self._preview_connection(authority, destination)
        prepared, verdict = read_source(self.research, authority, source)
        if verdict is not None:
            raise ExportError(verdict.code, current={"field": "source"})
        entry = self._read_destination(authority, row, destination_id)
        facts, render = self._renderer(authority, source, prepared, row, destination_id, entry)
        stored = self.repository.add_preview_revision(authority, facts, render, now=self._now())
        return preview_view(stored)

    @staticmethod
    def _source_reference(value) -> dict:
        source = _mapping(value, "source")
        artifact_id = _uuid(source.get("artifactId"), "artifactId")
        revision = source.get("revision")
        if not isinstance(revision, str) or not 1 <= len(revision) <= 128:
            invalid("revision")
        return {
            "artifactId": str(artifact_id),
            "revision": revision,
            "contentHash": _hash(source.get("contentHash"), "contentHash"),
        }

    def _preview_connection(self, authority, destination: Mapping):
        """The owner's connected connection, which the request's destination must name;
        the server derives every destination fact itself (A1)."""
        row = self.repository.read_connection(authority)
        if row["state"] == "unavailable":
            raise ExportError("POLICY_UNRESOLVED", current={"field": "credentialProtection"})
        if (
            row["state"] != "connected"
            or destination.get("connectionId") != str(row["id"])
            or destination.get("workspaceId") != row["workspace_id"]
            or destination.get("formatRevision") != FORMAT_REVISION
        ):
            raise ExportError("CONFLICT", current={"field": "destination"})
        return row

    def _read_destination(self, authority, row, destination_id: str) -> dict:
        """The destination read directly, through the gate (BR1.5, D15)."""
        read = self._run(
            self.adapter.read_destination(
                StoredConnection(authority.account_id, row["id"]),
                destination_id,
                gate_key=row["id"],
            )
        )
        if read.category == PROTECTION_UNAVAILABLE:
            raise ExportError("POLICY_UNRESOLVED", current={"field": "credentialProtection"})
        if read.category in (NOT_READABLE, TOKEN_INVALID, NOT_CONNECTED):
            raise ExportError("CONFLICT", current={"field": "destination"})
        if read.category != OK or not read.readable:
            raise ExportError("DEPENDENCY_UNAVAILABLE")
        capability = row["creation_capability"]
        return destination_entry(
            connection_id=str(row["id"]),
            workspace_id=row["workspace_id"],
            destination_id=destination_id,
            title=read.title,
            context=read.context,
            readable=True,
            creation_capability=capability,
            writable=capability != "refused",
        )

    def _renderer(self, authority, source, prepared, row, destination_id, entry):
        """The preview facts and the pure render step the store runs inside its
        transaction, once it knows the preview id and the next revision (BR2.3)."""
        output = prepared.get("output")
        eligibility = prepared.get("currentEligibilityRevision")
        refused = False
        try:
            summary = output.get("summary") if isinstance(output, Mapping) else None
            title = derive_title(summary, source["artifactId"])
            probe = build_page_body(
                output, title=title, marker=marker_for(_PROBE_PREVIEW, _PROBE_MARKER_REVISION)
            )
            refused = check_limits(probe) is not None
        except ValueError:
            refused = True
        if refused or not isinstance(eligibility, str | int) or str(eligibility) == "":
            raise ExportError("SOURCE_INELIGIBLE", current={"field": "size"})
        policy = self.policy.reference()
        facts = PreviewFacts(
            artifact_id=UUID(source["artifactId"]),
            destination_id=destination_id,
            source_revision=source["revision"],
            source_content_hash=source["contentHash"],
            source_eligibility_revision=str(eligibility),
            source_title=title,
            connection_id=row["id"],
            connection_revision=row["revision"],
            destination=entry,
            render_policy=policy,
        )

        def render(preview_id: UUID, revision: int) -> RenderedRevision:
            marker = marker_for(preview_id, revision)
            body = build_page_body(output, title=title, marker=marker)
            if check_limits(body) is not None:
                raise ExportError("SOURCE_INELIGIBLE", current={"field": "size"})
            rendered = content_hash(body)
            bound = binding_hash(
                {
                    "ownerId": str(authority.account_id),
                    "previewId": str(preview_id),
                    "revision": str(revision),
                    "source": source,
                    "sourceEligibilityRevision": str(eligibility),
                    "connectionRevision": str(row["revision"]),
                    "destination": entry,
                    "renderedContentHash": rendered,
                    "renderPolicy": policy,
                }
            )
            return RenderedRevision(marker, body, project_text(body), rendered, bound)

        return facts, render

    # -- approve and execute (BR3.1, BR3.2, BR3.7, BR5.1, BR5.2) --------------------------

    def approve(self, authority, value: Mapping, *, operation) -> dict:
        preview_id = _uuid(value.get("previewId"), "previewId")
        revision = _revision(value.get("previewRevision"), "previewRevision")
        bound_hash = _hash(value.get("bindingHash"), "bindingHash")
        key = _uuid(operation, "operationKey")
        replayed = self.repository.approval_replay(authority, key, preview_id, revision, bound_hash)
        if replayed is not None:
            return approval_view(replayed["approval"])
        if value.get("explicitApproval") is not True:
            invalid("explicitApproval")
        row = self.repository.read_preview(authority, preview_id, revision)
        if (
            row["current_revision"] != revision
            or row["binding_hash"] != bound_hash
            or row["trimmed_at"] is not None
        ):
            raise ExportError("CONFLICT", current={"revision": str(row["current_revision"])})
        facts = BoundFacts.of(
            row,
            account_id=authority.account_id,
            approving_session=authority.session_id,
            artifact_id=row["artifact_id"],
            destination_id=row["destination_id"],
        )
        verdict = self.binding.check(facts, gate_key=row["connection_id"])
        if not verdict.unchanged:
            raise ExportError(verdict.code, current={"reason": verdict.reason})
        recorded = self.repository.record_approval(
            authority,
            key,
            preview_id,
            revision,
            bound_hash,
            APPROVAL_VALIDITY_POLICY,
            now=self._now(),
        )
        return approval_view(recorded["approval"])

    def execute(self, authority, value: Mapping, *, operation) -> dict:
        approval_id = _uuid(value.get("approvalId"), "approvalId")
        bound_hash = _hash(value.get("bindingHash"), "bindingHash")
        key = _uuid(operation, "operationKey")
        replayed = self.repository.execute_replay(authority, key, approval_id)
        if replayed is not None:
            return self._effect(authority, replayed["effect"]["id"])
        read = self.repository.read_approval(authority, approval_id)
        approval = read["approval"]
        if approval["binding_hash"] != bound_hash:
            raise ExportError("CONFLICT", current={"field": "bindingHash"})
        if approval["state"] != "approved":
            raise ExportError("APPROVAL_REQUIRED")
        if approval["request_key"] != key:
            self._continue(authority, approval, read["revision"])
        now = self._now()
        bound = self.repository.bind_effect(authority, approval_id, key, now=now)
        return self._effect(authority, bound["effect"]["id"], now)

    def _continue(self, authority, approval, revision) -> None:
        """BR3.7: a continue re-derives the binding under the approving session. A
        definite change invalidates the approval; could-not-check leaves it approved."""
        facts = BoundFacts.of(
            revision,
            account_id=approval["account_id"],
            approving_session=approval["approving_session"],
            artifact_id=revision["artifact_id"],
            destination_id=revision["destination_id"],
        )
        verdict = self.binding.check(facts, gate_key=revision["connection_id"])
        if verdict.unchanged:
            return
        if not verdict.changed:
            raise ExportError(verdict.code, current={"reason": verdict.reason})
        self.repository.invalidate_approval(
            authority, approval["id"], verdict.reason, now=self._now()
        )
        # A source U4 no longer exports, or a destination outside the real allowance,
        # keeps its own code; every other change needs a fresh approval.
        code = verdict.code if verdict.code in CONTINUE_CODES else "APPROVAL_REQUIRED"
        raise ExportError(code, current={"reason": verdict.reason})

    # -- cancel, settle and reads (BR3.6, BR4.5, A2–A4, A10) ------------------------------

    def cancel(self, authority, value: Mapping) -> dict:
        approval_id = _uuid(value.get("approvalId"), "approvalId")
        expected = _revision(value.get("expectedRevision"), "expectedRevision")
        result = self.repository.cancel(authority, approval_id, expected, now=self._now())
        return approval_view(result["approval"])

    def settle(self, authority, value: Mapping, *, operation) -> dict:
        effect_id = _uuid(value.get("effectId"), "effectId")
        expected = _revision(value.get("expectedRevision"), "expectedRevision")
        disposition = value.get("disposition")
        if disposition not in SETTLE_ASSUMPTIONS:
            invalid("disposition")
        if value.get("assumptionAccepted") is not True:
            invalid("assumptionAccepted")
        remote_url = value.get("remoteUrl")
        if remote_url is not None:
            notion_page_link(remote_url)
            if disposition != "delivered":
                invalid("remoteUrl")
        replay = Replay(_uuid(operation, "operationKey"), replay_input_hash(dict(value)))
        now = self._now()
        self.repository.settle(
            authority,
            effect_id,
            expected,
            disposition,
            replay,
            assumption=SETTLE_ASSUMPTIONS[disposition],
            remote_url=remote_url,
            now=now,
        )
        return self._effect(authority, effect_id, now)

    def read_effect(self, authority, value: Mapping) -> dict:
        return self._effect(authority, _uuid(value.get("effectId"), "effectId"))

    def history(self, authority, value: Mapping) -> dict:
        limit = value.get("limit", self.policy.history_page_max)
        cursor = value.get("cursor")
        page = self.repository.history(authority, limit=limit, cursor=cursor, now=self._now())
        return history_view(page)
