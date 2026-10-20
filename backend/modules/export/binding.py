"""The one binding check, shared by approve, continue and the lane's pre-write check
(BR3.1, BR3.3, BR3.7).

It re-derives every fact an approval bound and answers one of three verdicts:

- `unchanged`: every fact still holds;
- `changed`: a fact definitely changed. The verdict carries the invalidation reason
  (`source-changed`, `destination-changed`, `connection-changed`, `authority-revoked`)
  and the refusal code an owner operation answers with;
- `could-not-check`: a fact could not be read (U4 or Notion unreachable, credential
  protection unavailable, policy unresolved). The verdict carries the failure reason a
  waiting effect ends with at the wait bound (`dependency-unavailable`,
  `policy-unresolved`) and the refusal code. A temporary failure is never a change.

Facts are checked cheapest first: the approving session (a 42501 is a definite
authority-revoked), the connection revision, the real-composition allowance, the source
through U4's export read under the approving owner's authority, and last a direct read
of the destination through Notion. The first definite change wins; a could-not-check is
kept while the remaining facts are still checked, so a definite change found later still
wins. The Notion read is skipped once a definite change is known, or while the
connection cannot be used.

Approve and continue pass the connection id as the gate key, so the destination read
takes an interactive slot (D15); the lane passes none.
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID

import psycopg

from backend.modules.research.errors import ResearchError
from backend.transactions import Authority
from backend.u6_policy import ExportPolicy

from .classification import (
    NOT_CONNECTED,
    NOT_READABLE,
    OK,
    PROTECTION_UNAVAILABLE,
    TOKEN_INVALID,
)
from .notion_session import StoredConnection

UNCHANGED = "unchanged"
CHANGED = "changed"
COULD_NOT_CHECK = "could-not-check"

SOURCE_CHANGED = "source-changed"
DESTINATION_CHANGED = "destination-changed"
CONNECTION_CHANGED = "connection-changed"
AUTHORITY_REVOKED = "authority-revoked"
DEPENDENCY_UNAVAILABLE = "dependency-unavailable"
POLICY_UNRESOLVED = "policy-unresolved"

# U4's definite answers about the source (BR2.1), with the code each one answers.
_SOURCE_CHANGES = {
    "NOT_FOUND": "NOT_FOUND",
    "CONFLICT": "CONFLICT",
    "SOURCE_INELIGIBLE": "SOURCE_INELIGIBLE",
}


@dataclass(frozen=True)
class BindingVerdict:
    status: str
    reason: str | None = None
    code: str | None = None

    @property
    def unchanged(self) -> bool:
        return self.status == UNCHANGED

    @property
    def changed(self) -> bool:
        return self.status == CHANGED


_UNCHANGED = BindingVerdict(UNCHANGED)


def _changed(reason: str, code: str) -> BindingVerdict:
    return BindingVerdict(CHANGED, reason, code)


def _unchecked(reason: str) -> BindingVerdict:
    code = "POLICY_UNRESOLVED" if reason == POLICY_UNRESOLVED else "DEPENDENCY_UNAVAILABLE"
    return BindingVerdict(COULD_NOT_CHECK, reason, code)


@dataclass(frozen=True)
class BoundFacts:
    """What one approval bound: owner and approving session, the source tuple and its
    eligibility revision, the connection revision and the destination."""

    account_id: UUID
    approving_session: UUID
    artifact_id: UUID
    source_revision: str
    source_content_hash: str
    source_eligibility_revision: str
    connection_id: UUID
    connection_revision: int
    destination_id: str

    @classmethod
    def of(
        cls,
        revision,
        *,
        account_id: UUID,
        approving_session: UUID,
        artifact_id: UUID,
        destination_id: str,
    ) -> "BoundFacts":
        """From a stored preview revision row and the approval's owner and session."""
        return cls(
            account_id=account_id,
            approving_session=approving_session,
            artifact_id=artifact_id,
            source_revision=revision["source_revision"],
            source_content_hash=revision["source_content_hash"],
            source_eligibility_revision=revision["source_eligibility_revision"],
            connection_id=revision["connection_id"],
            connection_revision=revision["connection_revision"],
            destination_id=destination_id,
        )

    @property
    def source(self) -> dict:
        """The ResearchArtifactRef tuple exactly as the preview froze it (R-02)."""
        return {
            "artifactId": str(self.artifact_id),
            "revision": self.source_revision,
            "contentHash": self.source_content_hash,
        }


