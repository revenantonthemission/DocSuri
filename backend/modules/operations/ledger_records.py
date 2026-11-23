"""The operations ledger's record kinds (U8 plan Step 13; BR3.4, BR6.10, NFR3.9).

Each kind has one typed schema. A schema holds only registered fields, and every value
has a fixed form: identifiers, states, times, reason keys, digests, counts, opaque
references and receipt references. No field takes free text, so a record can carry no
private text, email address, title or content (BR3.4, NFR3.9). A value that is not of
its field's form is refused, and so is a field the schema does not name.

Entries are events. A keyed kind (an entity) is appended as a new version of the whole
record (BR6.10); its current state is its latest version and its revision is the
number of versions, kept in memory and rebuilt from the chain on open (performance-
design § 4). The file layer's recovery records (`ledger.adopted`, `ledger.discarded`)
and a repair (`ledger.repaired`) are unkeyed events.

The kinds follow entities.md: ServiceIncident, RecoveryRequest, BackupSet,
RestoreVerification, RestoreTombstone, LedgerCopy, RetainedCopy, ProviderActivation,
ConsumerInventory, CutoverRecord, MaintainerApproval, MigrationRun, MisfitRecord,
MisfitDecision, ParityReport (a reference to the full report file), EmailAllowance
(reserve, release and settle as one reservation's versions), ReleaseRecord
(cicd-pipeline § 5.1 step 12) and ReceiptFacts. LifecycleEvidence holds
ServiceOperations' own lifecycle evidence (Step 17), which no other kind could hold.
Where a machine is defined (functional-spec.md § State machine), the schema carries its
state transitions; guards stay with the component that owns the machine. See the plan:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from uuid import UUID

ZERO = "0" * 64


class RecordRefused(ValueError):
    """A record outside its schema. The message is a fixed category and, at most, a
    registered field name; it never repeats a value."""

    def __init__(self, category: str, field_name: str | None = None):
        super().__init__(category if field_name is None else f"{category}:{field_name}")
        self.category, self.field_name = category, field_name


# --- Field forms --------------------------------------------------------------------------


class Form:
    def check(self, value: object) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True)
class Pattern(Form):
    expression: str

    def check(self, value: object) -> bool:
        return isinstance(value, str) and re.fullmatch(self.expression, value) is not None


class IdForm(Form):
    """A canonical, lower-case UUID."""

    def check(self, value: object) -> bool:
        if not isinstance(value, str) or len(value) != 36:
            return False
        try:
            return str(UUID(value)) == value
        except ValueError:
            return False


class TimeForm(Form):
    """One fixed timestamp form: UTC, milliseconds, `Z` (the ledger's own)."""

    SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")

    def check(self, value: object) -> bool:
        if not isinstance(value, str) or self.SHAPE.fullmatch(value) is None:
            return False
        try:
            dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return True


class CountForm(Form):
    def __init__(self, minimum: int = 0, maximum: int = 2**53):
        self.minimum, self.maximum = minimum, maximum

    def check(self, value: object) -> bool:
        return type(value) is int and self.minimum <= value <= self.maximum


class BoolForm(Form):
    def check(self, value: object) -> bool:
        return type(value) is bool


@dataclass(frozen=True)
class Enum(Form):
    values: tuple[str, ...]

    def check(self, value: object) -> bool:
        return isinstance(value, str) and value in self.values


@dataclass(frozen=True)
class ListOf(Form):
    item: Form
    maximum: int
    minimum: int = 0
    unique: bool = True

    def check(self, value: object) -> bool:
        if not isinstance(value, list) or not self.minimum <= len(value) <= self.maximum:
            return False
        if not all(self.item.check(entry) for entry in value):
            return False
        if self.unique:
            keys = [repr(entry) for entry in value]
            return len(keys) == len(set(keys))
        return True


@dataclass(frozen=True)
class MapOf(Form):
    key: Form
    value: Form
    maximum: int

    def check(self, value: object) -> bool:
        return (
            isinstance(value, dict)
            and len(value) <= self.maximum
            and all(self.key.check(k) and self.value.check(v) for k, v in value.items())
        )


@dataclass(frozen=True)
class ObjectOf(Form):
    """A nested object with its own registered fields."""

    fields: Mapping[str, Form]
    required: frozenset[str]

    def check(self, value: object) -> bool:
        if not isinstance(value, dict) or not set(value) <= set(self.fields):
            return False
        if not self.required <= set(value):
            return False
        return all(self.fields[name].check(item) for name, item in value.items())


@dataclass(frozen=True)
class NullOr(Form):
    """A value of its form, or null (a retired group whose volume is not known)."""

    form: Form

    def check(self, value: object) -> bool:
        return value is None or self.form.check(value)


ID = IdForm()
TIME = TimeForm()
COUNT = CountForm()
POSITIVE = CountForm(1)
BOOL = BoolForm()
DIGEST = Pattern(r"[0-9a-f]{64}")
# A registered key: reason keys, limitation keys, capability and operation names.
KEY = Pattern(r"[a-z][a-z0-9.-]{0,63}")
# An opaque reference: no space, no `@`, no `..` segment, so no address, name or text.
REF = Pattern(r"(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9._:/-]{0,159}")
ROUTE = Pattern(r"/[A-Za-z0-9/_{}.-]{0,200}")
TAG = Pattern(r"v\d{1,4}\.\d{1,4}\.\d{1,4}")
COMMIT = Pattern(r"[0-9a-f]{40}")
DAY = Pattern(r"\d{4}-\d{2}-\d{2}")
MONTH = Pattern(r"\d{4}-\d{2}")
ENVIRONMENT = Enum(("rehearsal", "live"))


# --- Schemas ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Schema:
    """One record kind. `key` names the identity fields of a keyed kind (an entity);
    an unkeyed kind is a pure event. `transitions` maps a state (None for a new entity)
    to the states it may move to. `immutable` fields never change once written;
    `extend_only` times may only move later; `receipts` names the fields that cite
    PlatformControl receipts (a receipt-bearing kind)."""

    kind: str
    entity: str
    fields: Mapping[str, Form]
    required: frozenset[str]
    key: tuple[str, ...] = ()
    transitions: Mapping[str | None, frozenset[str]] | None = None
    immutable: frozenset[str] = frozenset()
    extend_only: frozenset[str] = frozenset()
    receipts: tuple[str, ...] = ()
    max_versions: int = 10_000
    rules: tuple = field(default=())

    @property
    def keyed(self) -> bool:
        return bool(self.key)

    def key_of(self, record: Mapping) -> tuple:
        return tuple(record[name] for name in self.key)

    def validate(self, record: object) -> dict:
        """The record's structure: only registered fields, each of its form, every
        required field present, and each rule of the kind holding."""
        if not isinstance(record, dict):
            raise RecordRefused("record-not-a-mapping")
        for name in record:
            if name not in self.fields:
                raise RecordRefused("unregistered-field")
        for name in sorted(self.required):
            if name not in record:
                raise RecordRefused("required-field-missing", name)
        for name, value in record.items():
            if not self.fields[name].check(value):
                raise RecordRefused("field-form", name)
        for rule in self.rules:
            failure = rule(record)
            if failure is not None:
                raise RecordRefused("rule", failure)
        return record

    def validate_version(self, current: Mapping | None, record: Mapping) -> None:
        """A new version against the entity's current one."""
        if self.transitions is not None:
            before = None if current is None else current.get("state")
            allowed = self.transitions.get(before, frozenset())
            if record.get("state") not in allowed:
                raise RecordRefused("state-transition", "state")
        if current is None:
            return
        for name in sorted(self.immutable):
            if current.get(name) != record.get(name):
                raise RecordRefused("immutable-field", name)
        for name in sorted(self.extend_only):
            if name in current and (name not in record or record[name] < current[name]):
                raise RecordRefused("extend-only-field", name)

    def cited_receipts(self, record: Mapping) -> tuple[str, ...]:
        cited: list[str] = []
        for name in self.receipts:
            value = record.get(name)
            if isinstance(value, str):
                cited.append(value)
            elif isinstance(value, list):
                cited.extend(item for item in value if isinstance(item, str))
        return tuple(dict.fromkeys(cited))


def _states(machine: Mapping[str | None, Iterable[str]]) -> dict[str | None, frozenset[str]]:
    return {state: frozenset(nexts) for state, nexts in machine.items()}


def _together(names: tuple[str, ...]):
    """The named fields appear all together or not at all."""

    def rule(record: Mapping) -> str | None:
        present = [name in record for name in names]
        return None if all(present) or not any(present) else f"{names[0]}-fields-together"

    return rule


def _exactly_when(field_name: str, value: object, names: tuple[str, ...]):
    """`names` are present exactly when `field_name` equals `value`."""

    def rule(record: Mapping) -> str | None:
        expected = record.get(field_name) == value
        for name in names:
            if (name in record) != expected:
                return name
        return None

    return rule


INCIDENT_OPENED_BY = (
    "tolerance-exceeded", "job-failure-correlated", "switch-aborted", "rollback-copy-pending",
    "operator",
    # The ledger's own damage, recorded by its repair with the time it was first found
    # (your decision of 2026-10-22, BR6.10).
    "ledger-damaged",
    # A worker item whose processing failed, set aside for its turn (your decision of
    # 2026-10-23, "Set it aside, record it").
    "worker-item-set-aside",
)
INCIDENT_RESOLUTIONS = (
    "capability-available", "abort-reviewed", "rollback-copy-settled", "environment-stopped",
)
SERVICE_INCIDENT = Schema(
    kind="service-incident", entity="ServiceIncident", key=("incidentId",),
    fields={
        "incidentId": ID, "environment": ENVIRONMENT, "revision": POSITIVE,
        "capabilities": ListOf(KEY, 8, 1), "correlationIds": ListOf(REF, 32),
        "state": Enum(("open", "investigating", "recovering", "resolved")),
        "openedAt": TIME, "openedBy": Enum(INCIDENT_OPENED_BY), "diagnosisKey": KEY,
        "recoveryRequestIds": ListOf(ID, 16), "evidenceRefs": ListOf(REF, 16),
        "resolutionKind": Enum(INCIDENT_RESOLUTIONS), "resolvedAt": TIME,
    },
    required=frozenset({
        "incidentId", "environment", "revision", "capabilities", "correlationIds", "state",
        "openedAt", "openedBy", "recoveryRequestIds", "evidenceRefs",
    }),
    transitions=_states({
        None: ("open",),
        "open": ("open", "investigating", "resolved"),
        "investigating": ("investigating", "recovering", "resolved"),
        "recovering": ("recovering", "investigating", "resolved"),
    }),
    immutable=frozenset({"incidentId", "environment", "openedAt", "openedBy"}),
    rules=(_exactly_when("state", "resolved", ("resolutionKind", "resolvedAt")),),
)

RECOVERY_OPERATIONS = ("backup.create", "restore.verify", "restore.production")
RECOVERY_STATES = (
    "requested", "awaiting-operator", "running", "verifying", "post-restore-pending", "held",
    "succeeded", "failed", "unknown", "cancelled", "refused", "expired",
)
ACTIVE_RECOVERY_STATES = frozenset(
    {"awaiting-operator", "running", "verifying", "unknown", "post-restore-pending", "held"}
)


def _schedule_operations(record: Mapping) -> str | None:
    if record.get("origin") == "schedule" and record.get("operation") == "restore.production":
        return "operation"
    if record.get("origin") == "administrator" and (
        "requestedBy" not in record or "mfaVerifiedAt" not in record
    ):
        return "requestedBy"
    return None


RECOVERY_REQUEST = Schema(
    kind="recovery-request", entity="RecoveryRequest", key=("recoveryRequestId",),
    fields={
        "recoveryRequestId": ID, "revision": POSITIVE, "environment": ENVIRONMENT,
        "origin": Enum(("administrator", "schedule")), "incidentId": ID,
        "operation": Enum(RECOVERY_OPERATIONS), "targetId": REF, "expectedRevision": COUNT,
        "requestedBy": ID, "mfaVerifiedAt": TIME, "submissionId": ID, "idempotencyKey": DIGEST,
        "approvalId": ID, "preRestoreBackupId": ID, "postRestoreBackupId": ID,
        "successorRequestId": ID, "predecessorRequestId": ID, "abandonmentApprovalId": ID,
        "abandonmentRecreateReceiptRef": ID, "abandonedAt": TIME, "lossReportRef": REF,
        "startAuthorizedAt": TIME, "state": Enum(RECOVERY_STATES), "operatorReceiptRef": ID,
        "evidenceRefs": ListOf(REF, 16), "createdAt": TIME, "updatedAt": TIME,
    },
    required=frozenset({
        "recoveryRequestId", "revision", "environment", "origin", "operation", "targetId",
        "expectedRevision", "submissionId", "idempotencyKey", "state", "evidenceRefs",
        "createdAt", "updatedAt",
    }),
    transitions=_states({
        None: ("requested",),
        "requested": ("requested", "awaiting-operator", "refused", "expired", "cancelled"),
        "awaiting-operator": (
            "awaiting-operator", "running", "cancelled", "refused", "expired",
        ),
        "running": ("running", "verifying", "failed", "held", "unknown"),
        "verifying": (
            "verifying", "succeeded", "post-restore-pending", "failed", "unknown",
        ),
        "unknown": ("unknown", "verifying", "post-restore-pending", "held", "failed"),
        "post-restore-pending": ("post-restore-pending", "verifying"),
        "held": ("held", "failed", "unknown"),
    }),
    immutable=frozenset({
        "recoveryRequestId", "environment", "origin", "operation", "targetId",
        "expectedRevision", "requestedBy", "submissionId", "idempotencyKey", "createdAt",
    }),
    receipts=("operatorReceiptRef", "abandonmentRecreateReceiptRef"),
    rules=(_schedule_operations,),
)

BACKUP_SET = Schema(
    kind="backup-set", entity="BackupSet", key=("backupId",),
    fields={
        "backupId": ID, "environment": ENVIRONMENT, "revision": POSITIVE,
        # `pre-release`: an install's backup after writes stop (cicd-pipeline § 5.1 step 6).
        # `volume-retirement`: the set a retirement takes on the replacement (NFR7.11,
        # U8 plan Step 64(h)).
        "trigger": Enum(("scheduled", "requested", "pre-restore", "post-restore", "first-live",
                         "pre-release", "volume-retirement")),
        "recoveryRequestId": ID, "sourceCopyId": ID, "takenAt": TIME, "checksum": DIGEST,
        "sizeBytes": COUNT, "sourceDatabaseBytes": COUNT, "location": REF,
        "databaseIncarnation": REF, "stagingLocation": REF, "stagingRemovedAt": TIME,
        "retainUntil": TIME, "integrity": Enum(("unchecked", "passed", "failed")),
        "operatorReceiptRef": ID, "heldByFloorSince": TIME, "disposalPendingSince": TIME,
        # The latest failed disposal attempt (U8 plan Step 58(h)); `disposalPendingSince`
        # keeps the first.
        "lastDisposalFailedAt": TIME,
        "disposedAt": TIME, "retiredWithVolumeAt": TIME,
        # The retirement decision's receipt on a version closed with its volume (L1-18).
        "retirementReceiptRef": ID,
    },
    required=frozenset({
        "backupId", "environment", "revision", "trigger", "takenAt", "checksum", "sizeBytes",
        "sourceDatabaseBytes", "location", "databaseIncarnation", "stagingLocation",
        "retainUntil", "integrity", "operatorReceiptRef",
    }),
    immutable=frozenset({
        "backupId", "environment", "revision", "trigger", "takenAt", "checksum", "sizeBytes",
        "sourceDatabaseBytes", "location", "databaseIncarnation", "stagingLocation",
        "operatorReceiptRef",
    }),
    extend_only=frozenset({"retainUntil"}),
    receipts=("operatorReceiptRef", "retirementReceiptRef"),
)


def _verified_result(record: Mapping) -> str | None:
    if record.get("result") == "verified" and not (
        record.get("integrity") == "passed"
        and record.get("erasedOwnersSurviving") == 0
        and "scratchRemovedAt" in record
    ):
        return "result"
    return None


RESTORE_VERIFICATION = Schema(
    kind="restore-verification", entity="RestoreVerification", key=("verificationId",),
    fields={
        "verificationId": ID, "environment": ENVIRONMENT, "backupId": ID, "startedAt": TIME,
        "finishedAt": TIME, "registerHeadSequence": COUNT, "registerHeadDigest": DIGEST,
        "integrity": Enum(("passed", "failed")), "erasedOwnersSurviving": COUNT,
        "result": Enum(("verified", "failed")), "evidenceRef": REF, "scratchRemovedAt": TIME,
        # U8 plan Step 60(d): the agent's measured HNSW rebuild time and its projection to
        # the 8 GiB footprint budget, `ceil(hnswRebuildSeconds x footprint_budget_bytes /
        # sourceDatabaseBytes)`; a set of 0 bytes records the time and no projection.
        "hnswRebuildSeconds": COUNT, "hnswProjectedSeconds": COUNT,
    },
    required=frozenset({
        "verificationId", "environment", "backupId", "startedAt", "registerHeadSequence",
        "registerHeadDigest", "evidenceRef",
    }),
    immutable=frozenset({
        "verificationId", "environment", "backupId", "startedAt", "registerHeadSequence",
        "registerHeadDigest",
    }),
    rules=(_verified_result,),
)

RESTORE_TOMBSTONE = Schema(
    kind="restore-tombstone", entity="RestoreTombstone", key=("lifecycleRequestId",),
    fields={
        "sequence": POSITIVE, "accountId": ID, "lifecycleRequestId": ID, "appendedAt": TIME,
        "previousDigest": DIGEST, "digest": DIGEST,
    },
    required=frozenset({
        "sequence", "accountId", "lifecycleRequestId", "appendedAt", "previousDigest", "digest",
    }),
    max_versions=1,
)

LEDGER_COPY = Schema(
    kind="ledger-copy", entity="LedgerCopy", key=("ledgerCopyId",),
    fields={
        "ledgerCopyId": ID, "backupId": ID, "takenAt": TIME, "location": REF,
        "stagingLocation": REF, "stagingRemovedAt": TIME, "digest": DIGEST,
        "headSequence": COUNT, "headDigest": DIGEST, "verifiedAt": TIME, "retainUntil": TIME,
        "heldByFloorSince": TIME, "disposalPendingSince": TIME, "disposedAt": TIME,
        "retiredWithVolumeAt": TIME, "operatorReceiptRef": ID,
        # The latest failed disposal attempt (Step 58(h)).
        "lastDisposalFailedAt": TIME,
        # The retirement decision's receipt on a version closed with its volume (L1-18).
        "retirementReceiptRef": ID,
    },
    required=frozenset({
        "ledgerCopyId", "takenAt", "location", "stagingLocation", "digest", "headSequence",
        "headDigest", "retainUntil", "operatorReceiptRef",
    }),
    immutable=frozenset({
        "ledgerCopyId", "backupId", "takenAt", "location", "stagingLocation", "digest",
        "headSequence", "headDigest", "operatorReceiptRef",
    }),
    extend_only=frozenset({"retainUntil"}),
    receipts=("operatorReceiptRef", "retirementReceiptRef"),
)

DISPOSAL_REFS = ("disposalReceiptRef", "disposalAgentRef", "disposalVerificationRef")
RETAINED_COPY_KINDS = (
    "dry-run-snapshot", "rehearsal-database", "import-database", "scratch-restore",
    "v1-final-snapshot", "v1-stores", "rolled-back-v2-database",
)
RETAINED_COPY = Schema(
    kind="retained-copy", entity="RetainedCopy", key=("copyId",),
    fields={
        "copyId": ID, "kind": Enum(RETAINED_COPY_KINDS), "sourceRef": REF, "createdAt": TIME,
        "checksum": DIGEST, "completedAt": TIME, "sourceDatabaseBytes": COUNT,
        "locations": ListOf(REF, 16, 1), "stagingLocation": REF, "stagingRemovedAt": TIME,
        "disposeAfter": TIME, "disposalApprovalId": ID, "disposalPendingSince": TIME,
        "disposedAt": TIME, "disposalReceiptRef": ID, "retiredWithVolumeAt": TIME,
        "returnedToServiceAt": TIME,
        # The latest failed disposal attempt (Step 58(h)).
        "lastDisposalFailedAt": TIME,
        # The backup agent's own receipt for a file it deleted on its catalogue's terms
        # in the unattended disposal pass (Workflow 19 step 9; U8 plan Step 33): the
        # catalogue path it reported disposed. A disposal carries exactly one receipt.
        "disposalAgentRef": REF,
        # v1's stores, deleted by the operator by hand: the evidence of the read-only
        # check that each location is gone (the person's decision of 2026-10-22, BR9.17).
        "disposalCheckRef": REF,
        # A scratch database dropped through the scheduler's database login, with no
        # PlatformControl receipt to cite: its verification (U8 plan Step 64(d)).
        "disposalVerificationRef": REF,
        # A decided date re-dated by your decision: that decision's receipt (L1-3).
        "redateReceiptRef": ID,
        # A snapshot's size by part, outside its parts file and digest (NFR7.14).
        "partSizes": MapOf(KEY, COUNT, 16),
        # The retirement decision's receipt on a version closed with its volume (L1-18).
        "retirementReceiptRef": ID,
    },
    required=frozenset({"copyId", "kind", "sourceRef", "createdAt", "locations", "disposeAfter"}),
    immutable=frozenset({"copyId", "kind", "sourceRef", "createdAt", "locations"}),
    receipts=("disposalReceiptRef", "redateReceiptRef", "retirementReceiptRef"),
    rules=(
        lambda record: "returnedToServiceAt"
        if "returnedToServiceAt" in record and record.get("kind") != "v1-stores" else None,
        # A disposal carries exactly one of its three references (Step 64(d)).
        lambda record: "disposalReceiptRef"
        if ("disposedAt" in record) != (sum(
            name in record for name in DISPOSAL_REFS) == 1)
        or sum(name in record for name in DISPOSAL_REFS) > 1 else None,
        lambda record: "disposalCheckRef"
        if "disposalCheckRef" in record and (
            record.get("kind") != "v1-stores" or "disposalReceiptRef" not in record
        ) else None,
    ),
)

PROVIDER_ACTIVATION = Schema(
    kind="provider-activation", entity="ProviderActivation", key=("provider",),
    fields={
        "provider": Enum(("google", "orcid", "resend", "models", "notion")), "outward": BOOL,
        "state": Enum(("unconfigured", "held", "active", "degraded", "unavailable")),
        "approvalContentHash": DIGEST, "approvalId": ID, "approvedAt": TIME,
        "allowanceRemaining": MapOf(Enum(("daily", "monthly")), COUNT, 2),
        "limitations": ListOf(KEY, 16),
    },
    required=frozenset({"provider", "outward", "state", "limitations"}),
    immutable=frozenset({"provider", "outward"}),
)

CONSUMER = ObjectOf(
    fields={
        "clientRef": REF, "routesUsed": ListOf(ROUTE, 64),
        "source": Enum(("observed", "known")),
        "disposition": Enum(("moves-with-v2", "retired-with-v1", "informed", "accepted-to-break")),
        "approvalId": ID,
        "requests": COUNT,
    },
    required=frozenset({"clientRef", "routesUsed", "source"}),
)
# v1's traffic from your Cloudflare export (the person's decision of 2026-10-24,
# "Cloudflare's numbers"): the export's request count over the window and its busiest
# interval, whose rate the install's performance phase compares the test's pace against.
INVENTORY_COUNTS = ("source", "requests", "peakRequests", "peakAt", "intervalSeconds")
CONSUMER_INVENTORY = Schema(
    kind="consumer-inventory", entity="ConsumerInventory", key=("inventoryId",),
    fields={
        "inventoryId": ID, "observedFrom": TIME, "observedUntil": TIME,
        "consumers": ListOf(CONSUMER, 256), "complete": BOOL,
        "source": Enum(("cloudflare-export",)), "requests": COUNT, "peakRequests": COUNT,
        "peakAt": TIME, "intervalSeconds": COUNT,
    },
    required=frozenset({"inventoryId", "observedFrom", "observedUntil", "consumers", "complete"}),
    immutable=frozenset({"inventoryId", "observedFrom", "observedUntil", *INVENTORY_COUNTS}),
    rules=(_together(INVENTORY_COUNTS),),
)

CUTOVER_STATES = (
    "preparing", "rehearsing", "ready-to-switch", "switching", "aborting", "switched",
    "rolling-back", "rolled-back", "settled",
)
CUTOVER_RECORD = Schema(
    kind="cutover-record", entity="CutoverRecord", key=("cutoverId",),
    fields={
        "cutoverId": ID, "releaseTag": TAG, "state": Enum(CUTOVER_STATES),
        "soakStartedAt": TIME, "soakPeriodSeconds": POSITIVE, "soakClean": BOOL,
        "verificationRunId": ID, "acceptedDryRunId": ID, "consumerInventoryId": ID,
        "v1CheckoutCommit": COMMIT, "v1RestartRehearsedAt": TIME, "finalSnapshotCopyId": ID,
        "v1StoresCopyId": ID, "rollbackV1ServingAt": TIME, "rollbackCopyPendingSince": TIME,
        "rollbackCopyIncidentId": ID, "abortIncidentId": ID, "finalRunId": ID,
        "switchStartedAt": TIME, "switchTimeBoundSeconds": POSITIVE, "admissionOpenedAt": TIME,
        "rollbackWindowSeconds": POSITIVE, "effectReceipts": ListOf(ID, 512),
        "approvals": ListOf(ID, 512),
        # U8 plan Step 70(a)-(b) (L1-3, L1-21): the abort's start, the switch's one check
        # instant and the settlement's move.
        "abortStartedAt": TIME, "switchCheckedAt": TIME, "settledAt": TIME,
    },
    required=frozenset({
        "cutoverId", "releaseTag", "state", "soakPeriodSeconds", "soakClean",
        "switchTimeBoundSeconds", "rollbackWindowSeconds", "effectReceipts", "approvals",
    }),
    transitions=_states({
        None: ("preparing",),
        "preparing": ("preparing", "rehearsing"),
        "rehearsing": ("rehearsing", "ready-to-switch", "preparing"),
        "ready-to-switch": ("ready-to-switch", "rehearsing", "switching", "preparing"),
        "switching": ("switching", "switched", "aborting"),
        "aborting": ("aborting", "rehearsing"),
        "switched": ("switched", "rolling-back", "settled"),
        "rolling-back": ("rolling-back", "rolled-back", "switched"),
        "rolled-back": ("rolled-back", "rehearsing"),
    }),
    immutable=frozenset({"cutoverId"}),
    receipts=("effectReceipts",),
)

APPROVAL_STEPS = (
    "dry-run-go-ahead", "dry-run-report", "misfit-decision", "consumer-disposition",
    "v1-restart-rehearsal", "switch-start", "final-report", "provider-sign-in",
    "provider-first-effect", "admission-opening", "abort-review", "rollback", "rollback-cancel",
    "rollback-copy-waiver", "settlement", "production-restore", "restore-abandonment",
    "disposal-date", "backup-volume-retirement",
)
MAINTAINER_APPROVAL = Schema(
    kind="maintainer-approval", entity="MaintainerApproval", key=("approvalId",),
    fields={
        "approvalId": ID, "step": Enum(APPROVAL_STEPS), "subjectRef": REF,
        "subjectDigest": DIGEST, "decision": Enum(("approved", "declined")),
        "recordedAt": TIME, "operatorReceiptRef": ID,
    },
    required=frozenset({
        "approvalId", "step", "subjectRef", "subjectDigest", "decision", "recordedAt",
        "operatorReceiptRef",
    }),
    receipts=("operatorReceiptRef",),
    max_versions=1,
)

MIGRATION_PHASES = ("preparing", "copying", "importing", "verifying")
MIGRATION_RUN = Schema(
    kind="migration-run", entity="MigrationRun", key=("runId",),
    fields={
        "runId": ID, "kind": Enum(("dry", "final")), "snapshotCopyId": ID,
        "target": Enum(("rehearsal", "production")), "targetCopyId": ID, "toolCommit": COMMIT,
        "decisionsDigest": DIGEST,
        "state": Enum((*MIGRATION_PHASES, "reported", "accepted", "rejected", "failed",
                       "interrupted")),
        "interruptedPhase": Enum(MIGRATION_PHASES), "startedAt": TIME, "finishedAt": TIME,
        "acceptedAt": TIME, "reportApprovalId": ID,
        # Each phase's last start and seconds, and the run's duration from its snapshot's
        # start to its report (NFR8.8, U8 plan Step 68(g), L1-59); none is required, so a
        # run recorded before them stays valid.
        "phaseStartedAt": MapOf(Enum((*MIGRATION_PHASES, "reported")), TIME, 5),
        "phaseSeconds": MapOf(Enum(MIGRATION_PHASES), COUNT, 4),
        "snapshotStartedAt": TIME, "reportedAt": TIME,
        "durationSeconds": COUNT, "interruptions": COUNT,
    },
    required=frozenset({"runId", "kind", "target", "toolCommit", "decisionsDigest", "state",
                        "startedAt"}),
    transitions=_states({
        None: ("preparing",),
        "preparing": ("preparing", "copying", "failed", "interrupted"),
        "copying": ("copying", "importing", "failed", "interrupted"),
        "importing": ("importing", "verifying", "failed", "interrupted"),
        "verifying": ("verifying", "reported", "failed", "interrupted"),
        # A final run reported but not yet accepted ends failed when the switch aborts
        # (BR9.5, U8 plan Step 33).
        "reported": ("accepted", "rejected", "failed"),
        "interrupted": (*MIGRATION_PHASES, "failed"),
    }),
    immutable=frozenset({"runId", "kind", "target", "toolCommit", "decisionsDigest",
                         "startedAt"}),
    rules=(_exactly_when("state", "interrupted", ("interruptedPhase",)),),
)

PARITY_KINDS = (
    "account", "identity-link", "preferences", "paper", "paper-content", "paper-embedding",
    "paper-figure", "saved-paper", "followed-topic", "digest-settings", "glossary",
    "saved-search", "search-history", "behavior-event", "plan-record", "private-upload",
    "research-history", "novelty-history", "summary",
)
MISFIT_REASONS = (
    "not-in-scope", "no-v2-home", "required-field-without-source", "closed-in-v1",
    "unverified-in-v1", "locked-in-v1", "no-email", "email-case-conflict", "unconfirmed-link",
    "duplicate-provider-link", "dependency-not-migrated", "ineligible-in-v2", "exceeds-v2-limit",
    "content-shape-unconvertible", "embedding-provenance-unproven", "duplicate-by-version",
    # CorpusContent's refusals that are yours to decide, with no proposal (U8 plan Step
    # 68(h), L1-75 and its sixth addition).
    "refused-by-database-time-limits", "paper-metadata-changed", "version-content-changed",
)
MISFIT_RECORD = Schema(
    kind="misfit-record", entity="MisfitRecord",
    key=("runId", "kind", "sourceId", "reasonKey"),
    fields={
        "runId": ID, "kind": Enum(PARITY_KINDS), "sourceId": REF,
        "reasonKey": Enum(MISFIT_REASONS), "newInFinal": BOOL,
    },
    required=frozenset({"runId", "kind", "sourceId", "reasonKey", "newInFinal"}),
    max_versions=1,
)
MISFIT_DECISION = Schema(
    kind="misfit-decision", entity="MisfitDecision", key=("kind", "reasonKey"),
    fields={
        "kind": Enum(PARITY_KINDS), "reasonKey": Enum(MISFIT_REASONS),
        "decision": Enum(("map", "archive-only", "drop")), "mappingRule": KEY,
        "decidedAt": TIME, "approvalId": ID, "frozen": BOOL,
    },
    required=frozenset({"kind", "reasonKey", "decision", "decidedAt", "approvalId", "frozen"}),
    immutable=frozenset({"kind", "reasonKey"}),
    rules=(_exactly_when("decision", "map", ("mappingRule",)),),
)
PARITY_REPORT = Schema(
    kind="parity-report", entity="ParityReport", key=("runId",),
    fields={
        "runId": ID, "reportRef": REF, "reportDigest": DIGEST, "kinds": COUNT,
        "reconciles": BOOL, "recordedAt": TIME,
    },
    required=frozenset({"runId", "reportRef", "reportDigest", "kinds", "reconciles",
                        "recordedAt"}),
    max_versions=1,
)

EMAIL_ALLOWANCE = Schema(
    kind="email-allowance", entity="EmailAllowance", key=("reservationId",),
    fields={
        "reservationId": ID, "mailKind": Enum(("digest", "account")), "messageKey": ID,
        "day": DAY, "month": MONTH, "state": Enum(("reserved", "released", "settled")),
        "reservedAt": TIME, "updatedAt": TIME,
    },
    required=frozenset({"reservationId", "mailKind", "messageKey", "day", "month", "state",
                        "reservedAt", "updatedAt"}),
    transitions=_states({
        None: ("reserved",),
        "reserved": ("released", "settled"),
        "released": ("reserved",),
    }),
    immutable=frozenset({"reservationId", "mailKind", "messageKey"}),
)

# cicd-pipeline § 5.1 step 12 and § 6 (U8 plan Step 37): an install is `installing` from
# its preflight until it ends, which holds the live environment's exclusion (BR4.4); it
# ends `installed`, `failed` (a migration or an apply failed, the current release kept)
# or `switched-back` (not ready within 10 minutes); a later rollback is `rolling-back`
# while it runs (holding the same exclusion), then `rolled-back`, or `installed` again when
# it stopped before the links were switched.
RELEASE_STATES = ("installing", "installed", "failed", "switched-back", "rolling-back",
                  "rolled-back")
RELEASE_RECORD = Schema(
    kind="release-record", entity="ReleaseRecord", key=("releaseTag",),
    fields={
        "releaseTag": TAG, "releaseCommit": COMMIT, "previousTag": TAG,
        "state": Enum(RELEASE_STATES), "installedAt": TIME, "updatedAt": TIME,
        "receiptRef": ID, "backupId": ID, "arrangementVersion": POSITIVE,
        "verificationRunRef": REF, "readyWaitSeconds": COUNT, "reasonKey": KEY,
        "stepMilliseconds": MapOf(KEY, COUNT, 16),
        # A release installed while v2 was kept stopped waits for its probe journey until
        # the soak starts (the person's decision of 2026-10-25, "Probe it when the soak
        # starts"): `probePending`, then `probedAt` once it passed, or `switched-back`.
        "probePending": BOOL, "probedAt": TIME,
        # An unprobed release a later install moved to `release-previous`: no longer
        # waiting while another runs, and waiting again if a release rollback relinks it
        # (review finding, Minor, R13).
        "probeSuperseded": BOOL,
        # The switch back's own readiness wait, beside the install's (`readyWaitSeconds`):
        # a previous release not ready within its wait fails the switch back (review
        # finding, Major, R13).
        "switchBackWaitSeconds": COUNT,
        # A failed probe's switch back that left v2 stopped on the kept release
        # (`keptTag`): `docsuri-release verify` on that tag starts v2 for the soak, and
        # the mark is cleared once it did (the person's decision of 2026-10-26, "Only for
        # a pending probe").
        "v2Stopped": BOOL, "keptTag": TAG,
        # The first step of a switch back that did not complete (a stop that failed, the
        # kept release closed), kept beside `reasonKey` and cleared with it (review
        # finding, Major, R20).
        "switchBackStep": KEY,
    },
    required=frozenset({"releaseTag", "releaseCommit", "state", "installedAt", "updatedAt"}),
    transitions=_states({
        None: ("installing", "installed"),
        "installing": ("installing", "installed", "failed", "switched-back"),
        # `installed` again records a passed probe; `switched-back` a failed one.
        "installed": ("rolling-back", "rolled-back", "installed", "switched-back"),
        "rolling-back": ("rolled-back", "installed"),
        # The same state again: `docsuri-release recover` completing what a run left
        # (its reason key cleared; the review's findings of 2026-10-26).
        "failed": ("installing", "failed"),
        "switched-back": ("installing", "switched-back"),
        "rolled-back": ("installing", "rolled-back"),
    }),
    immutable=frozenset({"releaseTag", "releaseCommit", "installedAt"}),
    receipts=("receiptRef",),
)

EVIDENCE_ITEMS = 256
RECEIPT_OUTCOMES = ("accepted", "running", "succeeded", "failed", "unknown")
RECEIPT_FACTS = Schema(
    kind="receipt-facts", entity="ReceiptFacts", key=("receiptId",),
    fields={
        "receiptId": ID, "operationId": ID, "operation": KEY, "targetId": REF,
        "inputHash": DIGEST, "outcome": Enum(RECEIPT_OUTCOMES), "confirmedAt": TIME,
    },
    required=frozenset({"receiptId", "operationId", "operation", "targetId", "inputHash",
                        "outcome", "confirmedAt"}),
    immutable=frozenset({"receiptId", "operationId", "operation", "targetId", "inputHash"}),
)

LIFECYCLE_EVIDENCE = Schema(
    kind="lifecycle-evidence", entity="LifecycleEvidence", key=("requestId", "scope"),
    fields={
        "requestId": ID, "scope": Enum(("backups", "restore_enforcement")),
        "action": Enum(("withdraw", "erase", "reactivate")),
        "state": Enum(("waiting", "complete")), "reasonKey": KEY, "evidenceRef": ID,
        "setsCounted": COUNT, "copiesCounted": COUNT, "retiredCounted": COUNT,
        "latestGoneAt": TIME, "tombstoneSequence": POSITIVE, "registerHeadSequence": COUNT,
        "registerHeadDigest": DIGEST, "verificationId": ID, "recordedAt": TIME,
        # The backups evidence names each item (NFR3.14, L1-51; U8 plan Step 64(f)), at
        # most EVIDENCE_ITEMS each, which keeps the record within the entry bound.
        "undisposed": ListOf(ObjectOf({"recordId": REF, "kind": KEY, "goneAt": TIME},
                                      frozenset({"recordId", "kind", "goneAt"})),
                             EVIDENCE_ITEMS, unique=False),
        "retired": ListOf(ObjectOf({"volume": NullOr(REF), "retiredAt": TIME, "count": POSITIVE},
                                   frozenset({"volume", "retiredAt", "count"})),
                          EVIDENCE_ITEMS, unique=False),
        "unrecordedCounted": COUNT, "agentStatusRecorded": BOOL,
        # The covering verification's times, and its late start (L1-42).
        "verificationStartedAt": TIME, "verificationFinishedAt": TIME,
        "verificationStartLate": BOOL,
    },
    required=frozenset({"requestId", "scope", "action", "state", "reasonKey", "recordedAt"}),
    transitions=_states({None: ("waiting", "complete"), "waiting": ("waiting", "complete")}),
    immutable=frozenset({"requestId", "scope", "action"}),
    rules=(_exactly_when("state", "complete", ("evidenceRef",)),),
)

# The file layer's recovery records and a repair: unkeyed events.
LEDGER_ADOPTED = Schema(
    kind="ledger.adopted", entity="LedgerRecovery",
    fields={"from": COUNT, "to": COUNT}, required=frozenset({"from", "to"}),
)
LEDGER_DISCARDED = Schema(
    kind="ledger.discarded", entity="LedgerRecovery",
    fields={"bytes": COUNT, "atCount": COUNT}, required=frozenset({"bytes", "atCount"}),
)
LEDGER_REPAIRED = Schema(
    kind="ledger.repaired", entity="LedgerRepair",
    fields={
        "copySha256": DIGEST, "copyCount": COUNT, "copyHead": DIGEST, "asideRef": REF,
        "damage": KEY,
    },
    required=frozenset({"copySha256", "copyCount", "copyHead", "asideRef", "damage"}),
)

SCHEMAS: dict[str, Schema] = {
    schema.kind: schema
    for schema in (
        SERVICE_INCIDENT, RECOVERY_REQUEST, BACKUP_SET, RESTORE_VERIFICATION, RESTORE_TOMBSTONE,
        LEDGER_COPY, RETAINED_COPY, PROVIDER_ACTIVATION, CONSUMER_INVENTORY, CUTOVER_RECORD,
        MAINTAINER_APPROVAL, MIGRATION_RUN, MISFIT_RECORD, MISFIT_DECISION, PARITY_REPORT,
        EMAIL_ALLOWANCE, RELEASE_RECORD, RECEIPT_FACTS, LIFECYCLE_EVIDENCE, LEDGER_ADOPTED,
        LEDGER_DISCARDED, LEDGER_REPAIRED,
    )
}
RECOVERY_KINDS = frozenset({"ledger.adopted", "ledger.discarded", "ledger.repaired"})
RECEIPT_BEARING = frozenset(kind for kind, schema in SCHEMAS.items() if schema.receipts)


def schema_of(kind: str) -> Schema:
    schema = SCHEMAS.get(kind)
    if schema is None:
        raise RecordRefused("unregistered-kind")
    return schema


@dataclass
class Fold:
    """Each keyed entity's latest version and its revision (number of versions), plus
    each unkeyed kind's events, rebuilt from entries in order."""

    current: dict[tuple[str, tuple], dict] = field(default_factory=dict)
    revisions: dict[tuple[str, tuple], int] = field(default_factory=dict)
    events: dict[str, list[dict]] = field(default_factory=dict)
    by_kind: dict[str, dict[tuple, dict]] = field(default_factory=dict)

    def apply(self, kind: str, record: dict) -> None:
        schema = schema_of(kind)
        schema.validate(record)
        if not schema.keyed:
            self.events.setdefault(kind, []).append(record)
            return
        key = (kind, schema.key_of(record))
        revision = self.revisions.get(key, 0) + 1
        if revision > schema.max_versions:
            raise RecordRefused("version-bound")
        self.revisions[key] = revision
        self.current[key] = record
        self.by_kind.setdefault(kind, {})[key[1]] = record

    def get(self, kind: str, key: tuple) -> dict | None:
        return self.current.get((kind, tuple(key)))

    def revision(self, kind: str, key: tuple) -> int:
        return self.revisions.get((kind, tuple(key)), 0)

    def records(self, kind: str) -> list[dict]:
        return list(self.by_kind.get(kind, {}).values())


def fold(entries: Iterable) -> Fold:
    """Fold entries (any objects with `kind` and `record`) in order."""
    result = Fold()
    for entry in entries:
        result.apply(entry.kind, entry.record)
    return result


def latest_by(entries: Iterable, kind: str, key_field: str) -> dict[str, dict]:
    """The latest version of each record of `kind` by one key field, without schema
    checks: the start check reads raw entries before any component is built."""
    latest: dict[str, dict] = {}
    for entry in entries:
        if entry.kind == kind and isinstance(entry.record.get(key_field), str):
            latest[entry.record[key_field]] = entry.record
    return latest
