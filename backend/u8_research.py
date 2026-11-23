"""ResearchWorkspace's production work (U8 plan Step 21; your decision of 2026-10-24,
"Build the research executor"), as `u8_topics.py` does TopicsDigests' live work. No U4
backend file changes: the production policy, execution and service extend U4's own, and
every synthetic realm keeps `u4_host.research_contribution` as built.

**The provider interface** (`LocalResearchModel` in `u8_research_model.py` implements it):

- `available() -> bool`, cached for 30 s and asked only after a cheap check that work is
  claimable, so the runtime is never polled every second;
- `run(sources, *, request, deadline, sent=None) -> dict`, where `request` is
  `{kind, mode, text, prior}` with the `jobId` the evidence IDs derive from: output that
  has already passed `validate_output`, or
  `ResearchFailure(code)` (terminal) or `ProviderWaiting(cause)`. The rows it sent are
  appended to `sent`, so completion re-reads exactly those rows.

**How each failure ends** (design § 1.4): a runtime that is unreachable, reports another
digest, answers 5xx or does not answer in time is `ProviderWaiting` (the attempt counts,
the lease is cut to 30 s and the job records its `wait_reason`); our own request refused
(4xx, too large) fails with `INTERNAL_ERROR`; a malformed, truncated or out-of-bounds
answer fails with `INVALID_CONTENT`; nothing claimable, an unavailable provider or a busy
lane makes no claim and spends no attempt.

**How long results are kept** (your decision of 2026-10-24, "Until deleted or erased"):
until their owner deletes them or the account is erased. `PRODUCTION_RESEARCH` names the
policy `u8_research_retention.sql` recognises, which stores the fixed mark
`9999-12-31 00:00:00+00` as every production artifact's `expires_at`; its
`artifact_seconds` is kept only because U4's rules require a positive value there.

This module imports no ServiceOperations module (`u8_registry.PORT_OWNERS`): the
composition hands the service its observation read as a function.
"""

from __future__ import annotations

import dataclasses
import hashlib
import time
from collections.abc import Callable
from uuid import UUID, uuid5

from psycopg.errors import InsufficientPrivilege

from backend.modules.research.errors import ResearchError
from backend.modules.research.execution import ResearchExecution, binding
from backend.modules.research.repository import digest
from backend.modules.research.service import ResearchService, artifact_dto
from backend.transactions import Authority, UnknownCommit
from backend.u4_policy import ResearchPolicy

PRODUCTION_REALM = "production"
POLICY_ID = "docsuri-production-research"
WAIT_REASONS = frozenset({"DEADLINE_EXCEEDED", "DEPENDENCY_UNAVAILABLE"})
OUTCOMES = frozenset(
    {"idle", "closed", "cancelled", "succeeded", "failed", "waiting", "fenced", "unknown",
     "busy"}
)
ARTIFACT_KINDS = {
    "research-turn": "research-answer",
    "novelty-analysis": "novelty-result",
    "novelty-discussion": "novelty-discussion",
}
# The capability each kind of request is admitted under (BR3.2).
CAPABILITY_OF = {"research-turn": "research", "novelty-analysis": "novelty",
                 "novelty-discussion": "novelty"}
WAITING_REASON = "model-runtime-waiting"
HOUSEKEEPING_ROWS = 4


