"""Bounded, consent-aware Personalization behavior in the isolated U2 assembly.

Trusted component bindings are installed by composition and never constructed
from HTTP input. Reading a projection never records activity or starts cleanup.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from docsuri_shared.workspace import execution, wire
from psycopg.errors import InsufficientPrivilege
from psycopg.types.json import Jsonb

from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import ControlPolicy, PolicyUnavailable
from backend.modules.personalization.guarded_service import INTEREST_VOCABULARY, VOCABULARY
from backend.modules.personalization.reset_repository import ResetRepository
from backend.transactions import Authority, OwnerTransactions, guard


@dataclass(frozen=True, eq=False)
class ProducerBinding:
    component: str


class BehaviorAuthorityLost(PermissionError):
    """Roll back the complete transaction before publishing a safe suppression."""


class PersonalizationControlService:
    def __init__(
        self,
        transactions: OwnerTransactions,
        policy: ControlPolicy,
        cursor: ControlCursor,
        *,
        producers: tuple[ProducerBinding, ...],
        suggestions_provider: Callable[[Authority, str], list[dict]] | None = None,
    ):
        policy.require_realm(transactions.profile.realm)
        if (
            not producers
            or len(producers) > policy.max_scopes
            or any(
                item.component not in ("CorpusContent", "PaperAssistance", "Library", "Discovery")
                for item in producers
            )
        ):
            raise ValueError("bounded installed producer manifest required")
        self.transactions, self.policy, self.cursor = transactions, policy, cursor
        self.producers, self.suggestions_provider = producers, suggestions_provider
        self.resets = ResetRepository(transactions, policy, cursor)

    def _producer(self, producer: ProducerBinding) -> None:
        if not any(producer is installed for installed in self.producers):
            raise PermissionError("unregistered personalization producer")

    def _state(self, conn, authority: Authority) -> tuple[UUID, dict, int]:
        revision = guard(conn, authority, purpose="account-control")
        consent = conn.execute(
            "SELECT * FROM accounts.personalization_consent_status(%s,%s)",
            (authority.account_id, authority.session_id),
        ).fetchone()
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,22))", (str(authority.account_id),)
        )
        row = conn.execute(
            "SELECT input_boundary FROM personalization.settings WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()
        return revision, consent, row["input_boundary"] if row else 0

    def _limit(self, limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= self.policy.max_page_size:
            raise ValueError("invalid bounded page size")

    def suggestions(
        self,
        authority: Authority,
        *,
        limit: int,
        cursor: str | None = None,
        identity_link_id: str | None = None,
    ) -> dict:
        self._limit(limit)
        # Authenticate before consulting any linked-identity provider.
        revision = self.transactions.run(
            "personalization", lambda conn: guard(conn, authority, purpose="account-control")
        )
        items = [
            dict(
                interestId=item,
                labelKey="interest:" + item,
                source="retained_manual_vocabulary",
                sourceRevision=VOCABULARY,
                reasonKey="manual-selection",
            )
            for item in INTEREST_VOCABULARY
        ]
        if identity_link_id:
            if self.suggestions_provider is None:
                raise PolicyUnavailable(
                    "ORCID enrichment unavailable; manual choices remain available"
                )
            items += self.suggestions_provider(authority, identity_link_id)
        if len(items) > self.policy.max_page_size:
            raise ValueError("bounded suggestion vocabulary exceeded")
        # Provider output is validated, deduplicated and revision-bound.
        normalized = list(
            {
                item["interestId"]: item
                for item in (
                    wire.SettingsSuggestion.model_validate(item).model_dump(mode="json")
                    for item in items
                )
            }.values()
        )
        snapshot = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
        scope = f"suggestions:{revision}:{snapshot}:{identity_link_id or 'manual'}:{limit}"
        offset = self.cursor.decode(authority.account_id, scope, cursor)["offset"] if cursor else 0
        if type(offset) is not int or not 0 <= offset <= len(normalized):
            raise ValueError("stale suggestion page")
        page = normalized[offset : offset + limit]
        following = offset + len(page)
        # Recheck current authority after the provider call, before publication.
        current = self.transactions.run(
            "personalization", lambda conn: guard(conn, authority, purpose="account-control")
        )
        if current != revision:
            raise PermissionError("authority changed during suggestions")
        return wire.SettingsSuggestionPage.model_validate(
            {
                "items": page,
                "page": {
                    "snapshotRevision": snapshot,
                    "nextCursor": self.cursor.encode(
                        authority.account_id, scope, {"offset": following}
                    )
                    if following < len(normalized)
                    else None,
                },
                "appliedLimit": limit,
                "policyRef": self.policy.reference,
            }
        ).model_dump(mode="json")

    def record_behavior(self, producer: ProducerBinding, authority: Authority, event: dict) -> dict:
        self._producer(producer)
        event = execution.SettingsBehaviorEvent.model_validate(event).model_dump(mode="json")
        if len(json.dumps(event).encode()) > self.policy.max_value_bytes:
            raise ValueError("bounded behavior envelope required")
        required = {
            "eventId",
            "accountId",
            "paper",
            "activityId",
            "occurredAt",
            "consentRevision",
            "inputBoundary",
            "authorityRevision",
        }
        if set(event) != required or event["accountId"] != str(authority.account_id):
            raise ValueError("invalid behavior owner or fields")
        identifier = UUID(event["eventId"])
        paper = wire.PaperRef.model_validate(event["paper"]).model_dump(mode="json")
        if event["activityId"] not in ("paper-view", "summary", "translate", "save"):
            raise ValueError("unsupported synthetic activity")
        occurred = datetime.fromisoformat(event["occurredAt"])
        if occurred.tzinfo is None or len(str(event["inputBoundary"])) > 20:
            raise ValueError("bounded timestamp and boundary required")
        expected_boundary = int(event["inputBoundary"])
        expected_authority, expected_consent = (
            UUID(event["authorityRevision"]),
            UUID(event["consentRevision"]),
        )

        def write(conn):
            try:
                revision, consent, boundary = self._state(conn, authority)
            except InsufficientPrivilege as error:
                raise BehaviorAuthorityLost("current authority unavailable") from error
            disposition = "recorded"
            if revision != expected_authority:
                disposition = "suppressed_by_lifecycle"
            elif not consent["granted"] or consent["revision"] != expected_consent:
                disposition = "suppressed_by_consent"
            elif boundary != expected_boundary:
                disposition = "suppressed_by_reset"
            if disposition != "recorded":
                return {
                    "disposition": disposition,
                    "inputBoundary": str(boundary),
                    "requestId": str(identifier),
                }
            source = conn.execute(
                "SELECT * FROM corpus.personalization_source(%s,%s)",
                (paper["paperId"], paper["versionId"]),
            ).fetchone()
            if (
                source["disposition"] != "available"
                or str(source["eligibility_revision"]) != paper["eligibilityRevision"]
            ):
                raise PermissionError("behavior source unavailable")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if occurred > now:
                raise ValueError("future behavior timestamp")
            prior = conn.execute(
                "SELECT fact FROM personalization.behavior WHERE account_id=%s AND id=%s",
                (authority.account_id, identifier),
            ).fetchone()
            if prior:
                if prior["fact"] != event:
                    raise ValueError("behavior identity conflict")
                disposition = "duplicate"
            else:
                count = conn.execute(
                    "SELECT count(*) AS n FROM personalization.behavior WHERE account_id=%s",
                    (authority.account_id,),
                ).fetchone()["n"]
                if count >= self.policy.max_outstanding:
                    raise ValueError("finite synthetic behavior capacity")
                conn.execute(
                    "INSERT INTO personalization.behavior(account_id,id,purpose_revision,fact,"
                    "input_boundary,authority_revision,paper_version_id,activity) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        authority.account_id,
                        identifier,
                        consent["revision"],
                        Jsonb(event),
                        boundary,
                        revision,
                        paper["versionId"],
                        event["activityId"],
                    ),
                )
            return {
                "disposition": disposition,
                "inputBoundary": str(boundary),
                "requestId": str(identifier),
            }

        try:
            result = self.transactions.run("personalization", write)
        except BehaviorAuthorityLost:
            result = {
                "disposition": "suppressed_by_lifecycle",
                "inputBoundary": str(expected_boundary),
                "requestId": str(identifier),
            }
        return execution.SettingsBehaviorResult.model_validate(result).model_dump(mode="json")

    def recent(self, authority: Authority, *, limit: int, cursor: str | None = None) -> dict:
        self._limit(limit)

        def read(conn):
            revision, consent, boundary = self._state(conn, authority)
            if not consent["granted"]:
                raise PermissionError("personalized activity disabled")
            scope = f"recent:{revision}:{consent['revision']}:{boundary}:{limit}"
            position = self.cursor.decode(authority.account_id, scope, cursor) if cursor else None
            cutoff = (
                datetime.fromisoformat(position["cutoff"])
                if position
                else conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            )
            rows = conn.execute(
                "SELECT * FROM (SELECT DISTINCT ON (paper_version_id) * "
                "FROM personalization.behavior WHERE account_id=%s AND purpose_revision=%s "
                "AND authority_revision=%s AND input_boundary=%s AND created_at<=%s "
                "ORDER BY paper_version_id,created_at DESC,id DESC) latest "
                "WHERE (%s::timestamptz IS NULL OR (created_at,id)<(%s::timestamptz,%s::uuid)) "
                "ORDER BY created_at DESC,id DESC LIMIT %s",
                (
                    authority.account_id,
                    consent["revision"],
                    revision,
                    boundary,
                    cutoff,
                    position["time"] if position else None,
                    position["time"] if position else None,
                    position["id"] if position else None,
                    limit + 1,
                ),
            ).fetchall()
            items = []
            for row in rows[:limit]:
                paper = row["fact"]["paper"]
                source = conn.execute(
                    "SELECT * FROM corpus.personalization_source(%s,%s)",
                    (paper["paperId"], paper["versionId"]),
                ).fetchone()
                items.append(
                    {
                        "paper": paper,
                        "lastActivityAt": row["created_at"].isoformat(),
                        "activityReference": str(row["id"]),
                        "sourceDisposition": source["disposition"],
                    }
                )
            next_cursor = (
                self.cursor.encode(
                    authority.account_id,
                    scope,
                    {
                        "cutoff": cutoff.isoformat(),
                        "time": rows[limit - 1]["created_at"].isoformat(),
                        "id": str(rows[limit - 1]["id"]),
                    },
                )
                if len(rows) > limit
                else None
            )
            return wire.SettingsRecentPage.model_validate(
                {
                    "items": items,
                    "page": {"nextCursor": next_cursor, "snapshotRevision": cutoff.isoformat()},
                    "appliedLimit": limit,
                    "policyRef": self.policy.reference,
                }
            ).model_dump(mode="json")

        return self.transactions.run("personalization", read)

    def read_projection(
        self, producer: ProducerBinding, authority: Authority, *, purpose: str
    ) -> dict:
        self._producer(producer)
        if purpose != "personalization":
            raise PermissionError("unsupported projection purpose")

        def read(conn):
            revision, consent, boundary = self._state(conn, authority)
            interests = []
            disposition = "disabled"
            ids = []
            if consent["granted"]:
                rows = conn.execute(
                    "SELECT id,fact FROM personalization.behavior WHERE account_id=%s "
                    "AND purpose_revision=%s AND authority_revision=%s AND input_boundary=%s "
                    "ORDER BY created_at DESC,id DESC LIMIT %s",
                    (
                        authority.account_id,
                        consent["revision"],
                        revision,
                        boundary,
                        self.policy.max_outstanding,
                    ),
                ).fetchall()
                for row in rows:
                    paper = row["fact"]["paper"]
                    source = conn.execute(
                        "SELECT * FROM corpus.personalization_source(%s,%s)",
                        (paper["paperId"], paper["versionId"]),
                    ).fetchone()
                    if (
                        source["disposition"] == "available"
                        and str(source["eligibility_revision"]) == paper["eligibilityRevision"]
                    ):
                        ids.append(str(row["id"]))
                        if (
                            paper["paperId"] in INTEREST_VOCABULARY
                            and paper["paperId"] not in interests
                        ):
                            interests.append(paper["paperId"])
                disposition = "ready" if interests else "cold_start"
            projection_revision = uuid5(
                NAMESPACE_URL,
                f"{authority.account_id}:{revision}:{consent['revision']}:{boundary}:{disposition}:{','.join(ids)}",
            )
            return {
                "accountId": str(authority.account_id),
                "profileId": str(authority.account_id),
                "revision": str(projection_revision),
                "inputBoundary": str(boundary),
                "consentRevision": str(consent["revision"]),
                "disposition": disposition,
                "interestIds": interests,
                "reasonKey": disposition,
            }

        return execution.SettingsProfileProjection.model_validate(
            self.transactions.run("personalization", read)
        ).model_dump(mode="json")

    def clean_reset(self, identifier: UUID) -> dict:
        """Installed Personalization participant; no browser-supplied scope binding."""
        claim = self.resets.claim_scope(identifier, "Personalization", "behavior")

        def clean(conn):
            reset = conn.execute(
                "SELECT * FROM personalization.reset_responsibility WHERE id=%s FOR UPDATE",
                (identifier,),
            ).fetchone()
            scope = conn.execute(
                "SELECT *,clock_timestamp() AS now FROM personalization.reset_scope "
                "WHERE reset_id=%s AND participant='Personalization' "
                "AND scope='behavior' FOR UPDATE",
                (identifier,),
            ).fetchone()
            if (
                not scope
                or scope["generation"] != claim["generation"]
                or scope["lease_until"] <= scope["now"]
            ):
                raise ValueError("stale reset cleanup claim")
            # Preserve all activity admitted after the immutable accepted boundary.
            conn.execute(
                "DELETE FROM personalization.behavior WHERE account_id=%s AND input_boundary<%s",
                (reset["account_id"], reset["input_boundary"]),
            )
            conn.execute(
                "DELETE FROM personalization.projection WHERE account_id=%s AND input_boundary<%s",
                (reset["account_id"], reset["input_boundary"]),
            )
            evidence = uuid4()
            conn.execute(
                "INSERT INTO personalization.lifecycle_evidence(request_id,scope,generation,"
                "policy_ref,manifest_revision,evidence_ref) "
                "VALUES(%s,'reset-behavior',%s,%s,%s,%s) "
                "ON CONFLICT(request_id,scope) DO UPDATE SET generation=excluded.generation,"
                "evidence_ref=excluded.evidence_ref",
                (
                    identifier,
                    claim["generation"],
                    Jsonb(reset["policy_ref"]),
                    reset["manifest_revision"],
                    evidence,
                ),
            )
            return evidence

        evidence = self.transactions.run("personalization", clean)
        return self.resets.record_scope(
            identifier,
            "Personalization",
            "behavior",
            claim["generation"],
            evidence=evidence,
            reason="owner-cleanup-complete",
        )

    def apply_consent_boundary(self, fact: dict) -> dict:
        """Consume an installed AccountAccess outbox fact, never a browser body.

        A lost acknowledgement reuses the exact durable evidence. This records
        only the live Personalization store effect; backup enforcement is an
        independent required responsibility and cannot be inferred from it.
        """
        if fact["purpose"] != "personalization":
            raise ValueError("foreign consent purpose")
        owner, identifier = UUID(str(fact["account_id"])), UUID(str(fact["id"]))
        consent_revision = UUID(str(fact["consent_revision"]))
        authority_revision = UUID(str(fact["authority_revision"]))
        if type(fact["granted"]) is not bool:
            raise ValueError("invalid consent decision")
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "id": str(identifier),
                    "account": str(owner),
                    "consent": str(consent_revision),
                    "authority": str(authority_revision),
                    "granted": fact["granted"],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

        def write(conn):
            current = conn.execute(
                "SELECT * FROM accounts.personalization_effect_authority(%s)", (owner,)
            ).fetchone()
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,22))", (str(owner),))
            prior = conn.execute(
                "SELECT * FROM personalization.receipt WHERE account_id=%s "
                "AND kind='consent-boundary' AND key=%s",
                (owner, identifier),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != fingerprint:
                    raise ValueError("consent obligation conflict")
                return prior["outcome"]
            superseded = (
                current["authority_revision"] != authority_revision
                or current["consent_revision"] != consent_revision
                or current["granted"] != fact["granted"]
            )
            if not superseded:
                row = conn.execute(
                    "INSERT INTO personalization.settings(account_id,revision,input_boundary) "
                    "VALUES(%s,%s,1) ON CONFLICT(account_id) DO UPDATE SET "
                    "revision=excluded.revision,"
                    "input_boundary=personalization.settings.input_boundary+1 "
                    "RETURNING input_boundary",
                    (owner, uuid4()),
                ).fetchone()
                conn.execute(
                    "DELETE FROM personalization.behavior WHERE account_id=%s "
                    "AND input_boundary<%s",
                    (owner, row["input_boundary"]),
                )
                conn.execute(
                    "DELETE FROM personalization.projection WHERE account_id=%s "
                    "AND input_boundary<%s",
                    (owner, row["input_boundary"]),
                )
            outcome = {
                "evidenceRef": str(uuid4()),
                "disposition": "superseded" if superseded else "owner-cleanup-complete",
                "consentRevision": str(consent_revision),
            }
            conn.execute(
                "INSERT INTO personalization.receipt(account_id,kind,key,intent_hash,outcome) "
                "VALUES(%s,'consent-boundary',%s,%s,%s)",
                (owner, identifier, fingerprint, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("personalization", write)