def read_source(research, authority: Authority, reference: dict):
    """U4's export read, reduced to (prepared, verdict). Exactly one is not None.

    The verdict is a definite change for U4's absent, changed and ineligible answers
    and for a refused session; could-not-check for policy and for anything else."""
    verdict = None
    try:
        response = research.readNoveltyArtifactForExport(authority, reference)
    except psycopg.errors.InsufficientPrivilege:
        verdict = _changed(AUTHORITY_REVOKED, "UNAUTHENTICATED")
    except ResearchError as error:
        code = error.code
        if code in _SOURCE_CHANGES:
            verdict = _changed(SOURCE_CHANGED, _SOURCE_CHANGES[code])
        elif code == "POLICY_UNRESOLVED":
            verdict = _unchecked(POLICY_UNRESOLVED)
        else:
            verdict = _unchecked(DEPENDENCY_UNAVAILABLE)
    except Exception:  # noqa: BLE001 - unreachable is could-not-check, never ineligible
        verdict = _unchecked(DEPENDENCY_UNAVAILABLE)
    if verdict is not None:
        return None, verdict
    if not isinstance(response, dict):
        return None, _unchecked(DEPENDENCY_UNAVAILABLE)
    prepared = response.get("prepared")
    if response.get("availability") != "ready" or not isinstance(prepared, dict):
        return None, _changed(SOURCE_CHANGED, "SOURCE_INELIGIBLE")
    if prepared.get("artifact") != reference or prepared.get("kind") != "novelty-result":
        return None, _changed(SOURCE_CHANGED, "CONFLICT")
    return prepared, None


def check_source(
    research, authority: Authority, reference: dict, eligibility_revision: str
) -> BindingVerdict | None:
    """The source fact alone: U4's export read of the bound tuple, with the eligibility
    revision the preview froze. None while it holds; otherwise a definite change or a
    could-not-check. The pass step's housekeeping uses it as well (NFR4.9)."""
    prepared, verdict = read_source(research, authority, reference)
    if verdict is not None:
        return verdict
    if str(prepared.get("currentEligibilityRevision")) != eligibility_revision:
        return _changed(SOURCE_CHANGED, "CONFLICT")
    return None


class BindingCheck:
    def __init__(self, repository, adapter, research, policy: ExportPolicy):
        if not isinstance(policy, ExportPolicy):
            raise TypeError("an ExportPolicy is required")
        self._repository = repository
        self._adapter = adapter
        self._research = research
        self._policy = policy

    def check(self, facts: BoundFacts, *, gate_key: UUID | None = None) -> BindingVerdict:
        """Re-derive the binding; see the module docstring for the verdicts."""
        if not isinstance(facts, BoundFacts):
            raise TypeError("bound facts are required")
        found: list[BindingVerdict] = []

        def changed(verdict: BindingVerdict | None) -> bool:
            if verdict is not None:
                found.append(verdict)
            return verdict is not None and verdict.changed

        if changed(self._session(facts)):
            return found[-1]
        connection = self._connection(facts)
        if changed(connection):
            return connection
        if changed(self._allowance(facts)) or changed(self._source(facts)):
            return found[-1]
        if connection is None and changed(self._destination(facts, gate_key)):
            return found[-1]
        return found[0] if found else _UNCHANGED

    # -- the facts ----------------------------------------------------------------------

    def _session(self, facts: BoundFacts) -> BindingVerdict | None:
        try:
            current = self._repository.session_is_current(facts.account_id, facts.approving_session)
        except Exception:  # noqa: BLE001 - a guard that could not run is not a revocation
            return _unchecked(DEPENDENCY_UNAVAILABLE)
        return None if current else _changed(AUTHORITY_REVOKED, "UNAUTHENTICATED")

    def _connection(self, facts: BoundFacts) -> BindingVerdict | None:
        try:
            row = self._repository.connection_state(facts.account_id, facts.connection_id)
        except Exception:  # noqa: BLE001 - the store could not answer
            return _unchecked(DEPENDENCY_UNAVAILABLE)
        if row is None or row["revision"] != facts.connection_revision:
            return _changed(CONNECTION_CHANGED, "CONFLICT")
        if row["state"] == "unavailable":
            # BR1.6: the token cannot be opened; nothing changed, the work waits.
            return _unchecked(POLICY_UNRESOLVED)
        if row["state"] != "connected":
            return _changed(CONNECTION_CHANGED, "CONFLICT")
        return None

    def _allowance(self, facts: BoundFacts) -> BindingVerdict | None:
        activation = self._policy.activation_destination_id
        if activation is not None and facts.destination_id != activation:
            return _changed(DESTINATION_CHANGED, "FORBIDDEN")
        return None

    def _source(self, facts: BoundFacts) -> BindingVerdict | None:
        authority = Authority(facts.account_id, facts.approving_session)
        return check_source(
            self._research, authority, facts.source, facts.source_eligibility_revision
        )

    def _destination(self, facts: BoundFacts, gate_key: UUID | None) -> BindingVerdict | None:
        target = StoredConnection(facts.account_id, facts.connection_id)
        read = asyncio.run(
            self._adapter.read_destination(target, facts.destination_id, gate_key=gate_key)
        )
        if read.category == OK and read.readable:
            return None
        if read.category == NOT_READABLE:
            return _changed(DESTINATION_CHANGED, "CONFLICT")
        if read.category in (TOKEN_INVALID, NOT_CONNECTED):
            return _changed(CONNECTION_CHANGED, "CONFLICT")
        if read.category == PROTECTION_UNAVAILABLE:
            return _unchecked(POLICY_UNRESOLVED)
        return _unchecked(DEPENDENCY_UNAVAILABLE)