class ResearchFailure(Exception):
    """A terminal failure of one research job, with its code (`INVALID_CONTENT`,
    `INTERNAL_ERROR`, `SOURCE_INELIGIBLE`)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ProviderWaiting(Exception):
    """The model runtime is not answering for now; the job waits and its attempt counts.
    `cause` names why (fixed words only), `wait_reason` is what the job records."""

    def __init__(self, cause: str, *, wait_reason: str = "DEPENDENCY_UNAVAILABLE"):
        if wait_reason not in WAIT_REASONS:
            raise ValueError("unknown wait reason")
        super().__init__(cause)
        self.cause, self.wait_reason = cause, wait_reason


# --- PRODUCTION_RESEARCH ------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ProductionResearchPolicy(ResearchPolicy):
    """`docsuri-production-research` revision 1, recognised by its class. U4's
    `ResearchPolicy.__post_init__` refuses every policy but the synthetic one, so this
    runs U4's per-field checks itself, with concurrency 1."""

    policy_id: str = POLICY_ID
    revision: str = "1"
    synthetic_only: bool = False
    # The server enforces a question of at most 2,048 bytes.
    text_bytes: int = 2048
    # A claim's lease, the wait between attempts and the unclaimed bound.
    lease_seconds: int = 150
    retry_seconds: int = 30
    unclaimed_seconds: int = 900
    realm: str = PRODUCTION_REALM

    def __post_init__(self):
        for name in (
            "upload_bytes", "text_bytes", "queue_depth", "concurrency", "retries",
            "lease_seconds", "artifact_seconds", "page_size", "retry_seconds",
            "unclaimed_seconds",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"finite positive {name} required")
        if (self.policy_id, self.revision, self.realm) != (POLICY_ID, "1", PRODUCTION_REALM):
            raise ValueError("the production research policy is fixed")
        if self.synthetic_only or self.concurrency != 1:
            raise ValueError("production research runs one job at a time on real data")
        if self.durable_drafts or self.private_attachments:
            raise ValueError("drafts and private attachments stay off")
        if self.retry_seconds >= self.lease_seconds:
            raise ValueError("the wait between attempts must be shorter than the lease")


PRODUCTION_RESEARCH = ProductionResearchPolicy()


def require_production(transactions, policy) -> None:
    """`PRODUCTION_RESEARCH` runs in the production realm only, and only it does."""
    profile = getattr(transactions, "profile", None)
    if not isinstance(policy, ProductionResearchPolicy):
        raise ValueError("production research needs the production research policy")
    if not getattr(profile, "is_production", False) or profile.realm != PRODUCTION_REALM:
        raise ValueError("the production research policy runs in the production realm only")


def unread_reference(url: str) -> dict:
    """A scope web reference: recorded as not read, never fetched (U4's BR3.3)."""
    return {
        "sourceKind": "unread-reference",
        "sourceId": hashlib.sha256(url.encode()).hexdigest(),
        "sourceVersion": "unread",
        "location": "reference",
        "sourceUrl": url,
    }


# --- ProductionResearchExecution ---------------------------------------------------------


class ProductionResearchExecution(ResearchExecution):
    """U4's execution with the production provider (module docstring). `step()` runs
    housekeeping only, so `ResearchWorker.run_once` and any whole-chain run never do
    model work; the model lane runs `execute_next`."""

    enabled = True

    def __init__(self, transactions, corpus, provider, *, lane,
                 policy: ProductionResearchPolicy = PRODUCTION_RESEARCH,
                 housekeeping_rows: int = HOUSEKEEPING_ROWS):
        require_production(transactions, policy)
        if not 1 <= housekeeping_rows <= 16:
            raise ValueError("housekeeping reads a bounded page")
        super().__init__(transactions, corpus, policy=policy)
        # U2's controls for all usage (your decision of 2026-10-23), under production's
        # policy; U4's built execution keeps its repository.
        from backend.modules.plans.u8_usage import use_complete_usage

        use_complete_usage(self, transactions)
        self.provider, self.lane = provider, lane
        self.housekeeping_rows = housekeeping_rows
        # The rows each job in hand sent, by job: completion re-reads exactly these.
        self._sent: dict[str, list[dict]] = {}
        # Housekeeping's place among the open jobs: the last job its latest full page
        # examined, as `(accepted_at, id)`; None starts from the oldest.
        self._examined: tuple | None = None

    # --- selection ---------------------------------------------------------------------

    _DUE = (
        "SELECT j.*, j.accepted_at <= clock_timestamp() - %s*interval '1 second' AS overdue "
        "FROM research.job j JOIN research.admission a ON a.operation_id=j.id "
        "WHERE a.state='accepted' AND j.state = ANY(%s) "
        "AND (j.lease_until IS NULL OR j.lease_until<=clock_timestamp()) "
    )

    def _rows(self, states: list[str], *, claimable: bool, limit: int,
              after: tuple | None = None) -> list[dict]:
        """Due rows in `states`, oldest first; `after` starts behind one `(accepted_at,
        id)` place."""
        query = self._DUE + (
            "AND (j.accepted_at,j.id) > (%s,%s) " if after is not None else "") + (
            "AND j.attempts < %s " if claimable else "") + "ORDER BY j.accepted_at,j.id LIMIT %s"
        params = [self.policy.unclaimed_seconds, states, *(after or ())]
        if claimable:
            params.append(self.policy.retries + 1)
        params.append(limit)
        return self.transactions.run(
            "research", lambda conn: conn.execute(query, params).fetchall())

    def claimable(self) -> bool:
        """A job is due: accepted or running, its lease free, attempts left. One short
        read, never a runtime call."""
        return bool(self._rows(["accepted", "running"], claimable=True, limit=1))

    # --- closing ----------------------------------------------------------------------

    def _close_free(self, row, code: str) -> str:
        """Close a job no claim holds as `failed` with `code`, fenced on its fence, and
        release its usage."""
        closed = self.transactions.run(
            "research",
            lambda conn: conn.execute(
                "UPDATE research.job SET state='failed',error_code=%s,revision=revision+1,"
                "seq=seq+1 WHERE id=%s AND fence=%s AND state IN "
                "('accepted','running','cancel_requested') AND (lease_until IS NULL OR "
                "lease_until<=clock_timestamp()) RETURNING *",
                (code, row["id"], row["fence"]),
            ).fetchone(),
        )
        if not closed:
            return "idle"
        self.reconcile(closed)
        return "closed"

    def _close_claimed(self, row, claim, message: UUID, code: str) -> str:
        """Close a job this claim holds as `failed` with `code`, when the completion route
        itself refused (a withdrawn source, refused authority). The terminal fact's one
        receipt key is taken in the same transaction, so a fact already committed under
        this claim's message identifier wins and nothing changes."""
        key = "completion:" + str(message)
        fact = {"messageId": str(message), "operationId": str(row["id"]), "outcome": "failed",
                "code": code}

        def close(conn):
            if conn.execute(
                "SELECT 1 FROM research.receipt WHERE owner_id=%s AND operation_key=%s",
                (row["owner_id"], key),
            ).fetchone():
                return None
            closed = conn.execute(
                "UPDATE research.job SET state='failed',error_code=%s,revision=revision+1,"
                "seq=seq+1 WHERE id=%s AND fence=%s AND lease_id=%s AND state IN "
                "('running','cancel_requested') RETURNING *",
                (code, row["id"], claim["fence"], claim["leaseId"]),
            ).fetchone()
            if closed:
                from psycopg.types.json import Jsonb

                conn.execute(
                    "INSERT INTO research.receipt(owner_id,operation_key,input_hash,response) "
                    "VALUES(%s,%s,%s,%s)",
                    (row["owner_id"], key, digest(fact),
                     Jsonb({"jobId": str(row["id"]), "state": "failed"})),
                )
                conn.execute("UPDATE research.dispatch SET delivered=true WHERE job_id=%s",
                             (row["id"],))
            return closed

        closed = self.transactions.run("research", close)
        if not closed:
            return "unknown"
        self.reconcile(closed)
        return "failed"

    def _refused_claim(self, row, code: str) -> str:
        if code == "CAPACITY_EXHAUSTED":
            code = row.get("wait_reason") or "DEPENDENCY_UNAVAILABLE"
        elif code in ("NOT_FOUND", "FORBIDDEN"):
            code = "EXPIRED"
        return self._close_free(row, code)

    def _wait(self, row, claim, wait_reason: str) -> str:
        """A waiting failure: the lease is cut to the wait between attempts and the job
        records why it waits; the attempt the claim took stays spent."""
        self.transactions.run(
            "research",
            lambda conn: conn.execute(
                "UPDATE research.job SET lease_until=clock_timestamp()+%s*interval '1 second',"
                "wait_reason=%s WHERE id=%s AND fence=%s AND lease_id=%s",
                (self.policy.retry_seconds, wait_reason, row["id"], claim["fence"],
                 claim["leaseId"]),
            ),
        )
        return "waiting"

    def _scope_refusal(self, row) -> str | None:
        """Why a due job can no longer run, read under its owner's live authority: an
        ended session or context, or refused authority, is `EXPIRED`; a withdrawn source
        is `SOURCE_INELIGIBLE`. None while it can still run."""
        authority = Authority(row["owner_id"], row["authority_session"])

        def check(conn):
            try:
                with conn.transaction():
                    self.locked(conn, authority, row["id"])
            except InsufficientPrivilege:
                return "SOURCE_INELIGIBLE"
            except ResearchError as error:
                return "EXPIRED" if error.code == "NOT_FOUND" else error.code
            return None

        try:
            return self.run(authority, check)
        except (PermissionError, InsufficientPrivilege):
            return "EXPIRED"

    # --- housekeeping -----------------------------------------------------------------

    def housekeeping(self) -> dict:
        """U4's three recoveries, cancellations without the model (U4's BR6.4), and the
        refused claims: spent attempts close with their `wait_reason`; an ended session
        or context, or refused authority, with `EXPIRED`; an ineligible source with
        `SOURCE_INELIGIBLE`; and, only while the model is not ready and provider.models
        is not observed unavailable (`_unclaimed_closes`), a job accepted 900 s ago and
        never claimed with `DEPENDENCY_UNAVAILABLE`, releasing its usage.

        One pass is bounded: at most `housekeeping_rows` cancellations, read on their
        own so that no waiting job stands ahead of a cancel, and at most
        `housekeeping_rows` accepted or running jobs, taken in turn (`_open_page`), so a
        job that must close is reached within ceil(open jobs / `housekeeping_rows`)
        passes however many jobs wait for the model."""
        done = {"cancelled": 0, "closed": 0}
        self.admission.recover_prepared()
        self.admission.reconcile_release(self.usage)
        outstanding = self.transactions.run(
            "research",
            lambda conn: conn.execute(
                "SELECT j.* FROM research.job j JOIN research.admission a ON "
                "a.operation_id=j.id WHERE a.state='accepted' AND j.state IN "
                "('succeeded','failed','cancelled') AND usage_state='reserved' LIMIT 1"
            ).fetchone(),
        )
        if outstanding:
            self.reconcile(outstanding)
        for row in self._rows(["cancel_requested"], claimable=False,
                              limit=self.housekeeping_rows):
            if self._cancel(row) == "cancelled":
                done["cancelled"] += 1
        closes = None
        for row in self._open_page():
            code = None
            if row["attempts"] >= self.policy.retries + 1:
                code = row.get("wait_reason") or "DEPENDENCY_UNAVAILABLE"
            else:
                code = self._scope_refusal(row)
            if code is None and row["attempts"] == 0 and row["overdue"]:
                if closes is None:
                    closes = self._unclaimed_closes()
                if closes:
                    code = "DEPENDENCY_UNAVAILABLE"
            if code is not None and self._close_free(row, code) == "closed":
                done["closed"] += 1
        return done

    def _open_page(self) -> list[dict]:
        """The accepted and running jobs this pass examines: at most `housekeeping_rows`,
        continuing behind the last job the pass before examined and wrapping to the
        oldest, so every open job is examined once in every ceil(open jobs /
        `housekeeping_rows`) passes. Without this a page of jobs waiting out an observed
        outage (L4-4, option 1), which stay accepted and oldest, would keep every later
        job from being examined. With fewer open jobs than a page, every pass sees all."""
        limit, states = self.housekeeping_rows, ["accepted", "running"]
        rows = self._rows(states, claimable=False, limit=limit, after=self._examined)
        if self._examined is not None and len(rows) < limit:
            seen = {row["id"] for row in rows}
            rows += [row for row in self._rows(states, claimable=False,
                                               limit=limit - len(rows))
                     if row["id"] not in seen]
        self._examined = ((rows[-1]["accepted_at"], rows[-1]["id"])
                          if len(rows) == limit else None)
        return rows

    def _unclaimed_closes(self) -> bool:
        """Whether a job accepted 900 s ago and never claimed closes in this pass (your
        answer of 2026-11-22, L4-4 option 1; reliability-design § 10 line 146, "model
        jobs wait while provider.models is unavailable"). While the provider's circuit
        breaker is open nothing is asked of the runtime and no job closes: it waits for
        the outage to end. Otherwise the model is asked, and the job closes only while it
        is not ready. The breaker is read again after a not-ready answer, so a state that
        turned unavailable during the ask closes nothing either. A provider with no
        breaker (a stand-in) keeps the built rule."""
        held = getattr(self.provider, "held", None)
        if callable(held) and held():
            return False
        if self.provider.available():
            return False
        return not (callable(held) and held())

    def _cancel(self, row) -> str:
        authority = Authority(row["owner_id"], row["authority_session"])
        try:
            acquired = self.acquireExecutionClaim(
                authority, binding(row), self.worker_id, row["fence"] or None)
        except ResearchError as error:
            return self._refused_claim(row, error.code)
        except (PermissionError, InsufficientPrivilege):
            return self._refused_claim(row, "NOT_FOUND")
        message = self._message(row, acquired["claim"])
        return self._finish(authority, row, acquired, message, outcome="cancelled")

    def step(self):
        """Housekeeping only: model work runs in the model lane, never in the pass."""
        return self.housekeeping()

    # --- model work -------------------------------------------------------------------

    @staticmethod
    def _message(row, claim) -> UUID:
        """The one terminal message identifier of a claim: exactly one terminal fact can
        commit per claim."""
        return uuid5(UUID(str(row["id"])), f"{claim['leaseId']}:{claim['fence']}:terminal")

    def execute_next(self, *, deadline: float) -> str:
        """Claim the next due job, run the provider and complete it, under one message
        identifier derived from the lease and fence. Returns one of `OUTCOMES`. Only the
        provider's two failure types and the completion outcomes are caught here; anything
        else reaches the lane, which sets it aside as an incident."""
        from backend.modules.summarization.model_runtime import LaneBusy

        seconds = deadline - time.monotonic()
        if seconds <= 0:
            return "busy"
        try:
            with self.lane.work(min(seconds, 90.0), wait=0) as work_deadline:
                return self._execute(work_deadline)
        except LaneBusy:
            return "busy"

    def _execute(self, work_deadline: float) -> str:
        from .u8_job_lines import ENDED, STARTED, job_line

        rows = self._rows(["accepted", "running"], claimable=True, limit=1)
        if not rows or not self.provider.available():
            return "idle"
        row = rows[0]
        # The workers' job lines (Step 51(d), L1-6), from the row's origin request.
        origin = row.get("origin_request_id")
        job_line(STARTED, row["id"], origin)
        outcome = "error"
        try:
            outcome = self._execute_row(row, work_deadline)
            return outcome
        finally:
            job_line(ENDED, row["id"], origin, outcome)

    def _execute_row(self, row, work_deadline: float) -> str:
        authority = Authority(row["owner_id"], row["authority_session"])
        try:
            acquired = self.acquireExecutionClaim(
                authority, binding(row), self.worker_id, row["fence"] or None)
        except ResearchError as error:
            return self._refused_claim(row, error.code)
        except (PermissionError, InsufficientPrivilege):
            return self._refused_claim(row, "NOT_FOUND")
        claim = acquired["claim"]
        message = self._message(row, claim)
        try:
            payload = self.readExecutionPayload(authority, claim)
            sources = self.scope_sources(payload)
            request = self.request_of(authority, payload)
        except ResearchError as error:
            return self._close_claimed(row, claim, message, error.code)
        except InsufficientPrivilege:
            return self._close_claimed(row, claim, message, "SOURCE_INELIGIBLE")
        except PermissionError:
            return self._close_claimed(row, claim, message, "EXPIRED")
        sent: list[dict] = []
        try:
            output = self.provider.run(sources, request=request, deadline=work_deadline,
                                       sent=sent)
        except ProviderWaiting as waiting:
            return self._wait(row, claim, waiting.wait_reason)
        except ResearchFailure as failure:
            return self._finish(authority, row, acquired, message, outcome="failed",
                                code=failure.code)
        key = str(row["id"])
        self._sent[key] = sent
        try:
            return self._finish(authority, row, acquired, message, outcome="succeeded",
                                output=output)
        finally:
            self._sent.pop(key, None)

    def _fact(self, row, acquired, message: UUID, *, outcome: str, output=None,
              code: str | None = None) -> dict:
        fact = {
            "messageId": str(message),
            "causationId": str(row["id"]),
            "ownerComponent": "ResearchWorkspace",
            "operationId": str(row["id"]),
            "kind": row["kind"],
            "outcome": outcome,
            "resultRef": None,
            "error": None,
            "claim": acquired["claim"],
            "expectedJobRevision": acquired["jobRevision"],
            "inputHash": row["input_hash"],
            "progress": None,
            "prepared": None,
            "usageRecordId": str(row["usage_id"]),
        }
        if outcome == "succeeded":
            artifact_id = uuid5(UUID(str(row["id"])), "research-result:1")
            fact["resultRef"] = {"resultId": str(artifact_id), "revision": "1",
                                 "contentHash": digest(output), "mediaType": "application/json"}
            fact["prepared"] = artifact_dto({
                "id": artifact_id, "revision": 1, "content_hash": digest(output),
                "owner_id": row["owner_id"], "context_id": row["context_id"],
                "job_id": row["id"], "kind": ARTIFACT_KINDS[row["kind"]], "output": output,
                "eligibility_revision": 1, "policy": row["policy"],
            })
        elif outcome == "failed":
            fact["error"] = {"code": code, "requestId": str(row["id"]), "retryable": False,
                             "messageKey": "research.failed"}
        return fact

    def _finish(self, authority, row, acquired, message: UUID, *, outcome: str, output=None,
                code: str | None = None) -> str:
        """Record the one terminal fact. An unknown commit is sent once more and then
        left to the lease and the outstanding reconcile; a moved fence discards it; any
        other refusal of the completion closes the job `failed` with that refusal's code
        under the same message identifier."""
        fact = self._fact(row, acquired, message, outcome=outcome, output=output, code=code)
        for _ in range(2):
            try:
                return self.recordCompletion(authority, fact)["state"]
            except UnknownCommit:
                continue
            except ResearchError as error:
                if error.code == "CONFLICT":
                    return "fenced"
                if error.code == "IDEMPOTENCY_CONFLICT":
                    return "unknown"
                return self._close_claimed(row, acquired["claim"], message, error.code)
            except (PermissionError, InsufficientPrivilege):
                return self._close_claimed(row, acquired["claim"], message, "EXPIRED")
        return "unknown"

    # --- the job's sources and request --------------------------------------------------

    def scope_sources(self, payload) -> list[dict]:
        """What the provider may read: each scope paper by its identity alone (the
        provider reads its excerpts), then one unread entry per scope web reference."""
        snapshot = payload["input"]["inputSnapshot"]
        result = []
        for paper in snapshot["scope"]["publicPapers"]:
            identity = self.corpus.research_identity(paper["versionId"])
            if identity["paper_id"] != paper["paperId"]:
                raise ResearchError("SOURCE_INELIGIBLE")
            result.append({"sourceKind": "public-paper", "sourceId": paper["paperId"],
                           "sourceVersion": paper["versionId"],
                           "sourceUrl": identity["source_url"]})
        result.extend(unread_reference(url) for url in snapshot["scope"]["webReferences"])
        return result

    def sources(self, payload):
        """The sources completion validates against: exactly the rows this job sent,
        re-read by version and ordinal (`research_rows`), and its unread references."""
        sent = self._sent.get(payload["binding"]["operationId"], [])
        result = []
        by_version: dict[str, list[dict]] = {}
        for item in sent:
            by_version.setdefault(item["sourceVersion"], []).append(item)
        for version, items in by_version.items():
            first = items[0]
            for row in self.corpus.research_rows(version, [item["ordinal"] for item in items]):
                result.append({
                    "sourceKind": "public-paper", "sourceId": first["sourceId"],
                    "sourceVersion": version, "sourceUrl": first["sourceUrl"],
                    "location": row["location"], "text": row["text"],
                })
        snapshot = payload["input"]["inputSnapshot"]
        result.extend(unread_reference(url) for url in snapshot["scope"]["webReferences"])
        return result

    def request_of(self, authority, payload) -> dict:
        """`{kind, mode, text, prior}`: a discussion carries the earlier result's output,
        read as data (U4's BR6.3); it never reruns the analysis."""
        snapshot = payload["input"]["inputSnapshot"]
        kind = payload["input"]["kind"]
        prior = None
        if kind == "novelty-discussion":
            prior = self.read_artifact(authority, snapshot["source"])["output"]
        return {"kind": kind, "mode": snapshot.get("mode") or snapshot.get("inputMode"),
                "text": snapshot["text"], "prior": prior,
                "jobId": payload["binding"]["operationId"]}


# --- ProductionResearchService -------------------------------------------------------------


class ProductionResearchService(ResearchService):
    """U4's service under `PRODUCTION_RESEARCH`: the server enforces 2,048 bytes and
    accepts the production policy reference. A new request is refused with
    `DEPENDENCY_UNAVAILABLE` while its capability's latest observation is missing,
    stale, unavailable or reads `model-runtime-waiting`: one short read, never a runtime
    call (P7, NFR8.5). `observed(capability)` returns the latest fresh observation, or
    None when there is none or it is stale (unknown never counts as available, BR3.2)."""

    def __init__(self, transactions, corpus, *, execution, observed: Callable[[str], dict | None],
                 policy: ProductionResearchPolicy = PRODUCTION_RESEARCH):
        require_production(transactions, policy)
        super().__init__(transactions, corpus, execution=execution, policy=policy)
        self.observed = observed

    def admits(self, capability: str) -> bool:
        try:
            row = self.observed(capability)
        except Exception:  # noqa: BLE001 - an unreadable store never admits work
            return False
        return bool(
            row is not None
            and row.get("outcome") in ("available", "degraded")
            and row.get("reason_key") != WAITING_REASON
        )

    def accept(self, authority, operation, value, kind):
        if not self.admits(CAPABILITY_OF[kind]):
            raise ResearchError("DEPENDENCY_UNAVAILABLE")
        return super().accept(authority, operation, value, kind)

    def scope(self, authority, scope):
        """U4's scope checks, reading only each version's identity (`research_identity`):
        the paper, its eligibility and its source address, never its content."""
        from urllib.parse import urlsplit

        self.repository.run(
            authority, lambda conn: self.repository.context(conn, authority, scope["contextId"])
        )
        self.require_policy(scope["scopePolicy"])
        if len(scope["publicPapers"]) > 2 or len(scope["webReferences"]) > 8:
            raise ResearchError("INVALID_ARGUMENT")
        if scope["attachmentIds"]:
            raise ResearchError("POLICY_UNRESOLVED")
        for reference in scope["webReferences"]:
            try:
                parsed = urlsplit(reference)
                if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                        or parsed.password or parsed.port not in (None, 443)):
                    raise ValueError
            except (ValueError, TypeError):
                raise ResearchError("SOURCE_INELIGIBLE") from None
        for paper in scope["publicPapers"]:
            try:
                identity = self.corpus.research_identity(paper["versionId"])
            except InsufficientPrivilege:
                raise ResearchError("SOURCE_INELIGIBLE") from None
            if (identity["paper_id"] != paper["paperId"]
                    or str(identity["eligibility_revision"]) != paper["eligibilityRevision"]):
                raise ResearchError("SOURCE_INELIGIBLE")


# --- production_research(ctx) --------------------------------------------------------------

RESEARCH_MODES = ("question", "compare", "quote")
NOVELTY_MODES = ("topic",)


def capability_rows() -> list[dict]:
    """Production's rows: research with its three modes and novelty with its topic mode,
    both in Korean over excerpts, and neither synthetic-only."""
    return [
        {"id": name, "state": "available", "modeIds": [*modes, "excerpts"],
         "languageIds": ["ko"], "levelIds": [], "formatIds": ["json"],
         "policy": PRODUCTION_RESEARCH.reference()}
        for name, modes in (("research", RESEARCH_MODES), ("novelty", NOVELTY_MODES))
    ]


def observation_reader(ctx) -> Callable[[str], dict | None]:
    """The latest fresh observation of a capability, from ServiceOperations' store as
    the composition holds it (read at call time, so the contribution's build order does
    not matter); None when there is none, it is stale, or ServiceOperations is absent."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from backend.u8_registry import CAPABILITY_BY_ID, timing

    def latest(capability: str) -> dict | None:
        operations = ctx.parts.get("service-operations")
        if operations is None:
            return None
        row = operations["observations"].latest([capability]).get(capability)
        if row is None:
            return None
        _, freshness, _ = timing(CAPABILITY_BY_ID[capability], PRODUCTION_OPERATIONS)
        if (ctx.clock() - row["observed_at"]).total_seconds() > freshness:
            return None
        return row

    return latest


def production_research(ctx) -> dict:
    """ResearchWorkspace's production contribution, on the paper corpus's shared model
    runtime and embedder: U4's `ResearchWorker` and `research_router` over the production
    execution and service, with production's capability rows. Refused with
    `policy-unresolved` without a runtime or an embedder."""
    from backend.modules.research.http import research_router
    from backend.u4_host import ResearchWorker
    from backend.u8_host import PolicyUnresolved
    from backend.u8_outward import readiness_recorded
    from backend.u8_research_model import CorpusRanker, LocalResearchModel

    corpus = ctx.parts.get("paper-corpus") or {}
    runtime, embedder = corpus.get("runtime"), corpus.get("embedder")
    if runtime is None or embedder is None:
        raise PolicyUnresolved("policy-unresolved")
    repository = corpus["corpus_repository"]
    provider = LocalResearchModel(
        runtime, ready=readiness_recorded(ctx.profile, "research"),
        ranker=CorpusRanker(repository, embedder), clock=time.monotonic,
    )
    execution = ProductionResearchExecution(ctx.transactions, repository, provider,
                                            lane=runtime)
    service = ProductionResearchService(ctx.transactions, repository, execution=execution,
                                        observed=observation_reader(ctx))
    return {
        "service": service,
        "execution": execution,
        "provider": provider,
        "capabilities": capability_rows(),
        "router": research_router(ctx.transactions, entry=ctx.parts["paper-journey"]["entry"],
                                  service=service),
        "worker": ResearchWorker(corpus["worker"], execution),
    }
